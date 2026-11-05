using System.Diagnostics;

namespace Timetabling.Engine;

/// <summary>Budget, time limit, best-so-far and trace accounting (port of lab_core.SearchContext).</summary>
public sealed class SearchContext
{
    public Problem Problem { get; }
    public string RoomMode { get; }
    public ulong Seed { get; }
    public PyRandom Rng { get; }
    public int Budget { get; }
    public int Evaluations { get; private set; }
    public int AttemptedEvaluations { get; private set; }
    public Candidate? Best { get; private set; }
    public Candidate? Initial { get; set; }
    public List<TracePoint> Trace { get; } = [];

    readonly long started, deadline;
    readonly Action<ProgressEvent>? emit;
    readonly CancellationToken cancellation;
    double lastProgress;

    public SearchContext(Problem problem, ulong seed, int budget, double seconds, Action<ProgressEvent>? emit = null,
                         string roomMode = RoomModes.Weekly, CancellationToken cancellation = default)
    {
        if (!RoomModes.IsValid(roomMode)) throw new ArgumentException("room_mode must be one of weekly, fixed");
        Problem = problem;
        RoomMode = roomMode;
        Seed = seed;
        Rng = new PyRandom(seed);
        Budget = budget;
        started = Stopwatch.GetTimestamp();
        deadline = started + (long)(seconds * Stopwatch.Frequency);
        this.emit = emit;
        this.cancellation = cancellation;
    }

    public double Elapsed => Stopwatch.GetElapsedTime(started).TotalSeconds;

    public void Check()
    {
        if (Evaluations >= Budget) throw new SearchStoppedException("evaluation_budget");
        if (cancellation.IsCancellationRequested) throw new SearchStoppedException("cancelled");
        if (Stopwatch.GetTimestamp() >= deadline) throw new SearchStoppedException("time_limit");
    }

    public Candidate Evaluate(Genome genome)
    {
        Check();
        AttemptedEvaluations++;
        var candidate = Problem.Decode(genome, Best is not null ? deadline : null, RoomMode);
        Evaluations++;
        var improved = Best is null || candidate.Objectives < Best.Objectives;
        if (improved) Best = candidate;
        var elapsed = Elapsed;
        if (improved || Evaluations % 5 == 0 || Evaluations == Budget)
        {
            Trace.Add(new TracePoint(Evaluations, elapsed, Best!.Objectives.ToArray(), candidate.Objectives.ToArray()));
            if (emit is not null && (improved || elapsed - lastProgress >= 0.25))
            {
                lastProgress = elapsed;
                emit(new ProgressEvent(Evaluations, Budget, elapsed, Best.Objectives, candidate.Objectives));
            }
        }
        return candidate;
    }
}
