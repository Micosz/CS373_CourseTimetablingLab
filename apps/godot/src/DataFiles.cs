using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text.Json;
using Timetabling.Engine;

namespace RoomMap;

/// <summary>Metrics as stored by engine/solution_validator.py in a result record.</summary>
public sealed record StoredMetrics(long Unassigned, long UnnecessaryLabMinutes, long RoomChanges);

/// <summary>One result record of an experiment file (batch.results[]).</summary>
public sealed record RunRecord(
    string Algorithm, string RoomMode, ulong Seed, string Status, int Evaluations, int Budget,
    StoredMetrics? Metrics, Solution Solution, List<TracePoint> Trace)
{
    public string Key => $"{RoomMode}/{Algorithm}/{Seed}";
}

/// <summary>An experiment export (experiments/**/experiment.json[.gz]) or a bare result list.</summary>
public sealed class ExperimentFile
{
    public string Path { get; init; } = "";
    public string Name { get; init; } = "";
    public string? DatasetText { get; init; }
    public MethodParameters? Parameters { get; init; }
    public List<RunRecord> Runs { get; init; } = [];

    public IEnumerable<string> Methods => Order(Runs.Select(r => r.Algorithm).Distinct(), Algorithms.Names);
    public IEnumerable<string> Modes => Order(Runs.Select(r => r.RoomMode).Distinct(), RoomModes.All);
    public IEnumerable<ulong> Seeds => Runs.Select(r => r.Seed).Distinct().OrderBy(s => s);

    public RunRecord? Find(string mode, string method, ulong seed) =>
        Runs.FirstOrDefault(r => r.RoomMode == mode && r.Algorithm == method && r.Seed == seed);

    static IEnumerable<string> Order(IEnumerable<string> values, string[] preferred) =>
        values.OrderBy(v => Array.IndexOf(preferred, v) is var i && i < 0 ? int.MaxValue : i).ThenBy(v => v, StringComparer.Ordinal);

    public static Stream Open(string path)
    {
        Stream stream = File.OpenRead(path);
        if (path.EndsWith(".gz", StringComparison.OrdinalIgnoreCase))
            stream = new GZipStream(stream, CompressionMode.Decompress);
        return new BufferedStream(stream, 1 << 16);
    }

    /// <summary>True when the file's root object looks like a dataset (rooms + recurring_sessions).</summary>
    public static bool LooksLikeDataset(JsonElement root) =>
        root.ValueKind == JsonValueKind.Object && root.TryGetProperty("rooms", out _) && root.TryGetProperty("recurring_sessions", out _);

    public static ExperimentFile FromJson(string path, JsonElement root)
    {
        JsonElement results;
        JsonElement container = root;
        if (root.ValueKind == JsonValueKind.Array) results = root;
        else if (root.TryGetProperty("batch", out var batch) && batch.TryGetProperty("results", out results)) container = batch;
        else if (root.TryGetProperty("results", out results)) { }
        else if (root.TryGetProperty("solution", out _)) results = JsonDocument.Parse("[" + root.GetRawText() + "]").RootElement;
        else throw new InvalidDataException("Not an experiment file: no batch.results[]");

        MethodParameters? parameters = null;
        if (container.ValueKind == JsonValueKind.Object && container.TryGetProperty("config", out var config)
            && config.TryGetProperty("parameters", out var p) && p.ValueKind == JsonValueKind.Object)
            parameters = JsonSerializer.Deserialize<MethodParameters>(p.GetRawText(), Dataset.Json);

        var runs = new List<RunRecord>();
        foreach (var r in results.EnumerateArray())
        {
            if (!r.TryGetProperty("solution", out var s) || s.ValueKind != JsonValueKind.Object) continue;
            var mode = Str(r, "room_mode") ?? RoomModes.Weekly;
            StoredMetrics? metrics = null;
            if (r.TryGetProperty("metrics", out var m) && m.ValueKind == JsonValueKind.Object)
                metrics = new StoredMetrics(Long(m, "unassigned_weekly_sessions"), Long(m, "unnecessary_lab_minutes"), Long(m, "room_changes"));
            var trace = new List<TracePoint>();
            if (r.TryGetProperty("trace", out var t) && t.ValueKind == JsonValueKind.Array)
                foreach (var point in t.EnumerateArray())
                    trace.Add(new TracePoint(point.GetProperty("evaluations").GetInt32(), point.GetProperty("seconds").GetDouble(),
                        Longs(point, "objectives"), Longs(point, "current_objectives")));
            runs.Add(new RunRecord(Str(r, "algorithm") ?? "?", mode, r.TryGetProperty("seed", out var seed) ? seed.GetUInt64() : 0,
                Str(r, "status") ?? "", (int)Long(r, "evaluations"), (int)Long(r, "budget"), metrics, ParseSolution(s, mode), trace));
        }
        var name = container.ValueKind == JsonValueKind.Object ? Str(container, "name") : null;
        return new ExperimentFile
        {
            Path = path,
            Name = string.IsNullOrWhiteSpace(name) ? System.IO.Path.GetFileName(path) : name!,
            DatasetText = root.ValueKind == JsonValueKind.Object ? Str(root, "dataset_text") : null,
            Parameters = parameters,
            Runs = runs,
        };
    }

