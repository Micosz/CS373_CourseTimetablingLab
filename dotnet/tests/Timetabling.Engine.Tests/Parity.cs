using System.Collections.Concurrent;
using System.IO.Compression;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Timetabling.Engine.Tests;

/// <summary>JSON comparison as Python sees it: object key order is ignored and numbers compare by value (1925.0 == 1925).</summary>
public static class JsonDiff
{
    public static JsonNode? ToNode<T>(T value) => JsonSerializer.SerializeToNode(value, Dataset.Json);

    public static JsonNode? Parse(JsonElement element) => JsonNode.Parse(element.GetRawText());

    /// <summary>The first difference as "path: expected X, got Y", or null when equal.</summary>
    public static string? First(JsonNode? expected, JsonNode? actual, string path = "$")
    {
        if (expected is null || actual is null)
            return expected is null && actual is null ? null : $"{path}: expected {Show(expected)}, got {Show(actual)}";
        switch (expected)
        {
            case JsonObject e when actual is JsonObject a:
                var missing = e.Select(p => p.Key).Where(k => !a.ContainsKey(k)).ToList();
                var extra = a.Select(p => p.Key).Where(k => !e.ContainsKey(k)).ToList();
                if (missing.Count > 0 || extra.Count > 0)
                    return $"{path}: missing keys [{string.Join(", ", missing)}], extra keys [{string.Join(", ", extra)}]";
                foreach (var (key, value) in e)
                    if (First(value, a[key], $"{path}.{key}") is { } d) return d;
                return null;
            case JsonArray e when actual is JsonArray a:
                if (e.Count != a.Count) return $"{path}: expected {e.Count} items, got {a.Count}";
                for (var i = 0; i < e.Count; i++)
                    if (First(e[i], a[i], $"{path}[{i}]") is { } d) return d;
                return null;
            case JsonValue e when actual is JsonValue a:
                var (ek, ak) = (e.GetValueKind(), a.GetValueKind());
                if (ek == JsonValueKind.Number && ak == JsonValueKind.Number)
                    return JsonSerializer.SerializeToElement(e).GetDouble() == JsonSerializer.SerializeToElement(a).GetDouble()
                        ? null : $"{path}: expected {e.ToJsonString()}, got {a.ToJsonString()}";
                return ek == ak && e.ToJsonString() == a.ToJsonString() ? null : $"{path}: expected {Show(e)}, got {Show(a)}";
            default:
                return $"{path}: expected {Show(expected)}, got {Show(actual)}";
        }
    }

    static string Show(JsonNode? node)
    {
        var text = node?.ToJsonString() ?? "null";
        return text.Length > 160 ? text[..160] + "..." : text;
    }

    public static void Equal(JsonNode? expected, JsonNode? actual)
    {
        if (First(expected, actual) is { } difference) Assert.Fail(difference);
    }
}

/// <summary>A committed experiment file (experiments/&lt;name&gt;/experiment.json.gz), loaded once per test run.</summary>
public sealed class StoredBatch
{
    static readonly ConcurrentDictionary<string, Lazy<StoredBatch>> cache = new();

    public JsonElement Batch { get; }
    public string DatasetText { get; }
    public JsonElement[] Results { get; }
    readonly Lazy<Prepared> prepared;

    StoredBatch(string name)
    {
        using var gz = new GZipStream(File.OpenRead(RepoPaths.Of("experiments", name, "experiment.json.gz")), CompressionMode.Decompress);
        var root = JsonDocument.Parse(gz).RootElement;
        Batch = root.GetProperty("batch");
        DatasetText = root.GetProperty("dataset_text").GetString()!;
        Results = Batch.GetProperty("results").EnumerateArray().ToArray();
        prepared = new(() => Runner.Prepare(DatasetText));
    }

    public static StoredBatch Load(string name) => cache.GetOrAdd(name, n => new Lazy<StoredBatch>(() => new StoredBatch(n))).Value;

    public Prepared Prepared => prepared.Value;

    public static string Describe(JsonElement r) =>
        $"{r.GetProperty("algorithm").GetString()}/{r.GetProperty("room_mode").GetString()}/seed {r.GetProperty("seed")}/budget {r.GetProperty("budget")}";

    /// <summary>The per-run config the Python batch passed to run_one, rebuilt from the stored result.</summary>
    public static RunConfig ConfigOf(JsonElement r) => RunConfig.FromJson(new JsonObject
    {
        ["budget"] = r.GetProperty("budget").GetInt32(),
        ["seconds"] = JsonNode.Parse(r.GetProperty("time_limit_seconds").GetRawText()),
        ["room_mode"] = r.GetProperty("room_mode").GetString(),
        ["parameters"] = new JsonObject { [r.GetProperty("algorithm").GetString()!] = JsonDiff.Parse(r.GetProperty("parameters")) },
    });

    /// <summary>Runs one stored result again through the C# runner and lists every field that differs.</summary>
    public List<string> Rerun(JsonElement stored)
    {
        var result = Runner.RunOne(Prepared, ConfigOf(stored), stored.GetProperty("algorithm").GetString()!, stored.GetProperty("seed").GetUInt64());
        var differences = new List<string>();
        var actual = JsonDiff.ToNode(result)!.AsObject();
        foreach (var key in new[] { "solution", "metrics", "evaluations", "attempted_evaluations", "status", "valid", "parameters",
                                    "budget", "dataset_id", "dataset_sha256", "original_source_sha256", "energy_weights" })
            // The tuning and budget exports strip solutions (stored as null); metrics and trace still pin those runs.
            if (!(key == "solution" && stored.GetProperty(key).ValueKind == JsonValueKind.Null)
                && JsonDiff.First(JsonDiff.Parse(stored.GetProperty(key)), actual[key], key) is { } d)
                differences.Add(d);
        if (JsonDiff.First(JsonDiff.Parse(stored.GetProperty("validation").GetProperty("violation_count")), result.Validation!.ViolationCount, "validation.violation_count") is { } v)
            differences.Add(v);
        JsonArray Trace(IEnumerable<JsonNode?> points) => new(points.Select(p => (JsonNode)new JsonObject
        {
            ["evaluations"] = p!["evaluations"]!.DeepClone(), ["objectives"] = p["objectives"]!.DeepClone(),
            ["current_objectives"] = p["current_objectives"]!.DeepClone(),
        }).ToArray());
        if (JsonDiff.First(Trace(JsonDiff.Parse(stored.GetProperty("trace"))!.AsArray()), Trace(actual["trace"]!.AsArray()), "trace") is { } t)
            differences.Add(t);
        return differences;
    }
}
