using System.Diagnostics;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Timetabling.Engine;

/// <summary>Port of engine/runner.py prepare, check_configuration and run_one (without the Python-only custom method).</summary>
public static partial class Runner
{
    public const int MaxClasses = 2000, MaxRecurringSessions = 6000;
    const string SourcePrefix = "engine-src/";

    static Prepared PrepareCore(string datasetText)
    {
        var raw = JsonNode.Parse(datasetText) as JsonObject ?? throw new ArgumentException("Dataset must be a JSON object");
        static int Length(JsonNode? node) => node is JsonArray a ? a.Count : 0;
        if (Length(raw["classes"]) > MaxClasses || Length(raw["recurring_sessions"]) > MaxRecurringSessions)
            throw new ArgumentException("Dataset exceeds the browser workbench size limit");
        var report = InputValidator.ValidateRaw(raw, datasetText, out var data);
        if (report.Errors.Count > 0)
            throw new ArgumentException("Invalid dataset: " + string.Join("; ", report.Errors.Take(8)));
        var started = Stopwatch.GetTimestamp();
        var problem = new Problem(data!);
        var seconds = Stopwatch.GetElapsedTime(started).TotalSeconds;
        var meta = new PreparationMeta(report.Summary, report.Warnings, Dataset.Sha256(datasetText), seconds, Weights(problem));
        return new Prepared(problem, meta, datasetText);
    }

    static EnergyWeights Weights(Problem problem) => new(problem.UnassignedWeight, problem.MinuteWeight, 1);

    static void CheckCore(RunConfig config)
    {
        if (config.Budget is < 1 or > 100000)
            throw new ArgumentException("Evaluation budget must be an integer from 1 to 100000");
        if (double.IsNaN(config.Seconds) || config.Seconds is < 1 or > 3600)
            throw new ArgumentException("Time limit must be 1..3600 seconds per run");
        if (!RoomModes.IsValid(config.RoomMode))
            throw new ArgumentException("Room mode must be weekly or fixed");
        var p = config.Parameters ?? new MethodParameters();
        if (p.Hc.RestartPatience is < 1 or > 10000)
            throw new ArgumentException("HC restart patience must be 1..10000");
        if (!(0 < p.Sa.InitialAcceptance && p.Sa.InitialAcceptance < 1) || !(0 < p.Sa.CoolingRate && p.Sa.CoolingRate < 1))
            throw new ArgumentException("SA acceptance and cooling rate must be strictly between 0 and 1");
        var pop = p.Ga.PopulationSize;
        if (pop is < 4 or > 100 || !(1 <= p.Ga.Elites && p.Ga.Elites < pop))
            throw new ArgumentException("GA requires population 4..100 and 1 <= elites < population");
        if (!(2 <= p.Ga.TournamentSize && p.Ga.TournamentSize <= pop))
            throw new ArgumentException("GA tournament size must be 2..population size");
        foreach (var rate in new[] { p.Ga.MutationRate, p.Ga.CrossoverRate })
            if (!(0 <= rate && rate <= 1))
                throw new ArgumentException("GA probabilities must be in [0,1]");
    }

