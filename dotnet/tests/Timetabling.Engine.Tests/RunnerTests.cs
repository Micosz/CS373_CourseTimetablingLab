using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;

namespace Timetabling.Engine.Tests;

/// <summary>Runner contract checks that run in seconds; the full 240-run replay is in FullParityTests.</summary>
public class RunnerTests
{
    [Fact]
    public void PrepareMatchesStoredPreparation()
    {
        var batch = StoredBatch.Load("final");
        var meta = JsonDiff.ToNode(batch.Prepared.Meta)!.AsObject();
        var stored = JsonDiff.Parse(batch.Batch.GetProperty("preparation"))!.AsObject();
        foreach (var key in new[] { "summary", "warnings", "dataset_sha256", "energy_weights" })
            JsonDiff.Equal(stored[key], meta[key]);
        Assert.Equal(batch.Batch.GetProperty("dataset_hash").GetString(), batch.Prepared.Meta.DatasetSha256);
        Assert.Equal(Dataset.Sha256(Dataset.ReadText(RepoPaths.Of("data", "fall-cs.json.gz"))), batch.Prepared.Meta.DatasetSha256);
    }

    [Fact]
    public void GreedyRunMatchesPython()
    {
        var batch = StoredBatch.Load("final");
        foreach (var mode in RoomModes.All)
        {
            var stored = batch.Results.First(r => r.GetProperty("algorithm").GetString() == "greedy" && r.GetProperty("room_mode").GetString() == mode);
            Assert.Empty(batch.Rerun(stored));
        }
    }

    /// <summary>A C# result has every key of a stored Python result (run_one keys plus batch bookkeeping), and no others.</summary>
    [Fact]
    public void ResultHasPythonKeys()
    {
        var batch = StoredBatch.Load("final");
        var stored = batch.Results.First(r => r.GetProperty("algorithm").GetString() == "hc");
        var config = new RunConfig(Budget: 3, Seconds: 60, RoomMode: "weekly", Parameters: new MethodParameters());
        var result = JsonDiff.ToNode(Runner.RunOne(batch.Prepared, config, "hc", 7))!.AsObject();
        Assert.Equal(stored.EnumerateObject().Select(p => p.Name).Order(), result.Select(p => p.Key).Order());
        Assert.Equal(stored.GetProperty("validation").EnumerateObject().Select(p => p.Name).Order(), result["validation"]!.AsObject().Select(p => p.Key).Order());
        Assert.Equal(["dotnet", "platform"], result["runtime"]!.AsObject().Select(p => p.Key));
        Assert.Equal("evaluation_budget", (string)result["status"]!);
        Assert.Equal(3, (int)result["evaluations"]!);
        // Typed parameters without ParametersJson: the method's full typed object.
        JsonDiff.Equal(new JsonObject { ["restart_patience"] = 20 }, result["parameters"]);
    }

    [Fact]
    public void ParametersAreRecordedAsGiven()
    {
        var prepared = StoredBatch.Load("final").Prepared;
        var config = RunConfig.FromJson(new JsonObject { ["budget"] = 2, ["parameters"] = new JsonObject { ["ga"] = new JsonObject { ["elites"] = 2 } } });
        Assert.Equal(2, config.Parameters!.Ga.Elites);
        Assert.Equal(12, config.Parameters.Ga.PopulationSize);
        JsonDiff.Equal(new JsonObject { ["elites"] = 2 }, Runner.RunOne(prepared, config, "ga", 1).Parameters);
        JsonDiff.Equal(new JsonObject(), Runner.RunOne(prepared, config, "hc", 1).Parameters);
        JsonDiff.Equal(new JsonObject(), Runner.RunOne(prepared, new RunConfig(Budget: 1), "sa", 1).Parameters);
        // Python int() truncates a float parameter.
        Assert.Equal(7, RunConfig.FromJson(new JsonObject { ["parameters"] = new JsonObject { ["hc"] = new JsonObject { ["restart_patience"] = 7.9 } } }).Parameters!.Hc.RestartPatience);
    }

