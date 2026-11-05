using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Timetabling.Engine;

/// <summary>Typed view of the timetable-lab input contract (data/FORMAT.txt). Unknown fields are ignored.</summary>
public sealed record Dataset
{
    public string SchemaVersion { get; init; } = "";
    public string DatasetId { get; init; } = "";
    public SourceInfo? Source { get; init; }
    public CalendarInfo Calendar { get; init; } = new();
    public List<Room> Rooms { get; init; } = [];
    public List<Instructor> Instructors { get; init; } = [];
    public List<StudentGroup> StudentGroups { get; init; } = [];
    public List<ClassInfo> Classes { get; init; } = [];
    public List<RecurringSession> RecurringSessions { get; init; } = [];
    public List<ExternalClass> ExternalClasses { get; init; } = [];
    public Constraints Constraints { get; init; } = new();
    public ObjectiveSpec Objectives { get; init; } = new();

    public static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DictionaryKeyPolicy = null,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    public static Dataset Parse(string text) =>
        JsonSerializer.Deserialize<Dataset>(text, Json) ?? throw new InvalidDataException("Dataset is empty");

    /// <summary>Reads a .json or .json.gz file as UTF-8 text, exactly as the Python tools do.</summary>
    public static string ReadText(string path)
    {
        var bytes = File.ReadAllBytes(path);
        if (path.EndsWith(".gz", StringComparison.OrdinalIgnoreCase))
        {
            using var input = new GZipStream(new MemoryStream(bytes), CompressionMode.Decompress);
            using var output = new MemoryStream();
            input.CopyTo(output);
            bytes = output.ToArray();
        }
        return new UTF8Encoding(false, true).GetString(bytes);
    }

    public static string Sha256(string text) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();
}

public sealed record SourceInfo { public string? Sha256 { get; init; } }

public sealed record CalendarInfo { public List<int> WeekIds { get; init; } = []; }

public sealed record AvailabilityWindow { public int Day { get; init; } public int StartMinute { get; init; } public int EndMinute { get; init; } }

public sealed record Room
{
    public string Id { get; init; } = "";
    public string Kind { get; init; } = "";
    public bool Schedulable { get; init; }
    public int Capacity { get; init; }
    public List<AvailabilityWindow> Availability { get; init; } = [];
    public bool IsLab => Kind == "computer_lab";
}

public sealed record Instructor { public string Id { get; init; } = ""; public string? Origin { get; init; } }

public sealed record StudentGroup
{
    public string Id { get; init; } = "";
    public List<string> SourceStudentIds { get; init; } = [];
    public int KnownStudentCount { get; init; }
    public List<string> ClassIds { get; init; } = [];
}

public sealed record Meeting
{
    public int Day { get; init; }
    public int StartMinute { get; init; }
    public int DurationMinutes { get; init; }
    public string? SessionId { get; init; }
    [JsonIgnore] public int EndMinute => StartMinute + DurationMinutes;
}

public sealed record TimeOption { public string Id { get; init; } = ""; public List<Meeting> Meetings { get; init; } = []; }

public sealed record ClassInfo
{
    public string Id { get; init; } = "";
    public string? CourseId { get; init; }
    public int StudentCount { get; init; }
    public int KnownEnrolledStudentCount { get; init; }
    public List<string> InstructorIds { get; init; } = [];
    public List<string> StudentGroupIds { get; init; } = [];
    public List<string> LectureRoomIds { get; init; } = [];
    public List<string> LabRoomIds { get; init; } = [];
    public List<string> SourceAllowedRoomIds { get; init; } = [];
    public List<string> SessionIds { get; init; } = [];
    public List<TimeOption> TimeOptions { get; init; } = [];
}

public sealed record RecurringSession
{
    public string Id { get; init; } = "";
    public string ClassId { get; init; } = "";
    public int DurationMinutes { get; init; }
    public List<int> ActiveWeeks { get; init; } = [];
    public List<int> LabWeeks { get; init; } = [];
}

public sealed record ExternalClass
{
    public string Id { get; init; } = "";
    public List<string> RoomIds { get; init; } = [];
    public List<string> InstructorIds { get; init; } = [];
    public List<string> StudentGroupIds { get; init; } = [];
    public List<Meeting> Meetings { get; init; } = [];
    public List<int> ActiveWeeks { get; init; } = [];
}

public sealed record ConstraintGroup { public string SourceConstraintId { get; init; } = ""; public List<string> ClassIds { get; init; } = []; }

public sealed record Constraints
{
    public List<ConstraintGroup> NonOverlapGroups { get; init; } = [];
    public List<ConstraintGroup> SameTimeOfDayGroups { get; init; } = [];
    public bool ExternalStudentOverlapIsHard { get; init; }
}

public sealed record ObjectiveSpec { public List<string> OrderedMetrics { get; init; } = []; }
