using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Timetabling.Cli;
using Timetabling.Engine;

// Native C# counterpart of engine/cli.py ("run") and engine/batch.py ("batch run" / "batch merge").
// Output files use the same format, so engine/analyze.py and the web app read them unchanged.
return Cli.Run(args);

static class Cli
{
    const string Usage = """
        Timetable Lab, C# engine (results identical to the Python engine for the same seed)

          timetabling run   [--dataset P] [--methods greedy hc sa ga] [--room-modes weekly fixed]
                            [--budget 50] [--seconds 60] [--seed 42] [--repeats 3]
                            [--parameters P] [--name N] [--output results]
          timetabling batch run --seeds 1001-1030 --budget 500 --output DIR
                            [--dataset P] [--methods ...] [--room-modes ...] [--seconds 3600]
                            [--parameters P] [--workers N] [--name N] [--slim] [--keep-runs]
          timetabling batch merge --output DIR [--name N] [--keep-runs]
        """;

    public static int Run(string[] argv)
    {
        Console.OutputEncoding = Encoding.UTF8;
        try
        {
            var args = Args.Parse(argv);
            var cancel = new CancellationTokenSource();
            Console.CancelKeyPress += (_, e) => { e.Cancel = true; cancel.Cancel(); };
            switch (args.Positional)
            {
                case ["run"]: return SingleRun(args, cancel.Token);
                case ["batch", "run"]: return BatchRun(args, cancel.Token);
                case ["batch", "merge"]:
                    Console.WriteLine("Saved " + Batch.Merge(args.Required("output"), args.Get("name"), args.Flag("keep-runs")));
                    return 0;
                default:
                    Console.WriteLine(Usage);
                    return args.Flag("help") || args.Positional.Count == 0 ? 0 : 2;
            }
        }
        catch (ArgumentException e) { Console.Error.WriteLine("error: " + e.Message); return 2; }
    }

    static string DefaultDataset() => Path.Combine(Batch.RepoRoot(AppContext.BaseDirectory), "data", "fall-cs.json.gz");

    static string[] Choices(Args args, string name, string[] allowed, string[] fallback)
    {
        var values = args.List(name) ?? fallback;
        foreach (var v in values)
            if (!allowed.Contains(v)) throw new ArgumentException($"--{name}: invalid choice '{v}' (choose from {string.Join(", ", allowed)})");
        return values.Distinct().ToArray();
    }

    static List<ulong> ParseSeeds(string spec)
    {
        var seeds = new List<ulong>();
        foreach (var raw in spec.Split(','))
        {
            var part = raw.Trim();
            if (part.Contains('-'))
            {
                var bounds = part.Split('-', 2);
                for (ulong s = ulong.Parse(bounds[0]), hi = ulong.Parse(bounds[1]); s <= hi; s++) seeds.Add(s);
            }
            else if (part.Length > 0) seeds.Add(ulong.Parse(part));
        }
        if (seeds.Count == 0 || seeds.Distinct().Count() != seeds.Count)
            throw new ArgumentException("Seed list is empty or has duplicates: " + spec);
        return seeds;
    }

    static int BatchRun(Args args, CancellationToken cancel)
    {
        var dataset = args.Get("dataset") ?? DefaultDataset();
        var parameters = Batch.ReadParameterFile(args.Get("parameters"));
        var jobs = Batch.BuildJobs(Choices(args, "methods", Algorithms.Names, Algorithms.Names),
            Choices(args, "room-modes", RoomModes.All, [RoomModes.Weekly]), ParseSeeds(args.Required("seeds")),
            args.Int("budget") ?? throw new ArgumentException("--budget is required"), args.Double("seconds") ?? 3600, parameters);
        var output = args.Required("output");
        var name = args.Get("name") ?? "Native batch experiment (C#)";
        Batch.RunJobs(jobs, output, dataset, args.Int("workers") ?? Math.Max(1, Environment.ProcessorCount - 2),
                      args.Flag("slim"), name, Console.WriteLine, cancel);
        Console.WriteLine("Saved " + Batch.Merge(output, name, args.Flag("keep-runs")));
        return 0;
    }

