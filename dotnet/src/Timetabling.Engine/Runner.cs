using System.Text.Json.Nodes;
using System.Text.Json.Serialization;

namespace Timetabling.Engine;

// CONTRACT for the runner session. RunResult serializes (Dataset.Json options) to the same keys as one
// result record of engine/runner.py run_one, so engine/analyze.py and the web app can read C# output.

public sealed record RunConfig(int Budget = 100, double Seconds = 60, string RoomMode = RoomModes.Weekly, MethodParameters? Parameters = null)
{
    /// <summary>
    /// The "parameters" object exactly as the user gave it, when known. Python records
    /// config['parameters'].get(method, {}) in each result, so RunOne copies that object from here; without
    /// it RunOne writes the method's typed parameters (defaults included).
    /// </summary>
    [JsonIgnore] public JsonObject? ParametersJson { get; init; }

    /// <summary>Reads a run configuration the way runner.py does: config.get(key, default), int() of integer parameters.</summary>
    public static RunConfig FromJson(JsonObject config) => RunConfigReader.Read(config);
}

public sealed record EnergyWeights(long Unassigned, long LabMinute, long RoomChange);

public sealed record PreparationMeta(
    JsonObject Summary,
    List<JsonObject> Warnings,
    string DatasetSha256,
    double PreprocessingSeconds,
    EnergyWeights EnergyWeights);

public sealed record Prepared(Problem Problem, PreparationMeta Meta, string DatasetText);

public sealed record RunError(string Message, string? Traceback = null);

public sealed class RunResult
{
    public string Algorithm { get; set; } = "";
    public string RoomMode { get; set; } = RoomModes.Weekly;
    public ulong Seed { get; set; }
    public string Status { get; set; } = "";
    public bool Valid { get; set; }
    public AuditMetrics? Metrics { get; set; }
    public AuditResult? Validation { get; set; }
    public Solution? Solution { get; set; }
    public int Evaluations { get; set; }
    public int AttemptedEvaluations { get; set; }
    public int Budget { get; set; }
    public double TimeLimitSeconds { get; set; }
    public double SearchSeconds { get; set; }
    public double ValidationSeconds { get; set; }
    public List<TracePoint> Trace { get; set; } = [];
    public RunError? Error { get; set; }
    public JsonObject Parameters { get; set; } = [];
    public string DatasetId { get; set; } = "";
    public string? DatasetSha256 { get; set; }
    public string? OriginalSourceSha256 { get; set; }
    public string CodeSha256 { get; set; } = "";
    public string EngineVersion { get; set; } = Problem.Version;
    public JsonObject Runtime { get; set; } = [];
    public EnergyWeights? EnergyWeights { get; set; }
    // Batch bookkeeping, set by the CLI batch runner (same keys as engine/batch.py).
    public string? ConfigId { get; set; }
    public string? Fingerprint { get; set; }
    public string? StartedAt { get; set; }
    public string? FinishedAt { get; set; }
    public int? WorkerPid { get; set; }
    public int? RunIndex { get; set; }
}

/// <summary>Port of engine/runner.py.</summary>
public static partial class Runner
{
    public static Prepared Prepare(string datasetText) => PrepareCore(datasetText);

    public static void CheckConfiguration(RunConfig config) => CheckCore(config);

    public static RunResult RunOne(Prepared prepared, RunConfig config, string method, ulong seed,
                                   Action<ProgressEvent>? progress = null, CancellationToken cancellation = default) =>
        RunCore(prepared, config, method, seed, progress, cancellation);

    /// <summary>SHA-256 identifying the C# engine sources (counterpart of batch.engine_snapshot).</summary>
    public static string EngineSha256 => engineSha.Value;
}
