using System.Text.Json.Nodes;
using System.Text.Json.Serialization;

namespace Timetabling.Engine;

// CONTRACT for the validators session. Shapes serialize (snake_case, Dataset.Json options) to the same
// JSON as engine/solution_validator.py and engine/input_validation.py. Do not rename members.

public sealed record Violation(string Code, JsonNode? Detail);

public sealed record AuditMetrics(
    string RoomMode,
    long UnassignedWeeklySessions,
    long AssignedWeeklySessions,
    long TotalWeeklySessions,
    long UnnecessaryLabMinutes,
    double UnnecessaryLabHours,
    long RoomChanges,
    int HardViolations);

public sealed record AuditResult(
    bool Valid,
    int ViolationCount,
    List<Violation> Violations,
    bool ViolationsTruncated,
    AuditMetrics? Metrics);

/// <summary>Port of engine/solution_validator.py: audits a schedule from raw input records only.</summary>
public static partial class SolutionValidator
{
    public static AuditResult Audit(Dataset data, Solution? solution, string roomMode = RoomModes.Weekly) =>
        Run(data, solution, roomMode);
}

public sealed record InputReport(
    string Status,
    List<string> Errors,
    List<JsonObject> Warnings,
    JsonObject Summary,
    // Python leaves both keys out of a failed report, so null is not written.
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] JsonObject? LabRequiredMeetingsPerWeek = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] JsonObject? LocalFeasibility = null);

/// <summary>Port of engine/input_validation.py.</summary>
public static partial class InputValidator
{
    public static InputReport Validate(Dataset data) => Run(data);
}
