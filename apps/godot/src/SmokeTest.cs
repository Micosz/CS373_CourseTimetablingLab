using System;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using Timetabling.Engine;

namespace RoomMap;

/// <summary>
/// Headless check (godot --headless --path apps/godot -- --smoke): loads the dataset and experiments/final, decodes
/// Greedy in both room modes and compares the totals with the stored results; recomputes every stored run's totals
/// from its raw schedule; runs a short live search through SearchContext and checks it against the stored trace.
/// </summary>
public static class SmokeTest
{
    public static int Run(string? root, Action<string> print)
    {
        var failures = 0;
        void Check(bool ok, string what)
        {
            print((ok ? "PASS " : "FAIL ") + what);
            if (!ok) failures++;
        }
        try
        {
            var watch = Stopwatch.StartNew();
            Check(root is not null, $"repository found: {root}");
            var datasetPath = RepoLocator.DefaultDataset(root);
            var finalPath = RepoLocator.FinalExperiment(root);
            if (datasetPath is null || finalPath is null) { Check(false, "data/fall-cs.json.gz and experiments/final/experiment.json.gz exist"); return 1; }

            var ds = LoadedDataset.Load(datasetPath);
            var idx = ds.Index;
            print($"dataset {ds.Data.DatasetId}: {ds.Data.Classes.Count} classes, {ds.Data.RecurringSessions.Count} sessions, " +
                  $"{idx.TotalWeekly} weekly sessions, {idx.Rooms.Length} schedulable rooms ({idx.LabCount} Labs), weeks {idx.Weeks[0]}-{idx.Weeks[^1]} ({watch.Elapsed.TotalSeconds:0.0}s)");
            Check(ds.Data.Classes.Count == 174 && idx.TotalWeekly == 3345, "dataset has 174 classes and 3,345 weekly sessions");

            var exp = (ExperimentFile)DataFileLoader.Load(finalPath);
            print($"experiment '{exp.Name}': {exp.Runs.Count} runs, methods {string.Join(",", exp.Methods)}, modes {string.Join(",", exp.Modes)}, seeds {exp.Seeds.Count()} ({watch.Elapsed.TotalSeconds:0.0}s)");
            Check(exp.DatasetText is not null && Dataset.Sha256(exp.DatasetText) == idx.Sha256, "experiment dataset_text is the loaded dataset");

            foreach (var mode in RoomModes.All)
            {
                var decoded = ds.Problem.Decode(ds.Problem.InitialGenome(), null, mode);
                var o = decoded.Objectives;
                var schedule = new Schedule(idx, decoded.Solution, mode, "greedy", 0, "smoke");
                print($"greedy {mode}: decoded unassigned={o.Unassigned} unnecessary_lab_minutes={o.LabMinutes} ({o.LabMinutes / 60.0:0.#} h) room_changes={o.RoomChanges}");
                Check(schedule.Unassigned == o.Unassigned && schedule.UnnecessaryLabMinutes == o.LabMinutes && schedule.RoomChanges == o.RoomChanges,
                    $"greedy {mode}: app totals equal engine objectives");
                var stored = exp.Runs.Where(r => r.Algorithm == "greedy" && r.RoomMode == mode).ToList();
                var same = stored.Count(r => r.Metrics == new StoredMetrics(o.Unassigned, o.LabMinutes, o.RoomChanges));
                Check(stored.Count > 0 && same == stored.Count, $"greedy {mode}: matches experiments/final in {same}/{stored.Count} seeds");
            }
            var weeklyGreedy = exp.Find(RoomModes.Weekly, "greedy", exp.Seeds.First());
            Check(weeklyGreedy?.Metrics?.Unassigned == 20, $"weekly greedy stored unassigned = {weeklyGreedy?.Metrics?.Unassigned} (expected 20)");

            var mismatched = exp.Runs.Where(r =>
            {
                var s = new Schedule(idx, r.Solution, r.RoomMode, r.Algorithm, r.Seed, "");
                return r.Metrics != new StoredMetrics(s.Unassigned, s.UnnecessaryLabMinutes, s.RoomChanges);
            }).Select(r => r.Key).ToList();
            Check(mismatched.Count == 0, $"recomputed totals equal stored metrics for {exp.Runs.Count - mismatched.Count}/{exp.Runs.Count} runs {string.Join(" ", mismatched.Take(5))}");

            var byMode = RoomModes.All.ToDictionary(m => m, m => exp.Runs.Where(r => r.RoomMode == m).Average(r => r.Metrics!.UnnecessaryLabMinutes / 60.0));
            print($"mean unnecessary Lab hours over all runs: fixed {byMode["fixed"]:0.0} h, weekly {byMode["weekly"]:0.0} h (difference {byMode["fixed"] - byMode["weekly"]:0.0} h)");

            // Live path: the first evaluations of HC seed 1001 must reproduce the stored trace.
            var stored1001 = exp.Find(RoomModes.Weekly, "hc", 1001);
            if (stored1001 is not null)
            {
                const int budget = 10; // a multiple of the 5-evaluation trace cadence, so both traces have a point here
                var events = 0;
                var context = new SearchContext(ds.Problem, 1001, budget, 3600, _ => events++, RoomModes.Weekly);
                string reason = "completed";
                try
                {
                    context.Initial = context.Evaluate(ds.Problem.InitialGenome());
                    Algorithms.Run("hc", ds.Problem, context, exp.Parameters ?? new MethodParameters());
                }
                catch (SearchStoppedException stop) { reason = stop.Reason; }
                string Fmt(TracePoint p) => $"{p.Evaluations}:{string.Join(",", p.Objectives)}:{string.Join(",", p.CurrentObjectives)}";
                var expected = string.Join(" ", stored1001.Trace.Where(p => p.Evaluations <= budget).Select(Fmt));
                var actual = string.Join(" ", context.Trace.Select(Fmt));
                Check(reason == "evaluation_budget" && actual == expected, $"live HC weekly seed 1001, {budget} evals: trace equals stored ({actual})");
                Check(events > 0, $"progress callback fired {events} times");
            }

            // Cancellation through the CancellationToken stops a search between evaluations.
            using (var cts = new CancellationTokenSource())
            {
                var context = new SearchContext(ds.Problem, 7, 1000, 3600, e => { if (e.Evaluations >= 2) cts.Cancel(); }, RoomModes.Fixed, cts.Token);
                string reason = "completed";
                try
                {
                    context.Initial = context.Evaluate(ds.Problem.InitialGenome());
                    Algorithms.Run("sa", ds.Problem, context, new MethodParameters());
                }
                catch (SearchStoppedException stop) { reason = stop.Reason; }
                Check(reason == "cancelled" && context.Evaluations < 1000, $"cancel stops the search: {reason} after {context.Evaluations} evals");
            }
            print($"smoke finished in {watch.Elapsed.TotalSeconds:0.0}s with {failures} failure(s)");
        }
        catch (Exception ex)
        {
            print("FAIL exception: " + ex);
            failures++;
        }
        return failures == 0 ? 0 : 1;
    }
}
