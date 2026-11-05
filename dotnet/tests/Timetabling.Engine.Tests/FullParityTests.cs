using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text.Json;
using Xunit.Abstractions;

namespace Timetabling.Engine.Tests;

/// <summary>
/// Replays committed Python experiments through Runner.RunOne and requires identical solutions, metrics,
/// evaluation counts, statuses and traces. Run alone with: dotnet test --filter Category=Slow
/// </summary>
[Trait("Category", "Slow")]
public class FullParityTests(ITestOutputHelper output)
{
    /// <summary>All 240 runs of experiments/final (Python: 1,812 s wall time on 18 worker processes).</summary>
    [Fact]
    public void AllFinalRunsMatchPython()
    {
        var batch = StoredBatch.Load("final");
        _ = batch.Prepared;
        var failures = new ConcurrentBag<string>();
        var searchSeconds = new ConcurrentBag<double>();
        var clock = Stopwatch.StartNew();
        Parallel.ForEach(batch.Results, new ParallelOptions { MaxDegreeOfParallelism = Environment.ProcessorCount }, stored =>
        {
            var started = Stopwatch.GetTimestamp();
            foreach (var d in batch.Rerun(stored)) failures.Add($"{StoredBatch.Describe(stored)}: {d}");
            searchSeconds.Add(Stopwatch.GetElapsedTime(started).TotalSeconds);
        });
        clock.Stop();
        var python = batch.Results.Sum(r => r.GetProperty("search_seconds").GetDouble());
        var message = $"240 final runs: C# wall {clock.Elapsed.TotalSeconds:F1} s on {Environment.ProcessorCount} threads " +
                      $"(sum of per-run time {searchSeconds.Sum():F0} s); Python wall 1,812 s on 18 processes (sum of search_seconds {python:F0} s)";
        output.WriteLine(message);
        File.WriteAllText(Path.Combine(AppContext.BaseDirectory, "full-parity-timing.txt"), message + "\n");
        Assert.True(failures.IsEmpty, string.Join("\n", failures.Take(40)));
    }

    /// <summary>Spot checks with other parameters (tuning) and budgets (budget study).</summary>
    public static IEnumerable<object[]> SpotChecks()
    {
        // tuning: a non-default configuration of each method; budget: every budget level of each method.
        foreach (var (configId, seed) in new[] { ("hc-p5", 4), ("sa-a0.95-c0.999", 9), ("ga-17", 2), ("ga-19", 1) })
            yield return ["tuning", configId, seed];
        foreach (var (configId, seed) in new[] { ("b50", 1003), ("b200", 1005), ("b1000", 1010) })
            yield return ["budget", configId, seed];
    }

    [Theory, MemberData(nameof(SpotChecks))]
    public void SpotCheckMatchesPython(string experiment, string configId, int seed)
    {
        var batch = StoredBatch.Load(experiment);
        var runs = batch.Results.Where(r => r.GetProperty("config_id").GetString() == configId && r.GetProperty("seed").GetInt32() == seed).ToArray();
        Assert.NotEmpty(runs);
        var failures = new ConcurrentBag<string>();
        Parallel.ForEach(runs, stored =>
        {
            foreach (var d in batch.Rerun(stored)) failures.Add($"{StoredBatch.Describe(stored)} {JsonSerializer.Serialize(stored.GetProperty("parameters"))}: {d}");
        });
        Assert.True(failures.IsEmpty, string.Join("\n", failures));
        output.WriteLine($"{experiment}/{configId}/seed {seed}: {runs.Length} run(s) match ({string.Join(", ", runs.Select(StoredBatch.Describe))})");
    }
}