    public static IEnumerable<object[]> BadConfigs() =>
    [
        ["""{"budget": 0}""", "Evaluation budget must be an integer from 1 to 100000"],
        ["""{"budget": 100.0}""", "Evaluation budget must be an integer from 1 to 100000"],
        ["""{"budget": true}""", "Evaluation budget must be an integer from 1 to 100000"],
        ["""{"seconds": 0.5}""", "Time limit must be 1..3600 seconds per run"],
        ["""{"seconds": "60"}""", "Time limit must be 1..3600 seconds per run"],
        ["""{"room_mode": "nightly"}""", "Room mode must be weekly or fixed"],
        ["""{"room_mode": null}""", "Room mode must be weekly or fixed"],
        ["""{"parameters": {"hc": {"restart_patience": 0}}}""", "HC restart patience must be 1..10000"],
        ["""{"parameters": {"sa": {"cooling_rate": 1}}}""", "SA acceptance and cooling rate must be strictly between 0 and 1"],
        ["""{"parameters": {"ga": {"population_size": 3}}}""", "GA requires population 4..100 and 1 <= elites < population"],
        ["""{"parameters": {"ga": {"elites": 12}}}""", "GA requires population 4..100 and 1 <= elites < population"],
        ["""{"parameters": {"ga": {"tournament_size": 13}}}""", "GA tournament size must be 2..population size"],
        ["""{"parameters": {"ga": {"mutation_rate": 1.5}}}""", "GA probabilities must be in [0,1]"],
    ];

    [Theory, MemberData(nameof(BadConfigs))]
    public void ConfigurationErrorsUsePythonMessages(string json, string message)
    {
        var error = Assert.Throws<ArgumentException>(() => Runner.CheckConfiguration(RunConfig.FromJson(JsonNode.Parse(json)!.AsObject())));
        Assert.Equal(message, error.Message);
    }

    [Fact]
    public void RejectsUnknownMethodAndSeed()
    {
        var prepared = StoredBatch.Load("final").Prepared;
        Assert.Equal("Unknown algorithm: custom", Assert.Throws<ArgumentException>(() => Runner.RunOne(prepared, new RunConfig(), "custom", 1)).Message);
        Assert.Equal("Seed must be an integer in [0, 2^32-1]",
                     Assert.Throws<ArgumentException>(() => Runner.RunOne(prepared, new RunConfig(), "greedy", 1UL << 32)).Message);
    }

    [Fact]
    public void PrepareRejectsInvalidAndOversizedDatasets()
    {
        var text = Dataset.ReadText(RepoPaths.Of("data", "fall-cs.json.gz"));
        var broken = JsonNode.Parse(text)!.AsObject();
        broken["schema_version"] = "2.0";
        Assert.Equal("Invalid dataset: Unsupported schema version", Assert.Throws<ArgumentException>(() => Runner.Prepare(broken.ToJsonString())).Message);
        var huge = JsonNode.Parse(text)!.AsObject();
        huge["recurring_sessions"] = new JsonArray(Enumerable.Range(0, 6001).Select(_ => (JsonNode)new JsonObject()).ToArray());
        Assert.Equal("Dataset exceeds the browser workbench size limit", Assert.Throws<ArgumentException>(() => Runner.Prepare(huge.ToJsonString())).Message);
    }

    static string Normalized(string path) => File.ReadAllText(path).Replace("\r\n", "\n").Replace('\r', '\n');

    [Fact]
    public void SourceHashesCoverTheEngineSources()
    {
        var dir = RepoPaths.Of("dotnet", "src", "Timetabling.Engine");
        var files = Directory.GetFiles(dir, "*.cs").Select(Path.GetFileName).Order(StringComparer.Ordinal).ToArray();
        Assert.Equal(files, Runner.EngineSources.Keys);
        foreach (var name in files) Assert.Equal(Normalized(Path.Combine(dir, name!)), Runner.EngineSources[name!]);
        var algorithms = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(Normalized(Path.Combine(dir, "Algorithms.cs"))))).ToLowerInvariant();
        Assert.Equal(algorithms, Runner.AlgorithmsSha256);
        var prepared = StoredBatch.Load("final").Prepared;
        Assert.Equal(algorithms, Runner.RunOne(prepared, new RunConfig(Budget: 1), "greedy", 1).CodeSha256);
        Assert.Matches("^[0-9a-f]{64}$", Runner.EngineSha256);
    }
}
