using System.Text.Json.Serialization;

namespace Timetabling.Engine;

public static class RoomModes
{
    public const string Weekly = "weekly", Fixed = "fixed";
    public static readonly string[] All = [Weekly, Fixed];
    public static bool IsValid(string? mode) => mode is Weekly or Fixed;
}

/// <summary>Lexicographic objectives: unassigned weekly sessions, unnecessary Lab minutes, room changes.</summary>
public readonly record struct Objectives(long Unassigned, long LabMinutes, long RoomChanges) : IComparable<Objectives>
{
    public int CompareTo(Objectives other)
    {
        var c = Unassigned.CompareTo(other.Unassigned);
        if (c != 0) return c;
        c = LabMinutes.CompareTo(other.LabMinutes);
        return c != 0 ? c : RoomChanges.CompareTo(other.RoomChanges);
    }

    public static bool operator <(Objectives a, Objectives b) => a.CompareTo(b) < 0;
    public static bool operator >(Objectives a, Objectives b) => a.CompareTo(b) > 0;
    public long[] ToArray() => [Unassigned, LabMinutes, RoomChanges];
}

/// <summary>A class priority permutation plus one preferred time option per class, both by class index.</summary>
public sealed record Genome(int[] Order, int[] TimePreferences)
{
    public Genome Copy() => new((int[])Order.Clone(), (int[])TimePreferences.Clone());
}

public sealed record Assignment(string SessionId, int Week, string RoomId);

public sealed class Solution
{
    public string DatasetId { get; init; } = "";
    public string RoomMode { get; init; } = RoomModes.Weekly;
    public Dictionary<string, string?> ClassTimeOptions { get; init; } = [];
    public List<Assignment> WeeklyRoomAssignments { get; init; } = [];
}

public sealed record Candidate(Genome Genome, Solution Solution, Objectives Objectives, long Energy);

public sealed class SearchStoppedException(string reason) : Exception(reason)
{
    public string Reason { get; } = reason;
}

/// <summary>One point of the best-so-far trace, as stored in the Python result files.</summary>
public sealed record TracePoint(
    int Evaluations,
    double Seconds,
    long[] Objectives,
    [property: JsonPropertyName("current_objectives")] long[] CurrentObjectives);

public sealed record ProgressEvent(int Evaluations, int Budget, double Seconds, Objectives Best, Objectives Current);
