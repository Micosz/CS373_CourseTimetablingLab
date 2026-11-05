using System.Text.Json.Nodes;

namespace Timetabling.Engine;

/// <summary>
/// Port of engine/input_validation.py validate: independent checks of a converted input, not a proof of
/// global schedulability. Error messages, their order, warnings and summary keys follow Python.
/// </summary>
public static partial class InputValidator
{
    static readonly string[] RequiredFields =
        ["schema_version", "dataset_id", "calendar", "rooms", "instructors", "student_groups",
         "classes", "recurring_sessions", "external_classes", "constraints", "objectives"];

    static readonly string[] OrderedMetrics = ["unassigned_weekly_sessions", "unnecessary_lab_minutes", "room_changes"];

    static readonly HashSet<string> RoomKinds = ["lecture", "computer_lab", "background_only"];

    static InputReport Failed(List<string> errors) => new("failed", errors, [], []);

    /// <summary>
    /// Validates dataset JSON text. A typed <see cref="Dataset"/> fills missing fields with defaults, so the
    /// Python "Missing top-level field" check is made here on the raw object before parsing.
    /// </summary>
    public static InputReport ValidateText(string datasetText) =>
        JsonNode.Parse(datasetText) is JsonObject raw ? ValidateRaw(raw, datasetText, out _) : Failed(["Dataset must be a JSON object"]);

    internal static InputReport ValidateRaw(JsonObject raw, string datasetText, out Dataset? data)
    {
        data = null;
        var errors = new List<string>();
        foreach (var key in RequiredFields)
            if (!raw.ContainsKey(key)) errors.Add("Missing top-level field: " + key);
        if (errors.Count > 0) return Failed(errors);
        data = Dataset.Parse(datasetText);
        return Validate(data);
    }

    /// <summary>Python dict built from a list: the last record wins, keeping the first record's position.</summary>
    static Dictionary<string, T> ById<T>(IEnumerable<T> items, Func<T, string> id)
    {
        var map = new Dictionary<string, T>();
        foreach (var item in items) map[id(item)] = item;
        return map;
    }

    static bool Overlap(Meeting a, Meeting b) =>
        a.Day == b.Day && a.StartMinute < b.StartMinute + b.DurationMinutes && b.StartMinute < a.StartMinute + a.DurationMinutes;

    static bool FitsWindow(Meeting m, Room room) =>
        room.Availability.Any(w => w.Day == m.Day && w.StartMinute <= m.StartMinute && m.StartMinute + m.DurationMinutes <= w.EndMinute);

    static List<T> Bucket<T>(Dictionary<string, List<T>> table, string key) =>
        table.TryGetValue(key, out var list) ? list : table[key] = [];

