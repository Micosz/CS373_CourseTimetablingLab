using System.Text;
using System.Text.Json.Nodes;

namespace Timetabling.Engine;

/// <summary>
/// Port of engine/solution_validator.py audit_solution. It reads only the raw input records, never the
/// decoder's compiled caches. Violation order, de-duplication and the 200-entry cap follow Python, so the
/// serialized result has the same keys and values.
/// </summary>
public static partial class SolutionValidator
{
    const int MaxListed = 200;

    sealed class Collector
    {
        public readonly List<Violation> Listed = [];
        public readonly HashSet<string> Seen = [];

        // Python de-duplicates on (code, str(detail)); the JSON text of the detail is an equivalent key.
        public void Error(string code, JsonNode? detail)
        {
            var key = code + "\u0000" + (detail?.ToJsonString() ?? "null");
            if (Seen.Add(key) && Listed.Count < MaxListed) Listed.Add(new Violation(code, detail));
        }
    }

    sealed record Event(string EventId, string ClassId, bool Target, int Week, int Day, int Start, int End,
                        List<string> Rooms, List<string> Instructors, List<string> Groups);

    static JsonArray SessionWeek(string sid, int week) => [sid, week];

    static AuditResult Run(Dataset data, Solution? solution, string roomMode)
    {
        var errors = new Collector();
        if (solution is null)
            return new AuditResult(false, 1, [new Violation("SCHEMA", "Solution must be an object")], false, null);

        var classes = new Dictionary<string, ClassInfo>();
        foreach (var c in data.Classes) classes[c.Id] = c;
        var sessions = new Dictionary<string, RecurringSession>();
        foreach (var s in data.RecurringSessions) sessions[s.Id] = s;
        var rooms = new Dictionary<string, Room>();
        foreach (var r in data.Rooms) rooms[r.Id] = r;
        var choices = solution.ClassTimeOptions ?? [];
        var rows = solution.WeeklyRoomAssignments ?? [];

        if (!RoomModes.IsValid(roomMode))
            errors.Error("ROOM_MODE", $"Unknown room mode {PyRepr(roomMode)}");
        if (solution.RoomMode != roomMode)
            errors.Error("ROOM_MODE", $"Solution declares {PyRepr(solution.RoomMode)} but was audited as {PyRepr(roomMode)}");
        if (solution.DatasetId != data.DatasetId)
            errors.Error("DATASET_ID", "Solution belongs to a different dataset");
        foreach (var cid in choices.Keys)
            if (!classes.ContainsKey(cid)) errors.Error("UNKNOWN_CLASS", cid);

        var selected = new Dictionary<string, TimeOption>();
        var classMeetings = new Dictionary<string, Meeting>();
        foreach (var (cid, c) in classes)
        {
            if (!choices.TryGetValue(cid, out var value) || value is null) continue;
            var option = c.TimeOptions.FirstOrDefault(o => o.Id == value);
            if (option is null)
            {
                errors.Error("TIME_OPTION", cid);
                continue;
            }
            selected[cid] = option;
            foreach (var meeting in option.Meetings) classMeetings[meeting.SessionId ?? ""] = meeting;
        }

        var events = new List<Event>();
        var assigned = new Dictionary<(string, int), string>();
        long labMinutes = 0;
        for (var index = 0; index < rows.Count; index++)
        {
            var row = rows[index];
            if (row is null)
            {
                errors.Error("SCHEMA", $"Assignment {index} is not an object");
                continue;
            }
            string sid = row.SessionId, rid = row.RoomId;
            var week = row.Week;
            if (sid is null || rid is null || !sessions.ContainsKey(sid) || !rooms.ContainsKey(rid))
            {
                errors.Error("ASSIGNMENT_REFERENCE", index);
                continue;
            }
            var key = (sid, week);
            if (assigned.ContainsKey(key))
            {
                errors.Error("DUPLICATE_SESSION_WEEK", SessionWeek(sid, week));
                continue;
            }
            var s = sessions[sid];
            var c = classes[s.ClassId];
            var room = rooms[rid];
            if (!s.ActiveWeeks.Contains(week))
            {
                errors.Error("INACTIVE_WEEK", SessionWeek(sid, week));
                continue;
            }
            if (!classMeetings.TryGetValue(sid, out var meeting))
            {
                errors.Error("MISSING_TIME", SessionWeek(sid, week));
                continue;
            }
            assigned[key] = rid;
            var needLab = s.LabWeeks.Contains(week);
            var inDomain = c.LabRoomIds.Contains(rid) || (!needLab && c.LectureRoomIds.Contains(rid));
            if (!inDomain || !room.Schedulable) errors.Error("ROOM_DOMAIN", SessionWeek(sid, week));
            if (room.Capacity < c.StudentCount) errors.Error("CAPACITY", SessionWeek(sid, week));
            if (needLab && room.Kind != "computer_lab") errors.Error("LAB_REQUIRED", SessionWeek(sid, week));
            var end = meeting.StartMinute + meeting.DurationMinutes;
            if (!room.Availability.Any(w => w.Day == meeting.Day && w.StartMinute <= meeting.StartMinute && end <= w.EndMinute))
                errors.Error("ROOM_UNAVAILABLE", SessionWeek(sid, week));
            if (!needLab && room.Kind == "computer_lab") labMinutes += s.DurationMinutes;
            events.Add(new Event($"{sid}:{week}", c.Id, true, week, meeting.Day, meeting.StartMinute, end,
                                 [rid], c.InstructorIds, c.StudentGroupIds));
        }
        foreach (var e in data.ExternalClasses)
            foreach (var week in e.ActiveWeeks)
                for (var number = 0; number < e.Meetings.Count; number++)
                {
                    var m = e.Meetings[number];
                    events.Add(new Event($"EXT:{e.Id}:{number}:{week}", e.Id, false, week, m.Day, m.StartMinute,
                                         m.StartMinute + m.DurationMinutes, e.RoomIds, e.InstructorIds,
                                         data.Constraints.ExternalStudentOverlapIsHard ? e.StudentGroupIds : []));
                }

        var byClassConstraints = new Dictionary<string, List<string>>();
        for (var groupIndex = 0; groupIndex < data.Constraints.NonOverlapGroups.Count; groupIndex++)
        {
            var g = data.Constraints.NonOverlapGroups[groupIndex];
            foreach (var cid in g.ClassIds)
            {
                // Source ID 90 is reused for 80 different SAME_STUDENTS groups: never merge by source ID.
                if (!byClassConstraints.TryGetValue(cid, out var list)) byClassConstraints[cid] = list = [];
                list.Add($"{groupIndex}:{g.SourceConstraintId}");
            }
        }

        // Buckets are visited in first-insertion order, as Python's defaultdict does.
        var buckets = new Dictionary<(string Kind, string Resource, int Week, int Day), List<Event>>();
        var bucketOrder = new List<(string Kind, string Resource, int Week, int Day)>();
        void Put(string kind, string resource, Event ev)
        {
            var key = (kind, resource, ev.Week, ev.Day);
            if (!buckets.TryGetValue(key, out var items))
            {
                buckets[key] = items = [];
                bucketOrder.Add(key);
            }
            items.Add(ev);
        }
        foreach (var ev in events)
        {
            foreach (var r in ev.Rooms) Put("ROOM", r, ev);
            foreach (var t in ev.Instructors) Put("INSTRUCTOR", t, ev);
            foreach (var g in ev.Groups) Put("STUDENT_GROUP", g, ev);
            if (byClassConstraints.TryGetValue(ev.ClassId, out var constraintKeys))
                foreach (var k in constraintKeys) Put("DISTRIBUTION", k, ev);
        }
        foreach (var bucket in bucketOrder)
        {
            var items = buckets[bucket];
            var sorted = items.OrderBy(e => e.Start).ThenBy(e => e.End).ThenBy(e => e.EventId, StringComparer.Ordinal).ToList();
            var active = new List<Event>();
            foreach (var ev in sorted)
            {
                active.RemoveAll(other => other.End <= ev.Start);
                foreach (var other in active)
                {
                    if (ev.ClassId == other.ClassId && bucket.Kind == "DISTRIBUTION") continue;
                    if ((ev.Target || other.Target) && ev.EventId != other.EventId)
                    {
                        var pair = string.CompareOrdinal(ev.EventId, other.EventId) <= 0
                            ? new JsonArray(ev.EventId, other.EventId) : new JsonArray(other.EventId, ev.EventId);
                        errors.Error(bucket.Kind + "_OVERLAP", new JsonObject
                        {
                            ["resource"] = bucket.Resource, ["week"] = bucket.Week, ["day"] = bucket.Day, ["events"] = pair,
                        });
                    }
                }
                active.Add(ev);
            }
        }

        var external = new Dictionary<string, ExternalClass>();
        foreach (var e in data.ExternalClasses) external[e.Id] = e;
        Meeting? Interval(string cid) =>
            selected.TryGetValue(cid, out var o) ? o.Meetings[0] : external.TryGetValue(cid, out var e) ? e.Meetings[0] : null;
        foreach (var group in data.Constraints.SameTimeOfDayGroups)
        {
            var ids = group.ClassIds;
            for (var i = 0; i < ids.Count; i++)
                for (var j = i + 1; j < ids.Count; j++)
                {
                    string a = ids[i], b = ids[j];
                    if (!classes.ContainsKey(a) && !classes.ContainsKey(b)) continue;
                    Meeting? ma = Interval(a), mb = Interval(b);
                    if (ma is null || mb is null) continue;
                    if (!Problem.ContainedTime(ma, mb))
                        errors.Error("SAME_TIME", new JsonObject { ["constraint"] = group.SourceConstraintId, ["classes"] = new JsonArray(a, b) });
                }
        }

        long changes = 0;
        foreach (var (sid, session) in sessions)
        {
            string? previous = null;
            var used = new HashSet<string>();
            foreach (var week in session.ActiveWeeks.OrderBy(w => w))
            {
                if (!assigned.TryGetValue((sid, week), out var room)) continue;
                if (previous is not null && room != previous) changes++;
                previous = room;
                used.Add(room);
            }
            if (roomMode == RoomModes.Fixed)
            {
                var usedSorted = used.OrderBy(r => r, StringComparer.Ordinal).ToArray();
                JsonObject Detail() => new() { ["session"] = sid, ["rooms"] = new JsonArray(usedSorted.Select(r => (JsonNode)r).ToArray()) };
                if (usedSorted.Length > 1) errors.Error("FIXED_ROOM_CHANGED", Detail());
                if (session.LabWeeks.Count > 0 && usedSorted.Any(rid => rooms[rid].Kind != "computer_lab"))
                    errors.Error("FIXED_ROOM_NOT_LAB", Detail());
            }
        }
        var total = sessions.Values.Sum(s => (long)s.ActiveWeeks.Count);
        var metrics = new AuditMetrics(roomMode, total - assigned.Count, assigned.Count, total, labMinutes, labMinutes / 60.0,
                                       changes, errors.Seen.Count);
        return new AuditResult(errors.Seen.Count == 0, errors.Seen.Count, errors.Listed, errors.Seen.Count > errors.Listed.Count, metrics);
    }

    /// <summary>Python repr() of a str, as used in the ROOM_MODE messages.</summary>
    internal static string PyRepr(string? value)
    {
        if (value is null) return "None";
        var quote = value.Contains('\'') && !value.Contains('"') ? '"' : '\'';
        var sb = new StringBuilder().Append(quote);
        foreach (var ch in value)
        {
            if (ch == quote || ch == '\\') sb.Append('\\').Append(ch);
            else if (ch == '\n') sb.Append("\\n");
            else if (ch == '\r') sb.Append("\\r");
            else if (ch == '\t') sb.Append("\\t");
            else if (ch < 0x20 || ch == 0x7f) sb.Append($"\\x{(int)ch:x2}");
            else sb.Append(ch);
        }
        return sb.Append(quote).ToString();
    }
}
