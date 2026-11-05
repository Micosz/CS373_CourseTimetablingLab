using System.IO.Compression;
using System.Text.Json;

namespace Timetabling.Engine.Tests;

/// <summary>Quick check of each search method against one stored Python run (seed 1001, weekly).</summary>
public class AlgorithmSmokeTests
{
    [Theory]
    [InlineData("hc")]
    [InlineData("sa")]
    [InlineData("ga")]
    public void TraceMatchesPython(string method)
    {
        using var gz = new GZipStream(File.OpenRead(RepoPaths.Of("experiments", "final", "experiment.json.gz")), CompressionMode.Decompress);
        using var doc = JsonDocument.Parse(gz);
        var batch = doc.RootElement.GetProperty("batch");
        var stored = batch.GetProperty("results").EnumerateArray().First(r =>
            r.GetProperty("algorithm").GetString() == method && r.GetProperty("room_mode").GetString() == "weekly" && r.GetProperty("seed").GetInt32() == 1001);
        var parameters = JsonSerializer.Deserialize<MethodParameters>(batch.GetProperty("config").GetProperty("parameters").GetRawText(), Dataset.Json)!;
        var problem = RepoPaths.MainProblem;
        var context = new SearchContext(problem, 1001, stored.GetProperty("budget").GetInt32(), 3600, null, "weekly");
        try
        {
            context.Initial = context.Evaluate(problem.InitialGenome());
            Algorithms.Run(method, problem, context, parameters);
        }
        catch (SearchStoppedException stop) { Assert.Equal("evaluation_budget", stop.Reason); }
        string Trace(IEnumerable<(int, long[], long[])> t) => string.Join("\n", t.Select(x => $"{x.Item1} {string.Join(",", x.Item2)} {string.Join(",", x.Item3)}"));
        var expected = stored.GetProperty("trace").EnumerateArray().Select(p => (p.GetProperty("evaluations").GetInt32(),
            p.GetProperty("objectives").EnumerateArray().Select(x => x.GetInt64()).ToArray(),
            p.GetProperty("current_objectives").EnumerateArray().Select(x => x.GetInt64()).ToArray()));
        Assert.Equal(Trace(expected), Trace(context.Trace.Select(p => (p.Evaluations, p.Objectives, p.CurrentObjectives))));
    }
}
