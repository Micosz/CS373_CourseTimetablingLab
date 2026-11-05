namespace Timetabling.Engine;

/// <summary>Method parameters; defaults match engine/algorithms.py.</summary>
public sealed record HcParameters(int RestartPatience = 20);
public sealed record SaParameters(double InitialAcceptance = 0.8, double CoolingRate = 0.97);
public sealed record GaParameters(int PopulationSize = 12, int TournamentSize = 3, double MutationRate = 0.3,
                                  double CrossoverRate = 0.9, int Elites = 1);

public sealed record MethodParameters
{
    public HcParameters Hc { get; init; } = new();
    public SaParameters Sa { get; init; } = new();
    public GaParameters Ga { get; init; } = new();
}

/// <summary>The four methods on the shared genome and decoder (port of engine/algorithms.py).</summary>
public static class Algorithms
{
    public static readonly string[] Names = ["greedy", "hc", "sa", "ga"];

    public static Candidate? Run(string method, Problem problem, SearchContext context, MethodParameters parameters) =>
        method switch
        {
            "greedy" => context.Initial,
            "hc" => HillClimbing(problem, context, parameters.Hc),
            "sa" => SimulatedAnnealing(problem, context, parameters.Sa),
            "ga" => GeneticAlgorithm(problem, context, parameters.Ga),
            _ => throw new ArgumentException("Unknown algorithm: " + method),
        };

    public static Candidate HillClimbing(Problem problem, SearchContext context, HcParameters p)
    {
        var current = context.Initial!;
        var idle = 0;
        while (true)
        {
            context.Check();
            if (idle >= p.RestartPatience)
            {
                current = context.Evaluate(problem.RandomGenome(context.Rng));
                idle = 0;
            }
            else
            {
                var proposal = context.Evaluate(problem.Mutate(current.Genome, context.Rng));
                if (proposal.Objectives < current.Objectives) { current = proposal; idle = 0; }
                else idle++;
            }
        }
    }

    public static Candidate SimulatedAnnealing(Problem problem, SearchContext context, SaParameters p)
    {
        var current = context.Initial!;
        // Calibration evaluations are charged to the same budget and eligible as best-so-far.
        var uphill = new List<long>();
        var calibration = Math.Min(8, Math.Max(0, context.Budget - context.Evaluations - 1));
        for (var i = 0; i < calibration; i++)
        {
            var candidate = context.Evaluate(problem.Mutate(current.Genome, context.Rng));
            if (candidate.Energy > current.Energy) uphill.Add(candidate.Energy - current.Energy);
        }
        var typical = uphill.Count > 0 ? Median(uphill) : problem.MinuteWeight * 60.0;
        var temperature = Math.Max(1.0, -typical / Math.Log(p.InitialAcceptance));
        while (true)
        {
            var proposal = context.Evaluate(problem.Mutate(current.Genome, context.Rng));
            var delta = proposal.Energy - current.Energy;
            if (delta <= 0 || context.Rng.Random() < Math.Exp(-Math.Min(745.0, delta / Math.Max(temperature, 1e-12))))
                current = proposal;
            temperature *= p.CoolingRate;
        }
    }

    /// <summary>statistics.median: the middle value, or the mean of the two middle values.</summary>
    static double Median(List<long> values)
    {
        var sorted = values.OrderBy(v => v).ToArray();
        var mid = sorted.Length / 2;
        return sorted.Length % 2 == 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2.0;
    }

    public static int[] OrderedCrossover(int[] a, int[] b, PyRandom rng)
    {
        var n = a.Length;
        if (n < 2) return (int[])a.Clone();
        var pair = rng.SampleRange(n, 2);
        int left = Math.Min(pair[0], pair[1]), right = Math.Max(pair[0], pair[1]) + 1;
        var child = new int[n];
        var used = new HashSet<int>();
        for (var i = left; i < right; i++) { child[i] = a[i]; used.Add(a[i]); }
        var rest = b.Skip(right).Concat(b.Take(right)).Where(x => !used.Contains(x)).ToArray();
        var positions = Enumerable.Range(right, n - right).Concat(Enumerable.Range(0, left)).ToArray();
        for (var i = 0; i < Math.Min(positions.Length, rest.Length); i++) child[positions[i]] = rest[i];
        return child;
    }

    public static Candidate GeneticAlgorithm(Problem problem, SearchContext context, GaParameters p)
    {
        var population = new List<Candidate> { context.Initial! };
        while (population.Count < p.PopulationSize)
            population.Add(context.Evaluate(problem.RandomGenome(context.Rng)));

        Candidate Parent()
        {
            Candidate? best = null;
            for (var i = 0; i < p.TournamentSize; i++)
            {
                var pick = context.Rng.Choice(population);
                if (best is null || pick.Objectives < best.Objectives) best = pick;
            }
            return best!;
        }

        while (true)
        {
            context.Check();
            var following = population.OrderBy(c => c.Objectives).Take(p.Elites).ToList();
            while (following.Count < p.PopulationSize)
            {
                Candidate p1 = Parent(), p2 = Parent();
                Genome genome;
                if (context.Rng.Random() < p.CrossoverRate)
                {
                    var order = OrderedCrossover(p1.Genome.Order, p2.Genome.Order, context.Rng);
                    var preferences = new int[problem.ClassIds.Length];
                    for (var c = 0; c < preferences.Length; c++)
                        preferences[c] = (context.Rng.Random() < 0.5 ? p1 : p2).Genome.TimePreferences[c];
                    genome = new Genome(order, preferences);
                }
                else genome = p1.Genome;
                if (context.Rng.Random() < p.MutationRate) genome = problem.Mutate(genome, context.Rng);
                following.Add(context.Evaluate(genome));
            }
            population = following;
        }
    }
}
