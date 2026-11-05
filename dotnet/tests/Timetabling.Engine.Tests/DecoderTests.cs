using System.IO.Compression;
using System.Text.Json;

namespace Timetabling.Engine.Tests;

public class DecoderTests
{
    /// <summary>The initial (Greedy) genome must decode to exactly the schedule stored by the Python engine.</summary>
    [Theory]
    [InlineData("weekly")]
    [InlineData("fixed")]
    public void GreedyScheduleMatchesPythonFinalExperiment(string mode)
    {
        using var gz = new GZipStream(File.OpenRead(RepoPaths.Of("experiments", "final", "experiment.json.gz")), CompressionMode.Decompress);
        using var doc = JsonDocument.Parse(gz);
        var stored = doc.RootElement.GetProperty("batch").GetProperty("results").EnumerateArray()
            .First(r => r.GetProperty("algorithm").GetString() == "greedy" && r.GetProperty("room_mode").GetString() == mode);
        var problem = RepoPaths.MainProblem;
        var candidate = problem.Decode(problem.InitialGenome(), null, mode);
        var expected = stored.GetProperty("trace")[0].GetProperty("objectives").EnumerateArray().Select(x => x.GetInt64());
        Assert.Equal(expected, candidate.Objectives.ToArray());
        var solution = stored.GetProperty("solution");
        var rows = solution.GetProperty("weekly_room_assignments").EnumerateArray()
            .Select(r => new Assignment(r.GetProperty("session_id").GetString()!, r.GetProperty("week").GetInt32(), r.GetProperty("room_id").GetString()!));
        Assert.Equal(rows, candidate.Solution.WeeklyRoomAssignments);
        foreach (var p in solution.GetProperty("class_time_options").EnumerateObject())
            Assert.Equal(p.Value.ValueKind == JsonValueKind.Null ? null : p.Value.GetString(), candidate.Solution.ClassTimeOptions[p.Name]);
    }
}