    static int SingleRun(Args args, CancellationToken cancel)
    {
        var dataset = args.Get("dataset") ?? DefaultDataset();
        var methods = Choices(args, "methods", Algorithms.Names, Algorithms.Names);
        var modes = Choices(args, "room-modes", RoomModes.All, [RoomModes.Weekly]);
        int budget = args.Int("budget") ?? 50, repeats = args.Int("repeats") ?? 3;
        double seconds = args.Double("seconds") ?? 60;
        var seed = (ulong)(args.Long("seed") ?? 42);
        if (repeats is < 1 or > 100 || seed + (ulong)repeats - 1 > uint.MaxValue) throw new ArgumentException("Invalid repeats or seed range");
        var parameters = Batch.ReadParameterFile(args.Get("parameters"));
        var typed = Batch.ParseParameters(parameters);
        var text = Dataset.ReadText(dataset);
        var seeds = Enumerable.Range(0, repeats).Select(i => seed + (ulong)i).ToArray();
        Runner.CheckConfiguration(new RunConfig(budget, seconds, modes[0], typed));
        var prepared = Runner.Prepare(text);
        var id = Guid.NewGuid().ToString();
        var batch = new JsonObject
        {
            ["id"] = id, ["name"] = args.Get("name") ?? "Native Fall CS experiment (C#)", ["created_at"] = PyCompat.NowIso(),
            ["status"] = "running", ["dataset_hash"] = prepared.Meta.DatasetSha256, ["dataset_id"] = prepared.Problem.Data.DatasetId,
            ["dataset_label"] = Path.GetFileName(dataset),
            ["config"] = new JsonObject
            {
                ["budget"] = budget, ["seconds"] = seconds, ["methods"] = JsonSerializer.SerializeToNode(methods),
                ["room_modes"] = JsonSerializer.SerializeToNode(modes), ["seeds"] = JsonSerializer.SerializeToNode(seeds),
                ["parameters"] = parameters.DeepClone(),
            },
            ["preparation"] = JsonSerializer.SerializeToNode(prepared.Meta, Dataset.Json),
            ["engine"] = "dotnet", ["code_snapshot"] = Batch.EngineSources(), ["engine_sha256"] = Runner.EngineSha256,
            ["run_order"] = new JsonArray((from mode in modes from s in seeds from m in methods
                                           select (JsonNode?)new JsonObject { ["algorithm"] = m, ["room_mode"] = mode, ["seed"] = s }).ToArray()),
            ["results"] = new JsonArray(),
        };
        var output = args.Get("output") ?? "results";
        Directory.CreateDirectory(output);
        var target = Path.Combine(output, $"experiment-{id}.json");
        var indented = new JsonSerializerOptions(Dataset.Json) { WriteIndented = true };
        void Save()
        {
            var payload = new JsonObject { ["format"] = "timetable-lab-experiment/v1", ["exported_at"] = PyCompat.NowIso(), ["batch"] = batch.DeepClone(), ["dataset_text"] = text };
            var temporary = Path.ChangeExtension(target, ".tmp");
            File.WriteAllText(temporary, payload.ToJsonString(indented), new UTF8Encoding(false));
            File.Move(temporary, target, true);
        }
        Save();
        var results = batch["results"]!.AsArray();
        try
        {
            foreach (var mode in modes)
                foreach (var s in seeds)
                    foreach (var method in methods)
                    {
                        cancel.ThrowIfCancellationRequested();
                        var result = Runner.RunOne(prepared, new RunConfig(budget, seconds, mode, typed) { ParametersJson = parameters }, method, s, null, cancel);
                        result.RunIndex = results.Count;
                        results.Add(JsonSerializer.SerializeToNode(result, Dataset.Json));
                        Save();
                        var m = result.Metrics;
                        Console.WriteLine($"{mode} {method} {s} {result.Status} unassigned={m?.UnassignedWeeklySessions} " +
                                          $"lab_hours={m?.UnnecessaryLabHours} room_changes={m?.RoomChanges}");
                    }
            batch["status"] = "completed";
        }
        catch (OperationCanceledException) { batch["status"] = "cancelled"; }
        finally
        {
            batch["finished_at"] = PyCompat.NowIso();
            Save();
        }
        string[] fields = ["room_mode", "algorithm", "seed", "status", "valid", "evaluations", "search_seconds", "unassigned_weekly_sessions",
                           "unnecessary_lab_hours", "room_changes", "hard_violations", "dataset_sha256", "code_sha256"];
        using (var csv = PyCompat.CsvWriter(Path.ChangeExtension(target, ".csv")))
        {
            csv.WriteLine(string.Join(",", fields));
            foreach (var r in results)
            {
                var m = r!["metrics"];
                string?[] row =
                [
                    r["room_mode"]!.GetValue<string>(), r["algorithm"]!.GetValue<string>(), r["seed"]!.ToJsonString(), r["status"]!.GetValue<string>(),
                    PyCompat.Bool(r["valid"]!.GetValue<bool>()), r["evaluations"]!.ToJsonString(), PyCompat.Float(r["search_seconds"]!.GetValue<double>()),
                    m?["unassigned_weekly_sessions"]?.ToJsonString(), m is null ? null : PyCompat.Float(m["unnecessary_lab_hours"]!.GetValue<double>()),
                    m?["room_changes"]?.ToJsonString(), r["validation"]?["violation_count"]?.ToJsonString(),
                    r["dataset_sha256"]?.GetValue<string>(), r["code_sha256"]?.GetValue<string>(),
                ];
                csv.WriteLine(string.Join(",", row.Select(PyCompat.CsvField)));
            }
        }
        Console.WriteLine("Saved " + target);
        return 0;
    }
}

/// <summary>Minimal GNU-style parser: positional words, --name value(s), --flag.</summary>
sealed class Args
{
    public List<string> Positional { get; } = [];
    readonly Dictionary<string, List<string>> options = [];

    public static Args Parse(string[] argv)
    {
        var args = new Args();
        string? current = null;
        foreach (var token in argv)
        {
            if (token.StartsWith("--", StringComparison.Ordinal))
            {
                var eq = token.IndexOf('=');
                current = eq > 0 ? token[2..eq] : token[2..];
                args.options[current] = eq > 0 ? [token[(eq + 1)..]] : [];
                if (eq > 0) current = null;
            }
            else if (current is not null) args.options[current].Add(token);
            else args.Positional.Add(token);
        }
        return args;
    }

    public bool Flag(string name) => options.ContainsKey(name);
    public string? Get(string name) => options.TryGetValue(name, out var v) && v.Count > 0 ? v[^1] : null;
    public string Required(string name) => Get(name) ?? throw new ArgumentException($"--{name} is required");
    public string[]? List(string name) => options.TryGetValue(name, out var v) && v.Count > 0 ? v.ToArray() : null;
    public int? Int(string name) => Get(name) is { } s ? int.Parse(s) : null;
    public long? Long(string name) => Get(name) is { } s ? long.Parse(s) : null;
    public double? Double(string name) => Get(name) is { } s ? double.Parse(s, System.Globalization.CultureInfo.InvariantCulture) : null;
}
