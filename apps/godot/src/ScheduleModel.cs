using System;
using System.Collections.Generic;
using System.Linq;
using Timetabling.Engine;

namespace RoomMap;

/// <summary>What a block on the room map stands for.</summary>
public enum BlockState
{
    LabNeeded,       // a Lab held by a session that needs a Lab this week
    LabUnnecessary,  // a Lab held by a session that does not need one this week
    Lecture,         // a lecture room
    External,        // a fixed external booking (not an optimisation variable)
    Unavailable,     // outside the room's availability windows (other departments, closures)
    Unassigned,      // an active session that got no room this week
}

public sealed record Block(
    BlockState State, string? RoomId, int Day, int Start, int Duration, int Week,
    string? SessionId, string? ClassId, string? CourseId, string Label)
{
    public int End => Start + Duration;
}

/// <summary>Dataset lookups shared by every schedule drawn from it. Godot-free so the smoke test can use it.</summary>
public sealed class DatasetIndex
{
    public Dataset Data { get; }
    public string Sha256 { get; }
    /// <summary>Schedulable rooms in map order: Labs first, then lecture rooms, each by id.</summary>
    public Room[] Rooms { get; }
    public Dictionary<string, Room> RoomById { get; }
    public Dictionary<string, RecurringSession> Sessions { get; }
    public Dictionary<string, ClassInfo> Classes { get; }
    public int[] Weeks { get; }
    public int[] Days { get; }
    public int DayStart { get; }
    public int DayEnd { get; }
    public int LabCount { get; }
    public long TotalWeekly { get; }

    readonly Dictionary<(string Class, string Option), TimeOption> options = [];
    readonly Dictionary<(int Week, int Day), List<Block>> background = [];

    public DatasetIndex(Dataset data, string sha256)
    {
        Data = data;
        Sha256 = sha256;
        Rooms = data.Rooms.Where(r => r.Schedulable)
            .OrderBy(r => r.IsLab ? 0 : 1).ThenBy(r => r.Id, StringComparer.Ordinal).ToArray();
        RoomById = data.Rooms.ToDictionary(r => r.Id);
        LabCount = Rooms.Count(r => r.IsLab);
        Sessions = data.RecurringSessions.ToDictionary(s => s.Id);
        Classes = data.Classes.ToDictionary(c => c.Id);
        foreach (var c in data.Classes)
            foreach (var o in c.TimeOptions) options[(c.Id, o.Id)] = o;
        Weeks = data.Calendar.WeekIds.Count > 0
            ? data.Calendar.WeekIds.OrderBy(w => w).ToArray()
            : data.RecurringSessions.SelectMany(s => s.ActiveWeeks).Distinct().OrderBy(w => w).ToArray();
        TotalWeekly = data.RecurringSessions.Sum(s => (long)s.ActiveWeeks.Count);

        var meetings = data.Classes.SelectMany(c => c.TimeOptions).SelectMany(o => o.Meetings).ToList();
        var schedulable = Rooms.Select(r => r.Id).ToHashSet();
        var externalMeetings = data.ExternalClasses.Where(e => e.RoomIds.Any(schedulable.Contains)).SelectMany(e => e.Meetings).ToList();
        var all = meetings.Concat(externalMeetings).ToList();
        Days = all.Select(m => m.Day).Distinct().OrderBy(d => d).ToArray();
        if (Days.Length == 0) Days = [0, 1, 2, 3, 4];
        DayStart = all.Count > 0 ? all.Min(m => m.StartMinute) / 60 * 60 : 480;
        DayEnd = all.Count > 0 ? (all.Max(m => m.EndMinute) + 59) / 60 * 60 : 1080;
        if (DayEnd - DayStart < 240) DayEnd = DayStart + 240;
    }

    public TimeOption? Option(string classId, string? optionId) =>
        optionId is not null && options.TryGetValue((classId, optionId), out var o) ? o : null;

    /// <summary>External bookings and unavailable windows of the schedulable rooms for one week and day.</summary>
    public List<Block> Background(int week, int day)
    {
        if (background.TryGetValue((week, day), out var cached)) return cached;
        var list = new List<Block>();
        foreach (var room in Rooms)
        {
            // Complement of the availability windows inside the drawn day range.
            var windows = room.Availability.Where(w => w.Day == day).OrderBy(w => w.StartMinute).ToList();
            var cursor = DayStart;
            foreach (var w in windows)
            {
                if (w.StartMinute > cursor)
                    AddGap(list, room.Id, day, week, cursor, Math.Min(w.StartMinute, DayEnd));
                cursor = Math.Max(cursor, w.EndMinute);
            }
            if (cursor < DayEnd) AddGap(list, room.Id, day, week, cursor, DayEnd);
        }
        foreach (var e in Data.ExternalClasses)
        {
            if (!e.ActiveWeeks.Contains(week)) continue;
            foreach (var rid in e.RoomIds)
            {
                if (!RoomById.TryGetValue(rid, out var r) || !r.Schedulable) continue;
                foreach (var m in e.Meetings.Where(m => m.Day == day))
                    list.Add(new Block(BlockState.External, rid, day, m.StartMinute, m.DurationMinutes, week, null, e.Id, null, e.Id));
            }
        }
        background[(week, day)] = list;
        return list;
    }

    void AddGap(List<Block> list, string roomId, int day, int week, int start, int end)
    {
        start = Math.Max(start, DayStart);
        if (end - start <= 0) return;
        // An unavailable window that coincides with an external booking is drawn as the booking only.
        list.Add(new Block(BlockState.Unavailable, roomId, day, start, end - start, week, null, null, null, "unavailable"));
    }
}

