using System.Diagnostics;
using System.IO.Compression;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Timetabling.Engine;

namespace Timetabling.Cli;

public sealed record Job(string ConfigId, string Algorithm, string RoomMode, ulong Seed, int Budget, double Seconds, JsonObject Parameters)
{
    /// <summary>Same file key as engine/batch.py job_key.</summary>
    public string Key => $"{ConfigId}__{RoomMode}__{Algorithm}__{Seed}";

    public JsonObject MethodParameters => Parameters[Algorithm] is JsonObject o ? (JsonObject)o.DeepClone() : [];
}

/// <summary>Resumable parallel batch runner; writes the same files as engine/batch.py.</summary>
public static class Batch
{
    public static readonly string[] CsvFields = ["config_id", "room_mode", "algorithm", "seed", "status", "valid", "evaluations", "budget",
        "search_seconds", "unassigned_weekly_sessions", "unnecessary_lab_hours", "room_changes", "hard_violations", "dataset_sha256", "engine_sha256"];

    static readonly JsonSerializerOptions Compact = new(Dataset.Json) { WriteIndented = false };
    static readonly JsonSerializerOptions Indented = new(Dataset.Json) { WriteIndented = true };

    public static List<Job> BuildJobs(IEnumerable<string> methods, IEnumerable<string> modes, IEnumerable<ulong> seeds,
                                      int budget, double seconds, JsonObject parameters, string configId = "main") =>
        (from mode in modes from seed in seeds from method in methods
         select new Job(configId, method, mode, seed, budget, seconds, parameters)).ToList();

    /// <summary>Everything that determines a run's result; a stored run is reused only if this matches.</summary>
    public static string Fingerprint(Job job, string datasetSha, string engineSha)
    {
        var keep = new JsonObject
        {
            ["config_id"] = job.ConfigId, ["room_mode"] = job.RoomMode, ["algorithm"] = job.Algorithm,
            ["seed"] = job.Seed, ["budget"] = job.Budget, ["seconds"] = job.Seconds,
            ["parameters"] = job.MethodParameters, ["dataset_sha256"] = datasetSha, ["engine_sha256"] = engineSha,
            ["engine"] = "dotnet",
        };
        // Round-trip through text so every number keeps its literal form for the Python-style dump.
        return PyCompat.Sha256Hex(PyCompat.DumpsSorted(JsonNode.Parse(keep.ToJsonString())));
    }

    public static MethodParameters ParseParameters(JsonObject parameters) =>
        parameters.Deserialize<MethodParameters>(Dataset.Json) ?? new MethodParameters();

    public static JsonObject ReadParameterFile(string? path)
    {
        if (path is null) return [];
        var node = JsonNode.Parse(File.ReadAllText(path)) as JsonObject ?? throw new InvalidDataException("Parameters must be a JSON object");
        if (node["parameters"] is JsonObject inner) node = inner;
        var result = new JsonObject();
        foreach (var name in new[] { "hc", "sa", "ga" })
            if (node[name] is JsonObject o) result[name] = o.DeepClone();
        return result;
    }