    public static Solution ParseSolution(JsonElement s, string mode)
    {
        var options = new Dictionary<string, string?>();
        if (s.TryGetProperty("class_time_options", out var o) && o.ValueKind == JsonValueKind.Object)
            foreach (var p in o.EnumerateObject())
                options[p.Name] = p.Value.ValueKind == JsonValueKind.String ? p.Value.GetString() : null;
        var assignments = new List<Assignment>();
        if (s.TryGetProperty("weekly_room_assignments", out var a) && a.ValueKind == JsonValueKind.Array)
            foreach (var x in a.EnumerateArray())
                assignments.Add(new Assignment(x.GetProperty("session_id").GetString()!, x.GetProperty("week").GetInt32(), x.GetProperty("room_id").GetString()!));
        return new Solution { DatasetId = Str(s, "dataset_id") ?? "", RoomMode = Str(s, "room_mode") ?? mode, ClassTimeOptions = options, WeeklyRoomAssignments = assignments };
    }

    static string? Str(JsonElement e, string name) =>
        e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

    static long Long(JsonElement e, string name) =>
        e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetInt64() : 0;

    static long[] Longs(JsonElement e, string name) =>
        e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Array ? v.EnumerateArray().Select(x => x.GetInt64()).ToArray() : [];
}

/// <summary>A loaded dataset with its compiled engine problem.</summary>
public sealed record LoadedDataset(string Path, string Text, DatasetIndex Index, Problem Problem)
{
    public Dataset Data => Index.Data;

    public static LoadedDataset FromText(string path, string text)
    {
        var data = Dataset.Parse(text);
        return new LoadedDataset(path, text, new DatasetIndex(data, Dataset.Sha256(text)), new Problem(data));
    }

    public static LoadedDataset Load(string path) => FromText(path, Dataset.ReadText(path));
}

/// <summary>Finds the repository (the folder that has data/provenance.json) from the project or the executable.</summary>
public static class RepoLocator
{
    public static string? Root(params string[] starts)
    {
        var env = System.Environment.GetEnvironmentVariable("TIMETABLING_REPO");
        foreach (var start in (env is null ? starts : starts.Prepend(env)).Where(s => !string.IsNullOrEmpty(s)))
            for (var dir = new DirectoryInfo(start); dir is not null; dir = dir.Parent)
                if (File.Exists(System.IO.Path.Combine(dir.FullName, "data", "provenance.json"))) return dir.FullName;
        return null;
    }

    public static string? DefaultDataset(string? root) =>
        root is not null && File.Exists(System.IO.Path.Combine(root, "data", "fall-cs.json.gz")) ? System.IO.Path.Combine(root, "data", "fall-cs.json.gz") : null;

    public static string? FinalExperiment(string? root) =>
        root is not null && File.Exists(System.IO.Path.Combine(root, "experiments", "final", "experiment.json.gz"))
            ? System.IO.Path.Combine(root, "experiments", "final", "experiment.json.gz") : null;
}

/// <summary>Opens a .json/.json.gz file that may be either a dataset or an experiment.</summary>
public static class DataFileLoader
{
    public static object Load(string path)
    {
        using (var stream = ExperimentFile.Open(path))
        using (var doc = JsonDocument.Parse(stream, new JsonDocumentOptions { MaxDepth = 256 }))
        {
            if (!ExperimentFile.LooksLikeDataset(doc.RootElement)) return ExperimentFile.FromJson(path, doc.RootElement);
        }
        return LoadedDataset.Load(path);
    }
}