    static InputReport Run(Dataset data)
    {
        var errors = new List<string>();
        void Require(bool condition, string message)
        {
            if (!condition) errors.Add(message);
        }

        Require(data.SchemaVersion == "1.0", "Unsupported schema version");
        void Unique(IEnumerable<string> ids, string key)
        {
            var list = ids.ToList();
            Require(list.Count == list.Distinct().Count(), "Duplicate IDs in " + key);
        }
        Unique(data.Rooms.Select(x => x.Id), "rooms");
        Unique(data.Instructors.Select(x => x.Id), "instructors");
        Unique(data.StudentGroups.Select(x => x.Id), "student_groups");
        Unique(data.Classes.Select(x => x.Id), "classes");
        Unique(data.RecurringSessions.Select(x => x.Id), "recurring_sessions");
        Unique(data.ExternalClasses.Select(x => x.Id), "external_classes");
        var rooms = ById(data.Rooms, x => x.Id);
        var teachers = ById(data.Instructors, x => x.Id);
        var groups = ById(data.StudentGroups, x => x.Id);
        var classes = ById(data.Classes, x => x.Id);
        var sessions = ById(data.RecurringSessions, x => x.Id);
        var external = ById(data.ExternalClasses, x => x.Id);
        var knownClassIds = classes.Keys.Concat(external.Keys).ToHashSet();
        Require(!classes.Keys.Any(external.ContainsKey), "Target and external class IDs overlap");
        var weeks = data.Calendar.WeekIds;
        var weekSet = weeks.ToHashSet();
        Require(weeks.Count > 0 && weeks.SequenceEqual(Enumerable.Range(1, weeks.Count)), "Weeks must be contiguous positive IDs");

        foreach (var r in rooms.Values)
        {
            Require(r.Capacity >= 0, "Invalid capacity: " + r.Id);
            Require(RoomKinds.Contains(r.Kind), "Unknown room kind: " + r.Id);
            Require(!r.Schedulable || r.Kind != "background_only", "Background room is schedulable: " + r.Id);
            foreach (var w in r.Availability)
                Require(0 <= w.Day && w.Day <= 6 && 0 <= w.StartMinute && w.StartMinute < w.EndMinute && w.EndMinute <= 1440,
                        "Invalid availability interval: " + r.Id);
        }
        foreach (var g in groups.Values)
        {
            Require(g.ClassIds.All(knownClassIds.Contains), "Unknown class in group: " + g.Id);
            Require(g.SourceStudentIds.Count == g.SourceStudentIds.Distinct().Count() && g.SourceStudentIds.Count == g.KnownStudentCount,
                    "Student group count/IDs disagree: " + g.Id);
        }
        var sourceStudents = groups.Values.SelectMany(g => g.SourceStudentIds).ToList();
        Require(sourceStudents.Count == sourceStudents.Distinct().Count(), "A student is duplicated across roster groups");

        var optionIds = new List<string>();
        var referencedSessions = new List<string>();
        foreach (var c in classes.Values)
        {
            var cid = c.Id;
            Require(c.InstructorIds.All(teachers.ContainsKey) && c.InstructorIds.Count > 0, "Invalid instructor reference: " + cid);
            Require(c.StudentGroupIds.All(groups.ContainsKey), "Invalid student group reference: " + cid);
            Require(c.StudentCount > 0, "Invalid student demand: " + cid);
            Require(c.KnownEnrolledStudentCount <= c.StudentCount, "Known enrollment exceeds seat demand: " + cid);
            Require(c.StudentGroupIds.Where(groups.ContainsKey).Sum(g => (long)groups[g].KnownStudentCount) == c.KnownEnrolledStudentCount,
                    "Roster count does not reconcile: " + cid);
            foreach (var gid in c.StudentGroupIds)
                if (groups.TryGetValue(gid, out var g))
                    Require(g.ClassIds.Contains(cid), "Group membership not reciprocal: " + cid);
            Require(c.SourceAllowedRoomIds.All(rooms.ContainsKey), "Unknown source room: " + cid);
            Require(c.LectureRoomIds.All(c.SourceAllowedRoomIds.Contains), "Lecture domain expanded without provenance: " + cid);
            foreach (var (field, ids, kind) in new[] { ("lecture_room_ids", c.LectureRoomIds, "lecture"), ("lab_room_ids", c.LabRoomIds, "computer_lab") })
            {
                Require(ids.Count > 0, "Empty capacity-compatible " + field + ": " + cid);
                foreach (var rid in ids)
                {
                    Require(rooms.ContainsKey(rid), "Unknown room " + rid + " in " + cid);
                    if (rooms.TryGetValue(rid, out var room))
                        Require(room.Schedulable && room.Kind == kind && room.Capacity >= c.StudentCount,
                                "Invalid room eligibility: " + cid + "/" + rid);
                }
            }
            referencedSessions.AddRange(c.SessionIds);
            Require(c.TimeOptions.Count > 0, "Empty time domain: " + cid);
            foreach (var option in c.TimeOptions)
            {
                optionIds.Add(option.Id);
                Require(option.Meetings.Select(m => m.SessionId).SequenceEqual(c.SessionIds), "Option/session mapping differs: " + option.Id);
                foreach (var m in option.Meetings)
                {
                    var known = m.SessionId is not null && sessions.ContainsKey(m.SessionId);
                    Require(known, "Unknown session in option: " + option.Id);
                    Require(0 <= m.Day && m.Day <= 6 && 0 <= m.StartMinute && m.StartMinute < m.StartMinute + m.DurationMinutes
                            && m.StartMinute + m.DurationMinutes <= 1440, "Invalid meeting bounds: " + option.Id);
                    Require(m.StartMinute % 5 == 0 && m.DurationMinutes % 5 == 0 && m.DurationMinutes > 0, "Invalid source time units: " + option.Id);
                    if (known)
                        Require(m.DurationMinutes == sessions[m.SessionId!].DurationMinutes, "Duration not fixed: " + option.Id);
                }
            }
        }
        Require(optionIds.Count == optionIds.Distinct().Count(), "Duplicate time option IDs");
        Require(referencedSessions.Count == referencedSessions.Distinct().Count() && referencedSessions.ToHashSet().SetEquals(sessions.Keys),
                "Recurring session references are missing or duplicated");
        foreach (var s in sessions.Values)
        {
            Require(classes.ContainsKey(s.ClassId), "Session references unknown class: " + s.Id);
            Require(s.ActiveWeeks.Count == s.ActiveWeeks.Distinct().Count() && s.ActiveWeeks.All(weekSet.Contains), "Invalid active weeks: " + s.Id);
            Require(s.LabWeeks.SequenceEqual(s.LabWeeks.Distinct().Order()) && s.LabWeeks.All(s.ActiveWeeks.Contains), "Invalid lab weeks: " + s.Id);
        }
        foreach (var e in external.Values)
        {
            Require(e.RoomIds.All(rooms.ContainsKey), "Unknown fixed room: " + e.Id);
            Require(e.InstructorIds.All(teachers.ContainsKey), "Unknown fixed instructor: " + e.Id);
            Require(e.StudentGroupIds.All(groups.ContainsKey), "Unknown fixed student group: " + e.Id);
            Require(e.ActiveWeeks.All(weekSet.Contains) && e.Meetings.Count > 0, "Invalid fixed calendar: " + e.Id);
        }
        foreach (var (kind, list) in new[] { ("non_overlap_groups", data.Constraints.NonOverlapGroups), ("same_time_of_day_groups", data.Constraints.SameTimeOfDayGroups) })
            foreach (var constraint in list)
                Require(constraint.ClassIds.All(knownClassIds.Contains), "Unknown class in " + kind + ": " + constraint.SourceConstraintId);
        Require(data.Objectives.OrderedMetrics.SequenceEqual(OrderedMetrics), "Objective priority changed");
        if (errors.Count > 0) return Failed(errors);

        // Necessary local checks: each target against locked classes, not against other targets.
        var extByRoom = new Dictionary<string, List<ExternalClass>>();
        var extByTeacher = new Dictionary<string, List<ExternalClass>>();
        var extByGroup = new Dictionary<string, List<ExternalClass>>();
        foreach (var e in external.Values)
        {
            foreach (var id in e.RoomIds) Bucket(extByRoom, id).Add(e);
            foreach (var id in e.InstructorIds) Bucket(extByTeacher, id).Add(e);
            foreach (var id in e.StudentGroupIds) Bucket(extByGroup, id).Add(e);
        }
        var extraConflicts = new Dictionary<string, HashSet<string>>();
        var sameTimeLinks = new Dictionary<string, HashSet<string>>();
        HashSet<string> Links(Dictionary<string, HashSet<string>> table, string key) =>
            table.TryGetValue(key, out var set) ? set : table[key] = [];
        foreach (var (table, list) in new[] { (extraConflicts, data.Constraints.NonOverlapGroups), (sameTimeLinks, data.Constraints.SameTimeOfDayGroups) })
            foreach (var constraint in list)
            {
                var ids = constraint.ClassIds.ToHashSet();
                foreach (var cid in ids.Where(classes.ContainsKey))
                    Links(table, cid).UnionWith(ids.Where(external.ContainsKey));
            }

        var localImpossible = new List<(string Session, int Week)>();
        var incompleteClasses = new List<string>();
        var completeOptionCount = new JsonObject();
        var studentRuleHard = data.Constraints.ExternalStudentOverlapIsHard;
        foreach (var c in classes.Values)
        {
            var personExternal = new HashSet<string>(Links(extraConflicts, c.Id));
            foreach (var tid in c.InstructorIds)
                if (extByTeacher.TryGetValue(tid, out var list)) personExternal.UnionWith(list.Select(e => e.Id));
            if (studentRuleHard)
                foreach (var gid in c.StudentGroupIds)
                    if (extByGroup.TryGetValue(gid, out var list)) personExternal.UnionWith(list.Select(e => e.Id));
            var links = Links(sameTimeLinks, c.Id);
            var possible = new HashSet<(string, int)>();
            var completeCount = 0;
            foreach (var option in c.TimeOptions)
            {
                var relationOk = links.All(eid => Problem.ContainedTime(option.Meetings[0], external[eid].Meetings[0]));
                var complete = relationOk;
                foreach (var m in option.Meetings)
                {
                    var session = sessions[m.SessionId!];
                    foreach (var week in session.ActiveWeeks)
                    {
                        var peopleFree = relationOk && !personExternal.Any(eid =>
                            external[eid].ActiveWeeks.Contains(week) && external[eid].Meetings.Any(f => Overlap(m, f)));
                        var eligible = session.LabWeeks.Contains(week) ? c.LabRoomIds : c.LectureRoomIds.Concat(c.LabRoomIds);
                        var roomFree = peopleFree && eligible.Any(rid => FitsWindow(m, rooms[rid]) &&
                            !(extByRoom.TryGetValue(rid, out var booked) && booked.Any(f => f.ActiveWeeks.Contains(week) && f.Meetings.Any(x => Overlap(m, x)))));
                        if (roomFree) possible.Add((session.Id, week));
                        else complete = false;
                    }
                }
                if (complete) completeCount++;
            }
            completeOptionCount[c.Id] = completeCount;
            if (completeCount == 0) incompleteClasses.Add(c.Id);
            foreach (var sid in c.SessionIds)
                foreach (var week in sessions[sid].ActiveWeeks)
                    if (!possible.Contains((sid, week))) localImpossible.Add((sid, week));
        }

        var warnings = new List<JsonObject>();
        if (localImpossible.Count > 0)
            warnings.Add(new JsonObject
            {
                ["code"] = "LOCAL_INFEASIBILITY", ["weekly_session_count"] = localImpossible.Count,
                ["meaning"] = "No local placement against fixed background; global completeness is impossible under this model.",
            });
        var syntheticTeachers = teachers.Values.Count(t => t.Origin == "assumption_A05");
        warnings.Add(new JsonObject { ["code"] = "SYNTHETIC_ROOM_TYPES_AND_LABS", ["meaning"] = "Source candidate rooms are modeled as lecture rooms; independent synthetic labs are added." });
        warnings.Add(new JsonObject { ["code"] = "MISSING_SOURCE_INSTRUCTORS", ["classes"] = syntheticTeachers, ["meaning"] = "Unique synthetic instructors add no unknown shared-teacher conflicts." });
        warnings.Add(new JsonObject { ["code"] = "SYNTHETIC_CALENDAR", ["meaning"] = "All target and external classes repeat for the synthetic calendar; source dates masks are provenance only." });
        warnings.Add(new JsonObject
        {
            ["code"] = "ADAPTED_STUDENT_RULE", ["external_student_overlap_is_hard"] = studentRuleHard,
            ["meaning"] = "Known student groups cannot overlap among CS targets; external-student conflicts are hard only in the strict variant. Original student-conflict score and re-sectioning are not reproduced.",
        });
        warnings.Add(new JsonObject { ["code"] = "GLOBAL_FEASIBILITY_NOT_PROVEN", ["meaning"] = "Local checks do not jointly assign target classes or certify a complete timetable." });

        var labCounts = new Dictionary<int, int>();
        foreach (var s in sessions.Values)
            foreach (var w in s.LabWeeks) labCounts[w] = labCounts.GetValueOrDefault(w) + 1;
        var summary = new JsonObject
        {
            ["target_classes"] = classes.Count,
            ["source_course_offerings"] = classes.Values.Select(c => c.CourseId).Distinct().Count(),
            ["recurring_sessions"] = sessions.Count,
            ["weeks"] = weeks.Count,
            ["weekly_sessions"] = sessions.Values.Sum(s => s.ActiveWeeks.Count),
            ["lab_required_weekly_sessions"] = sessions.Values.Sum(s => s.LabWeeks.Count),
            ["lab_required_minutes"] = sessions.Values.Sum(s => (long)s.LabWeeks.Count * s.DurationMinutes),
            ["mixed_recurring_sessions"] = sessions.Values.Count(s => s.LabWeeks.Count > 0),
            ["lecture_only_recurring_sessions"] = sessions.Values.Count(s => s.LabWeeks.Count == 0),
            ["source_schedulable_lecture_rooms"] = rooms.Values.Count(r => r.Kind == "lecture" && r.Schedulable),
            ["synthetic_computer_labs"] = rooms.Values.Count(r => r.Kind == "computer_lab"),
            ["background_only_room_records"] = rooms.Values.Count(r => !r.Schedulable),
            ["committed_classes"] = external.Count,
            ["synthetic_instructor_classes"] = syntheticTeachers,
            ["student_roster_groups"] = groups.Count,
            ["known_students_in_target_rosters"] = sourceStudents.Count,
            ["classes_without_known_enrollment"] = classes.Values.Count(c => c.KnownEnrolledStudentCount == 0),
            ["classes_without_locally_complete_time_option"] = incompleteClasses.Count,
            ["weekly_sessions_without_any_local_placement"] = localImpossible.Count,
        };
        var perWeek = new JsonObject();
        foreach (var w in weeks) perWeek[w.ToString(System.Globalization.CultureInfo.InvariantCulture)] = labCounts.GetValueOrDefault(w);
        var feasibility = new JsonObject
        {
            ["scope"] = "Against external room/instructor reservations, conditional external student rule, room windows, capacity/type and fixed SAME_TIME only; other targets not jointly scheduled.",
            ["complete_time_option_counts"] = completeOptionCount,
            ["classes_without_complete_time_option"] = new JsonArray(incompleteClasses.Select(id => (JsonNode)id).ToArray()),
            ["weekly_sessions_without_any_placement"] = new JsonArray(localImpossible
                .Select(x => (JsonNode)new JsonObject { ["session_id"] = x.Session, ["week"] = x.Week }).ToArray()),
        };
        return new InputReport("passed_with_warnings", errors, warnings, summary, perWeek, feasibility);
    }
}