    public static List<RunResult> RunJobs(IReadOnlyList<Job> jobs, string output, string datasetPath, int workers,
                                          bool slim, string name, Action<string> log, CancellationToken cancellation = default)
    {
        var runsDir = Path.Combine(output, "runs");
        Directory.CreateDirectory(runsDir);
        var merged = Path.Combine(output, "experiment.json.gz");
        if (File.Exists(merged) && Directory.GetFiles(runsDir, "*.json").Length == 0)
        {
            // A finished, merged batch: unpack it so the same command resumes instead of starting over.
            var payload = JsonNode.Parse(Dataset.ReadText(merged))!;
            foreach (var r in payload["batch"]!["results"]!.AsArray())
            {
                var run = r!.AsObject();
                run.Remove("run_index");
                var key = $"{run["config_id"]?.GetValue<string>() ?? "main"}__{run["room_mode"]}__{run["algorithm"]}__{run["seed"]}";
                File.WriteAllText(Path.Combine(runsDir, key + ".json"), run.ToJsonString(Compact), Utf8);
            }
        }
        var text = Dataset.ReadText(datasetPath);
        var prepared = Runner.Prepare(text);
        var datasetSha = prepared.Meta.DatasetSha256;
        var engineSha = Runner.EngineSha256;
        if (jobs.Select(j => j.Key).Distinct().Count() != jobs.Count) throw new ArgumentException("Duplicate jobs in batch");
        var pending = new List<(Job Job, string Target, string Fingerprint)>();
        foreach (var job in jobs)
        {
            Runner.CheckConfiguration(new RunConfig(job.Budget, job.Seconds, job.RoomMode, ParseParameters(job.Parameters)));
            var fingerprint = Fingerprint(job, datasetSha, engineSha);
            var target = Path.Combine(runsDir, job.Key + ".json");
            if (File.Exists(target))
            {
                var stored = JsonNode.Parse(File.ReadAllText(target, Utf8));
                if (stored?["fingerprint"]?.GetValue<string>() != fingerprint)
                    throw new InvalidOperationException($"{target} was produced by a different configuration, dataset or engine; " +
                                                        "use a new --output directory or delete it deliberately");
                continue;
            }
            pending.Add((job, target, fingerprint));
        }
        var manifestPath = Path.Combine(output, "manifest.json");
        var manifest = File.Exists(manifestPath)
            ? JsonNode.Parse(File.ReadAllText(manifestPath, Utf8))!.AsObject()
            : new JsonObject { ["name"] = name, ["created_at"] = PyCompat.NowIso(), ["sessions"] = new JsonArray() };
        log($"{jobs.Count - pending.Count} / {jobs.Count} runs already done; running {pending.Count} with {workers} workers");
        var session = new JsonObject { ["started_at"] = PyCompat.NowIso(), ["runs"] = pending.Count, ["workers"] = workers };
        var wall = Stopwatch.StartNew();
        var failures = new List<string>();
        var done = 0;
        var gate = new object();
        Parallel.ForEach(pending, new ParallelOptions { MaxDegreeOfParallelism = workers, CancellationToken = cancellation }, item =>
        {
            try
            {
                var (job, target, fingerprint) = item;
                var config = new RunConfig(job.Budget, job.Seconds, job.RoomMode, ParseParameters(job.Parameters));
                var started = PyCompat.NowIso();
                var result = Runner.RunOne(prepared, config, job.Algorithm, job.Seed, null, cancellation);
                result.Parameters = job.MethodParameters;
                result.ConfigId = job.ConfigId;
                result.Fingerprint = fingerprint;
                result.StartedAt = started;
                result.FinishedAt = PyCompat.NowIso();
                result.WorkerPid = Environment.ProcessId;
                if (slim) Slim(result);
                var temporary = Path.ChangeExtension(target, ".tmp");
                File.WriteAllText(temporary, JsonSerializer.Serialize(result, Compact), Utf8);
                File.Move(temporary, target, true);
                var m = result.Metrics;
                lock (gate)
                {
                    done++;
                    log($"[{done}/{pending.Count}] {job.Key} {result.Status} {result.Valid} {m?.UnassignedWeeklySessions} " +
                        $"{m?.UnnecessaryLabHours} {m?.RoomChanges} {Math.Round(result.SearchSeconds, 1)}");
                }
            }
            catch (Exception exc) when (exc is not OperationCanceledException)
            {
                lock (gate) { failures.Add(exc.ToString()); log("FAILED " + exc.Message); }
            }
        });
        session["finished_at"] = PyCompat.NowIso();
        session["wall_seconds"] = wall.Elapsed.TotalSeconds;
        session["failures"] = new JsonArray(failures.Select(f => (JsonNode?)JsonValue.Create(f)).ToArray());
        var root = RepoRoot(datasetPath);
        manifest["dataset"] = Path.GetRelativePath(root, Path.GetFullPath(datasetPath)).Replace('\\', '/');
        manifest["dataset_sha256"] = datasetSha;
        manifest["engine"] = "dotnet";
        manifest["engine_sha256"] = engineSha;
        manifest["dotnet"] = Environment.Version.ToString();
        manifest["platform"] = OperatingSystem.IsWindows() ? "win32" : OperatingSystem.IsMacOS() ? "darwin" : "linux";
        manifest["cpu_count"] = Environment.ProcessorCount;
        manifest["total_runs"] = jobs.Count;
        var sessions = manifest["sessions"]!.AsArray();
        if (pending.Count > 0) sessions.Add(session);
        manifest["wall_seconds_total"] = sessions.Sum(s => s!["wall_seconds"]!.GetValue<double>());
        File.WriteAllText(manifestPath, manifest.ToJsonString(Indented), Utf8);
        if (failures.Count > 0) throw new InvalidOperationException($"{failures.Count} runs failed; rerun the same command to retry them");
        return jobs.Select(j => JsonSerializer.Deserialize<RunResult>(File.ReadAllText(Path.Combine(runsDir, j.Key + ".json"), Utf8), Dataset.Json)!).ToList();
    }