    static RunResult RunCore(Prepared prepared, RunConfig config, string method, ulong seed,
                             Action<ProgressEvent>? progress, CancellationToken cancellation)
    {
        CheckCore(config);
        if (!Algorithms.Names.Contains(method)) throw new ArgumentException("Unknown algorithm: " + method);
        if (seed > uint.MaxValue) throw new ArgumentException("Seed must be an integer in [0, 2^32-1]");
        var problem = prepared.Problem;
        var parameters = config.Parameters ?? new MethodParameters();
        var context = new SearchContext(problem, seed, config.Budget, config.Seconds, progress, config.RoomMode, cancellation);
        string status = "completed";
        RunError? failure = null;
        var started = Stopwatch.GetTimestamp();
        try
        {
            context.Initial = context.Evaluate(problem.InitialGenome());
            Algorithms.Run(method, problem, context, parameters);
        }
        catch (SearchStoppedException stop)
        {
            status = stop.Reason;
        }
        catch (Exception exc)
        {
            status = "error";
            failure = new RunError(exc.Message, exc.ToString());
        }
        var searchSeconds = Stopwatch.GetElapsedTime(started).TotalSeconds;
        var solution = context.Best?.Solution;
        var validationStart = Stopwatch.GetTimestamp();
        var checkedResult = SolutionValidator.Audit(problem.Data, solution, config.RoomMode);
        var validationSeconds = Stopwatch.GetElapsedTime(validationStart).TotalSeconds;
        if (status != "error" && !checkedResult.Valid) status = "invalid_solution";
        if (checkedResult.Valid && context.Best is not null)
        {
            var actual = checkedResult.Metrics!;
            var independent = new Objectives(actual.UnassignedWeeklySessions, actual.UnnecessaryLabMinutes, actual.RoomChanges);
            if (independent != context.Best.Objectives)
            {
                status = "error";
                failure = new RunError("Search score disagrees with independent solution validator");
            }
        }
        return new RunResult
        {
            Algorithm = method,
            RoomMode = config.RoomMode,
            Seed = seed,
            Status = status,
            Valid = checkedResult.Valid && status != "error",
            Metrics = checkedResult.Metrics,
            Validation = checkedResult,
            Solution = solution,
            Evaluations = context.Evaluations,
            AttemptedEvaluations = context.AttemptedEvaluations,
            Budget = context.Budget,
            TimeLimitSeconds = config.Seconds,
            SearchSeconds = searchSeconds,
            ValidationSeconds = validationSeconds,
            Trace = context.Trace,
            Error = failure,
            Parameters = GivenParameters(config, method),
            DatasetId = problem.Data.DatasetId,
            DatasetSha256 = prepared.Meta.DatasetSha256,
            OriginalSourceSha256 = problem.Data.Source?.Sha256,
            CodeSha256 = AlgorithmsSha256,
            EngineVersion = Problem.Version,
            Runtime = new JsonObject { ["dotnet"] = Environment.Version.ToString(), ["platform"] = PlatformName() },
            EnergyWeights = Weights(problem),
        };
    }

    /// <summary>Python records config['parameters'].get(method, {}): the chosen method's object as given.</summary>
    static JsonObject GivenParameters(RunConfig config, string method)
    {
        if (config.ParametersJson is { } given)
            return given[method] is JsonObject o ? (JsonObject)o.DeepClone() : [];
        if (config.Parameters is not { } p) return [];
        object? typed = method switch { "hc" => p.Hc, "sa" => p.Sa, "ga" => p.Ga, _ => null };
        return typed is null ? [] : JsonSerializer.SerializeToNode(typed, typed.GetType(), Dataset.Json)!.AsObject();
    }

    /// <summary>The value Python's platform.system() reports on the same OS.</summary>
    static string PlatformName() =>
        OperatingSystem.IsWindows() ? "Windows" : OperatingSystem.IsLinux() ? "Linux" : OperatingSystem.IsMacOS() ? "Darwin"
        : RuntimeInformation.OSDescription;

    // ---- Source hashes -------------------------------------------------------------------------------

    static readonly Lazy<SortedDictionary<string, string>> sources = new(() =>
    {
        var assembly = typeof(Runner).Assembly;
        var map = new SortedDictionary<string, string>(StringComparer.Ordinal);
        foreach (var name in assembly.GetManifestResourceNames().Where(n => n.StartsWith(SourcePrefix, StringComparison.Ordinal)))
        {
            using var stream = assembly.GetManifestResourceStream(name)!;
            using var reader = new StreamReader(stream, new UTF8Encoding(false, true), detectEncodingFromByteOrderMarks: true);
            // Universal newlines, as Python's Path.read_text(): the hash does not depend on the git checkout's line endings.
            map[name[SourcePrefix.Length..]] = reader.ReadToEnd().Replace("\r\n", "\n").Replace('\r', '\n');
        }
        if (!map.ContainsKey("Algorithms.cs")) throw new InvalidOperationException("Engine sources are not embedded in " + assembly.GetName().Name);
        return map;
    });

    static string Hex(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    /// <summary>SHA-256 of the C# Algorithms.cs source (counterpart of run_one's code_sha256 of algorithms.py).</summary>
    public static string AlgorithmsSha256 => algorithmsSha.Value;
    static readonly Lazy<string> algorithmsSha = new(() => Hex(Encoding.UTF8.GetBytes(sources.Value["Algorithms.cs"])));

    /// <summary>Same construction as batch.engine_snapshot: SHA-256 of compact JSON {file name: source text}, here sorted by name.</summary>
    static readonly Lazy<string> engineSha = new(() =>
    {
        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer, new JsonWriterOptions { Encoder = Dataset.Json.Encoder }))
        {
            writer.WriteStartObject();
            foreach (var (name, text) in sources.Value) writer.WriteString(name, text);
            writer.WriteEndObject();
        }
        return Hex(buffer.ToArray());
    });

    /// <summary>The embedded engine sources by file name, LF line endings (counterpart of batch code_snapshot).</summary>
    public static IReadOnlyDictionary<string, string> EngineSources => sources.Value;
}