/// <summary>Per-week numbers of one schedule.</summary>
public sealed record WeekStats(int Week, long LabNeededMinutes, long LabUnnecessaryMinutes, long LectureMinutes, long Unassigned);

/// <summary>
/// One schedule (a solution) laid out for drawing. Its totals are recomputed from the raw records with the same rules
/// as engine/solution_validator.py, so they can be checked against the metrics stored in an experiment file.
/// </summary>
public sealed class Schedule
{
    public DatasetIndex Index { get; }
    public Solution Solution { get; }
    public string RoomMode { get; }
    public string Title { get; }
    public string Algorithm { get; }
    public ulong Seed { get; }

    public long Assigned { get; }
    public long Unassigned { get; }
    public long UnnecessaryLabMinutes { get; }
    public double UnnecessaryLabHours => UnnecessaryLabMinutes / 60.0;
    public long RoomChanges { get; }
    public int UnscheduledClasses { get; }
    public WeekStats[] PerWeek { get; }

    readonly Dictionary<string, Meeting> meetingOf = [];
    readonly Dictionary<(string Session, int Week), string> roomOf = [];
    readonly Dictionary<(int Week, int Day), List<Block>> blocks = [];

    public Schedule(DatasetIndex index, Solution solution, string roomMode, string algorithm, ulong seed, string title)
    {
        Index = index;
        Solution = solution;
        RoomMode = roomMode;
        Algorithm = algorithm;
        Seed = seed;
        Title = title;

        foreach (var (classId, optionId) in solution.ClassTimeOptions)
        {
            var option = index.Option(classId, optionId);
            if (option is null) { UnscheduledClasses++; continue; }
            foreach (var m in option.Meetings)
                if (m.SessionId is not null) meetingOf[m.SessionId] = m;
        }
        foreach (var a in solution.WeeklyRoomAssignments) roomOf[(a.SessionId, a.Week)] = a.RoomId;

        long lab = 0, changes = 0;
        foreach (var a in solution.WeeklyRoomAssignments)
        {
            if (!index.Sessions.TryGetValue(a.SessionId, out var s) || !index.RoomById.TryGetValue(a.RoomId, out var room)) continue;
            if (room.IsLab && !s.LabWeeks.Contains(a.Week)) lab += s.DurationMinutes;
        }
        foreach (var s in index.Data.RecurringSessions)
        {
            string? previous = null;
            foreach (var week in s.ActiveWeeks.OrderBy(w => w))
            {
                if (!roomOf.TryGetValue((s.Id, week), out var room)) continue;
                if (previous is not null && room != previous) changes++;
                previous = room;
            }
        }
        Assigned = roomOf.Count;
        Unassigned = index.TotalWeekly - Assigned;
        UnnecessaryLabMinutes = lab;
        RoomChanges = changes;

        PerWeek = index.Weeks.Select(week =>
        {
            long needed = 0, unnecessary = 0, lecture = 0, unassigned = 0;
            foreach (var s in index.Data.RecurringSessions)
            {
                if (!s.ActiveWeeks.Contains(week)) continue;
                if (!roomOf.TryGetValue((s.Id, week), out var rid)) { unassigned++; continue; }
                var room = index.RoomById[rid];
                if (!room.IsLab) lecture += s.DurationMinutes;
                else if (s.LabWeeks.Contains(week)) needed += s.DurationMinutes;
                else unnecessary += s.DurationMinutes;
            }
            return new WeekStats(week, needed, unnecessary, lecture, unassigned);
        }).ToArray();
    }

    public Meeting? MeetingOf(string sessionId) => meetingOf.TryGetValue(sessionId, out var m) ? m : null;

    public string? RoomOf(string sessionId, int week) => roomOf.TryGetValue((sessionId, week), out var r) ? r : null;

    public BlockState StateOf(RecurringSession s, int week, string? roomId)
    {
        if (roomId is null) return BlockState.Unassigned;
        var room = Index.RoomById[roomId];
        if (!room.IsLab) return BlockState.Lecture;
        return s.LabWeeks.Contains(week) ? BlockState.LabNeeded : BlockState.LabUnnecessary;
    }

    /// <summary>Scheduled sessions (and unassigned ones that have a time) for one week and day.</summary>
    public List<Block> Blocks(int week, int day)
    {
        if (blocks.TryGetValue((week, day), out var cached)) return cached;
        var list = new List<Block>();
        foreach (var s in Index.Data.RecurringSessions)
        {
            if (!s.ActiveWeeks.Contains(week) || MeetingOf(s.Id) is not { } m || m.Day != day) continue;
            var room = RoomOf(s.Id, week);
            var cls = Index.Classes.GetValueOrDefault(s.ClassId);
            list.Add(new Block(StateOf(s, week, room), room, m.Day, m.StartMinute, m.DurationMinutes, week,
                s.Id, s.ClassId, cls?.CourseId, s.ClassId));
        }
        blocks[(week, day)] = list;
        return list;
    }

    /// <summary>Room changes of one session over its active weeks (validator rule).</summary>
    public int ChangesOf(string sessionId)
    {
        if (!Index.Sessions.TryGetValue(sessionId, out var s)) return 0;
        string? previous = null;
        var changes = 0;
        foreach (var week in s.ActiveWeeks.OrderBy(w => w))
        {
            if (RoomOf(s.Id, week) is not { } room) continue;
            if (previous is not null && room != previous) changes++;
            previous = room;
        }
        return changes;
    }
}
