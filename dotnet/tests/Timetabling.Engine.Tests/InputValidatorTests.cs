using System.Text.Json.Nodes;

namespace Timetabling.Engine.Tests;

/// <summary>InputValidator against engine/input_validation.py (expected reports from Fixtures/make_input_reports.py).</summary>
public class InputValidatorTests
{
    static readonly JsonArray Cases = JsonNode.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Fixtures", "input_reports.json")))!.AsArray();

    public static IEnumerable<object[]> CaseNames() => Cases.Select(c => new object[] { (string)c!["name"]! });

    static string Apply(string text, JsonArray edits)
    {
        if (edits.Count == 0) return text;
        var root = JsonNode.Parse(text)!;
        foreach (var edit in edits)
        {
            var path = edit!["path"]!.AsArray();
            var node = root;
            for (var i = 0; i < path.Count - 1; i++) node = Step(node, path[i]!)!;
            var last = path[^1]!;
            if (edit["delete"]?.GetValue<bool>() == true) node.AsObject().Remove((string)last!);
            else if (node is JsonArray a) a[(int)last] = edit["value"]!.DeepClone();
            else node.AsObject()[(string)last!] = edit["value"]?.DeepClone();
        }
        return root.ToJsonString();
    }

    static JsonNode? Step(JsonNode node, JsonNode key) => node is JsonArray a ? a[(int)key] : node[(string)key!];

    [Theory, MemberData(nameof(CaseNames))]
    public void ReportMatchesPython(string name)
    {
        var c = Cases.First(x => (string)x!["name"]! == name)!;
        var text = Apply(Dataset.ReadText(RepoPaths.Of(((string)c["dataset"]!).Split('/'))), c["edits"]!.AsArray());
        var report = InputValidator.ValidateText(text);
        var expected = c["expected"]!;
        Assert.Equal(expected["errors"]!.AsArray().Select(e => (string)e!), report.Errors);
        JsonDiff.Equal(expected, JsonDiff.ToNode(report));
    }

    [Fact]
    public void TypedEntryPointMatchesTextEntryPoint()
    {
        var text = Dataset.ReadText(RepoPaths.Of("data", "fall-cs.json.gz"));
        JsonDiff.Equal(JsonDiff.ToNode(InputValidator.ValidateText(text)), JsonDiff.ToNode(InputValidator.Validate(Dataset.Parse(text))));
    }
}