    static void Slim(RunResult result)
    {
        // Drop the full schedule and violation list (tuning runs); metrics and trace stay.
        result.Solution = null;
        if (result.Validation is { } v) result.Validation = v with { Violations = [] };
    }

    public static string Merge(string output, string? name = null, bool keepRuns = false)
    {
        var runsDir = Path.Combine(output, "runs");
        var results = Directory.Exists(runsDir)
            ? Directory.GetFiles(runsDir, "*.json").OrderBy(p => p, StringComparer.Ordinal)
                .Select(p => JsonNode.Parse(File.ReadAllText(p, Utf8))!.AsObject()).ToList()
            : [];
        if (results.Count == 0) throw new InvalidOperationException("No runs found in " + runsDir);
        var manifest = JsonNode.Parse(File.ReadAllText(Path.Combine(output, "manifest.json"), Utf8))!.AsObject();
        var root = RepoRoot(output);
        var datasetPath = Path.Combine(root, manifest["dataset"]!.GetValue<string>());
        var text = Dataset.ReadText(datasetPath);
        var engineSha = Runner.EngineSha256;
        if (manifest["engine_sha256"]?.GetValue<string>() != engineSha || results.Any(r => r["engine_version"] is null))
            throw new InvalidOperationException("Engine code changed since these runs were made; merge with the original code");
        var order = new Dictionary<string, int> { ["greedy"] = 0, ["hc"] = 1, ["sa"] = 2, ["ga"] = 3 };
        results = results.OrderBy(r => r["config_id"]?.GetValue<string>() ?? "", StringComparer.Ordinal)
            .ThenBy(r => r["room_mode"]!.GetValue<string>(), StringComparer.Ordinal)
            .ThenBy(r => r["seed"]!.GetValue<ulong>())
            .ThenBy(r => order.GetValueOrDefault(r["algorithm"]!.GetValue<string>(), 9)).ToList();
        for (var i = 0; i < results.Count; i++) results[i]["run_index"] = i;
        var modes = results.Select(r => r["room_mode"]!.GetValue<string>()).Distinct().ToList();
        var first = results[0];
        var parameters = new JsonObject();
        foreach (var r in results)
            if (r["parameters"] is JsonObject p && p.Count > 0) parameters[r["algorithm"]!.GetValue<string>()] = p.DeepClone();
        var prepared = Runner.Prepare(text);
        var sessions = manifest["sessions"]!.AsArray();
        var batch = new JsonObject
        {
            ["id"] = PyCompat.Uuid5Url(Path.GetFullPath(output)).ToString(),
            ["name"] = name ?? manifest["name"]?.GetValue<string>(),
            ["created_at"] = manifest["created_at"]!.DeepClone(),
            ["finished_at"] = sessions.Count > 0 ? sessions[^1]!["finished_at"]!.DeepClone() : manifest["created_at"]!.DeepClone(),
            ["status"] = "completed",
            ["dataset_hash"] = manifest["dataset_sha256"]!.DeepClone(),
            ["dataset_id"] = first["dataset_id"]!.DeepClone(),
            ["dataset_label"] = Path.GetFileName(manifest["dataset"]!.GetValue<string>()),
            ["config"] = new JsonObject
            {
                ["budget"] = first["budget"]!.DeepClone(), ["seconds"] = first["time_limit_seconds"]!.DeepClone(),
                ["methods"] = new JsonArray(results.Select(r => r["algorithm"]!.GetValue<string>()).Distinct().Select(m => (JsonNode?)m).ToArray()),
                ["room_modes"] = new JsonArray(modes.Select(m => (JsonNode?)m).ToArray()),
                ["room_mode"] = modes.Count == 1 ? modes[0] : null,
                ["seeds"] = new JsonArray(results.Select(r => r["seed"]!.GetValue<ulong>()).Distinct().Order().Select(s => (JsonNode?)s).ToArray()),
                ["parameters"] = parameters,
            },
            ["preparation"] = JsonSerializer.SerializeToNode(prepared.Meta, Dataset.Json),
            ["engine"] = "dotnet",
            ["code_snapshot"] = EngineSources(),
            ["engine_sha256"] = engineSha,
            ["run_order"] = new JsonArray(results.Select(r => (JsonNode?)new JsonObject
            {
                ["algorithm"] = r["algorithm"]!.DeepClone(), ["room_mode"] = r["room_mode"]!.DeepClone(), ["seed"] = r["seed"]!.DeepClone(),
            }).ToArray()),
            ["results"] = new JsonArray(results.Select(r => (JsonNode?)r).ToArray()),
        };
        var payload = new JsonObject
        {
            ["format"] = "timetable-lab-experiment/v1", ["exported_at"] = PyCompat.NowIso(), ["batch"] = batch, ["dataset_text"] = text,
        };
        var blob = Utf8.GetBytes(payload.ToJsonString(Compact));
        var target = Path.Combine(output, "experiment.json.gz");
        using (var file = File.Create(target))
        using (var gz = new GZipStream(file, CompressionLevel.SmallestSize))
            gz.Write(blob);
        using (var csv = PyCompat.CsvWriter(Path.Combine(output, "experiment.csv")))
        {
            csv.WriteLine(string.Join(",", CsvFields));
            foreach (var r in results)
            {
                var m = r["metrics"] as JsonObject;
                string? Num(JsonNode? n) => n is null ? null : n.GetValueKind() == JsonValueKind.Number
                    ? (n.ToJsonString().IndexOfAny(['.', 'e', 'E']) >= 0 ? PyCompat.Float(n.GetValue<double>()) : n.ToJsonString()) : n.ToString();
                var hours = m?["unnecessary_lab_hours"];
                string?[] row =
                [
                    r["config_id"]?.GetValue<string>(), r["room_mode"]!.GetValue<string>(), r["algorithm"]!.GetValue<string>(),
                    r["seed"]!.ToJsonString(), r["status"]!.GetValue<string>(), PyCompat.Bool(r["valid"]!.GetValue<bool>()),
                    r["evaluations"]!.ToJsonString(), r["budget"]!.ToJsonString(),
                    PyCompat.Float(Math.Round(r["search_seconds"]!.GetValue<double>(), 3, MidpointRounding.ToEven)),
                    Num(m?["unassigned_weekly_sessions"]),
                    hours is null ? null : PyCompat.Float(hours.GetValue<double>()),
                    Num(m?["room_changes"]), Num(r["validation"]?["violation_count"]),
                    r["dataset_sha256"]?.GetValue<string>(), engineSha,
                ];
                csv.WriteLine(string.Join(",", row.Select(PyCompat.CsvField)));
            }
        }
        if (!keepRuns)
        {
            foreach (var p in Directory.GetFiles(runsDir, "*.json")) File.Delete(p);
            Directory.Delete(runsDir);
        }
        return target;
    }

