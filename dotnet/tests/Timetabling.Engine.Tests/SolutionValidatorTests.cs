using System.Text.Json;
using System.Text.Json.Nodes;

namespace Timetabling.Engine.Tests;

/// <summary>SolutionValidator.Audit against engine/solution_validator.py.</summary>
public class SolutionValidatorTests
{
    static readonly JsonObject Cases = JsonNode.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Fixtures", "validator_cases.json")))!.AsObject();

    public static IEnumerable<object[]> CaseNames() => Cases["cases"]!.AsArray().Select(c => new object[] { (string)c!["name"]! });

    static Solution Deserialize(JsonNode node) => node.Deserialize<Solution>(Dataset.Json)!;

    [Fact]
    public void AllStoredFinalSolutionsAuditLikePython()
    {
        var batch = StoredBatch.Load("final");
        Assert.Equal(240, batch.Results.Length);
        var data = batch.Prepared.Problem.Data;
        var failures = new List<string>();
        foreach (var r in batch.Results)
        {
            var audit = SolutionValidator.Audit(data, Deserialize(JsonDiff.Parse(r.GetProperty("solution"))!), r.GetProperty("room_mode").GetString()!);
            if (JsonDiff.First(JsonDiff.Parse(r.GetProperty("validation")), JsonDiff.ToNode(audit)) is { } d)
                failures.Add($"{StoredBatch.Describe(r)}: {d}");
        }
        Assert.True(failures.Count == 0, string.Join("\n", failures));
    }

    /// <summary>The hand-made invalid solutions of Fixtures/make_validator_cases.py: same violations, counts and metrics.</summary>
    [Theory, MemberData(nameof(CaseNames))]
    public void InvalidSolutionMatchesPython(string name)
    {
        var batch = StoredBatch.Load("final");
        var c = Cases["cases"]!.AsArray().First(x => (string)x!["name"]! == name)!;
        var stored = batch.Results.First(r => r.GetProperty("algorithm").GetString() == "greedy" && r.GetProperty("seed").GetInt32() == 1001
                                             && r.GetProperty("room_mode").GetString() == (string)c["base"]!);
        var solution = JsonDiff.Parse(stored.GetProperty("solution"))!.AsObject();
        var rows = solution["weekly_room_assignments"]!.AsArray();
        if (c["set_all_rooms"] is { } room)
            foreach (var row in rows) row!["room_id"] = room.DeepClone();
        foreach (var edit in c["set_rows"]?.AsArray() ?? [])
            rows[(int)edit![0]!] = edit[1]!.DeepClone();
        foreach (var row in c["append_rows"]?.AsArray() ?? []) rows.Add(row!.DeepClone());
        var options = solution["class_time_options"]!.AsObject();
        foreach (var (key, value) in c["set_options"]?.AsObject() ?? []) options[key] = value?.DeepClone();
        foreach (var (key, value) in c["set_fields"]?.AsObject() ?? []) solution[key] = value?.DeepClone();

        var audit = SolutionValidator.Audit(RepoPaths.MainDataset, Deserialize(solution), (string)c["audit_mode"]!);
        var expected = c["expected"]!;
        Assert.Equal((int)expected["violation_count"]!, audit.ViolationCount);
        JsonDiff.Equal(expected, JsonDiff.ToNode(audit));
    }

    /// <summary>
    /// Python's early return for a non-object solution has no violations_truncated key; the C# record always
    /// carries it (false). Every other key and value is the same.
    /// </summary>
    [Fact]
    public void NullSolutionIsASchemaViolation()
    {
        var expected = Cases["null_solution"]!.AsObject();
        var actual = JsonDiff.ToNode(SolutionValidator.Audit(RepoPaths.MainDataset, null))!.AsObject();
        Assert.False(actual["violations_truncated"]!.GetValue<bool>());
        actual.Remove("violations_truncated");
        JsonDiff.Equal(expected, actual);
    }

    [Fact]
    public void ReprQuotesLikePython()
    {
        Assert.Equal("'weekly'", SolutionValidator.PyRepr("weekly"));
        Assert.Equal("\"it's\"", SolutionValidator.PyRepr("it's"));
        Assert.Equal("'a\\'b\"c'", SolutionValidator.PyRepr("a'b\"c"));
        Assert.Equal("'tab\\there'", SolutionValidator.PyRepr("tab\there"));
    }
}
