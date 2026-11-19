using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text.Json;
using Xunit.Abstractions;

namespace Timetabling.Engine.Tests;

/// <summary>
/// Replays committed experiments through Runner.RunOne and requires identical solutions, metrics,
/// evaluation counts, statuses and traces. The committed runs were produced by this C# engine, so this checks
/// that the results reproduce on every machine and OS in CI; agreement with the Python engine is covered by
/// the fast tests (CPython RNG vectors, validator cases, input reports). Run alone with: dotnet test --filter Category=Slow
/// </summary>
[Trait("Category", "Slow")]
public class FullParityTests(ITestOutputHelper output)
{
    /// <summary>All 240 runs of experiments/final.</summary>
    [Fact]
    public void AllFinalRunsReproduce()
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
        var stored = batch.Results.Sum(r => r.GetProperty("search_seconds").GetDouble());
        var message = $"{batch.Results.Length} final runs: wall {clock.Elapsed.TotalSeconds:F1} s on {Environment.ProcessorCount} threads " +
                      $"(sum of per-run time {searchSeconds.Sum():F0} s; stored sum of search_seconds {stored:F0} s)";
        output.WriteLine(message);
        File.WriteAllText(Path.Combine(AppContext.BaseDirectory, "full-parity-timing.txt"), message + "\n");
        Assert.True(failures.IsEmpty, string.Join("\n", failures.Take(40)));
    }

    /// <summary>Spot checks with other parameters (tuning) and other datasets (Lab-weeks study).</summary>
    public static IEnumerable<object[]> SpotChecks()
    {
        // tuning: a non-default configuration of each method; lab-weeks: a light, a tight and a full-Lab level.
        foreach (var (configId, seed) in new[] { ("hc-p5", 4), ("sa-a0.95-c0.9", 9), ("ga-17", 2), ("ga-19", 1) })
            yield return [$"tuning/configs/{configId}", "main", seed];
        foreach (var (level, seed) in new[] { ("w01", 1003), ("w08", 1005), ("w15", 1010) })
            yield return [$"lab-weeks/{level}", "main", seed];
    }

    [Theory, MemberData(nameof(SpotChecks))]
    public void SpotCheckReproduces(string experiment, string configId, int seed)
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