    /// <summary>The engine's own .cs sources embedded in the engine assembly (code_snapshot for provenance).</summary>
    public static JsonObject EngineSources()
    {
        var assembly = typeof(Problem).Assembly;
        var sources = new JsonObject();
        foreach (var resource in assembly.GetManifestResourceNames().Where(n => n.EndsWith(".cs", StringComparison.Ordinal)).Order(StringComparer.Ordinal))
        {
            using var stream = assembly.GetManifestResourceStream(resource)!;
            using var reader = new StreamReader(stream, Utf8);
            sources[resource] = reader.ReadToEnd();
        }
        return sources;
    }

    /// <summary>The repository root (the folder holding data/provenance.json) above <paramref name="start"/>, or the working directory.</summary>
    public static string RepoRoot(string start)
    {
        for (var dir = new DirectoryInfo(Path.GetFullPath(start)); dir is not null; dir = dir.Parent)
            if (File.Exists(Path.Combine(dir.FullName, "data", "provenance.json"))) return dir.FullName;
        for (var dir = new DirectoryInfo(Directory.GetCurrentDirectory()); dir is not null; dir = dir.Parent)
            if (File.Exists(Path.Combine(dir.FullName, "data", "provenance.json"))) return dir.FullName;
        return Directory.GetCurrentDirectory();
    }

    static readonly Encoding Utf8 = new UTF8Encoding(false);
}
