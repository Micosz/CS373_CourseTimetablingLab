using System.Diagnostics;

namespace Timetabling.Engine;

/// <summary>
/// Shared deterministic decoder (port of engine/lab_core.py). Every tie-break, iteration order and
/// strict comparison follows the Python code so the same genome decodes to the same schedule.
/// Thread-safe: a decode allocates its own working state, so one Problem can serve parallel runs.
/// </summary>
public sealed class Problem
{
    public const string Version = "1.0.0";

    /// <summary>One week of one meeting of a compiled time option.</summary>
    public readonly record struct Placement(int Session, int Week, SlotRange Mask, int[] Allowed, int Duration, bool NeedLab);

    public sealed record SessionPlan(int Session, Placement[] Rows, int[] Rooms);

    public sealed record CompiledOption(string Id, Meeting First, bool RelationOk, Placement[] Placements, SessionPlan[] BySession, int StaticPossible);

    public Dataset Data { get; }
    public string[] ClassIds { get; }
    public string[] SessionIds { get; }
    public Room[] Rooms { get; }
    public CompiledOption[][] Options { get; }
    public int[] BaseOrder { get; }
    public long TotalWeekly { get; }
    public long MaxLabMinutes { get; }
    public long MaxChanges { get; }
    public long MinuteWeight { get; }
    public long UnassignedWeight { get; }

    readonly int[][] conflicts, sameTimes;
    readonly int[] roomRank;
    readonly int maxWeek;

    public Problem(Dataset data)
    {
        Data = data;
        ClassIds = data.Classes.Select(c => c.Id).ToArray();
        SessionIds = data.RecurringSessions.Select(s => s.Id).ToArray();
        Rooms = data.Rooms.ToArray();
        var classIndex = Index(ClassIds);
        var sessionIndex = Index(SessionIds);
        var roomIndex = Index(Rooms.Select(r => r.Id));
        var external = data.ExternalClasses.ToDictionary(e => e.Id);
        // Python compares room ids as str; ordinal ranks reproduce that order for every tie-break.
        roomRank = new int[Rooms.Length];
        var byName = Enumerable.Range(0, Rooms.Length).OrderBy(i => Rooms[i].Id, StringComparer.Ordinal).ToArray();
        for (var r = 0; r < byName.Length; r++) roomRank[byName[r]] = r;

        var sessions = data.RecurringSessions;
        TotalWeekly = sessions.Sum(s => (long)s.ActiveWeeks.Count);
        MaxLabMinutes = sessions.Sum(s => (long)s.DurationMinutes * s.ActiveWeeks.Count);
        MaxChanges = sessions.Sum(s => (long)Math.Max(0, s.ActiveWeeks.Count - 1));
        MinuteWeight = MaxChanges + 1;
        UnassignedWeight = (MaxLabMinutes + 1) * MinuteWeight;
        maxWeek = new[] { data.Calendar.WeekIds.DefaultIfEmpty(1).Max() }
            .Concat(sessions.SelectMany(s => s.ActiveWeeks)).Concat(data.ExternalClasses.SelectMany(e => e.ActiveWeeks)).Max();

        int n = ClassIds.Length;
        var conflictSets = Enumerable.Range(0, n).Select(_ => new HashSet<int>()).ToArray();
        var sameSets = Enumerable.Range(0, n).Select(_ => new HashSet<int>()).ToArray();
        var fixedPeople = Enumerable.Range(0, n).Select(_ => NewSet()).ToArray();
        var fixedRooms = Enumerable.Range(0, Rooms.Length).Select(_ => NewSet()).ToArray();

        var teachers = new Dictionary<string, HashSet<int>>();
        var groups = new Dictionary<string, HashSet<int>>();
        for (var c = 0; c < n; c++)
        {
            foreach (var t in data.Classes[c].InstructorIds) Bucket(teachers, t).Add(c);
            foreach (var g in data.Classes[c].StudentGroupIds) Bucket(groups, g).Add(c);
        }
        foreach (var table in new[] { teachers, groups })
            foreach (var ids in table.Values)
                foreach (var c in ids)
                    foreach (var other in ids) if (other != c) conflictSets[c].Add(other);

        var externalMasks = new Dictionary<string, SlotSet>();
        foreach (var e in data.ExternalClasses)
        {
            var mask = NewSet();
            foreach (var week in e.ActiveWeeks)
                foreach (var m in e.Meetings) mask.Add(SlotRange.Of(m, week));
            externalMasks[e.Id] = mask;
            foreach (var rid in e.RoomIds)
                if (roomIndex.TryGetValue(rid, out var r)) fixedRooms[r].UnionWith(mask);
            var related = new HashSet<int>();
            foreach (var t in e.InstructorIds)
                if (teachers.TryGetValue(t, out var ids)) related.UnionWith(ids);
            if (data.Constraints.ExternalStudentOverlapIsHard)
                foreach (var g in e.StudentGroupIds)
                    if (groups.TryGetValue(g, out var ids)) related.UnionWith(ids);
            foreach (var c in related) fixedPeople[c].UnionWith(mask);
        }
        foreach (var g in data.Constraints.NonOverlapGroups)
        {
            var targets = g.ClassIds.Where(classIndex.ContainsKey).Select(id => classIndex[id]).ToHashSet();
            var externals = g.ClassIds.Where(external.ContainsKey).Distinct().ToArray();
            foreach (var c in targets)
            {
                foreach (var other in targets) if (other != c) conflictSets[c].Add(other);
                foreach (var eid in externals) fixedPeople[c].UnionWith(externalMasks[eid]);
            }
        }
        var fixedSame = Enumerable.Range(0, n).Select(_ => new List<Meeting>()).ToArray();
        foreach (var g in data.Constraints.SameTimeOfDayGroups)
        {
            var targets = g.ClassIds.Where(classIndex.ContainsKey).Select(id => classIndex[id]).ToHashSet();
            var externals = g.ClassIds.Where(external.ContainsKey).Distinct().ToArray();
            foreach (var c in targets)
            {
                foreach (var other in targets) if (other != c) sameSets[c].Add(other);
                fixedSame[c].AddRange(externals.Select(eid => external[eid].Meetings[0]));
            }
        }
        conflicts = conflictSets.Select(s => s.ToArray()).ToArray();
        sameTimes = sameSets.Select(s => s.ToArray()).ToArray();

        Options = new CompiledOption[n][];
        for (var c = 0; c < n; c++)
        {
            var cls = data.Classes[c];
            var labRooms = cls.LabRoomIds.Select(id => roomIndex[id]).ToHashSet();
            var labDomain = cls.LabRoomIds.Select(id => roomIndex[id]).ToArray();
            var mixedDomain = cls.LectureRoomIds.Concat(cls.LabRoomIds).Select(id => roomIndex[id]).ToArray();
            var compiled = new List<CompiledOption>();
            foreach (var option in cls.TimeOptions)
            {
                var first = option.Meetings[0];
                var relationOk = fixedSame[c].All(other => ContainedTime(first, other));
                var placements = new List<Placement>();
                foreach (var m in option.Meetings)
                {
                    var sid = sessionIndex[m.SessionId!];
                    var s = sessions[sid];
                    foreach (var week in s.ActiveWeeks.OrderBy(w => w))
                    {
                        var mask = SlotRange.Of(m, week);
                        var needLab = s.LabWeeks.Contains(week);
                        var domain = needLab ? labDomain : mixedDomain;
                        var allowed = domain.Where(r => Available(m, Rooms[r]) && !fixedRooms[r].Intersects(mask)).ToArray();
                        var peopleOk = relationOk && !fixedPeople[c].Intersects(mask);
                        placements.Add(new Placement(sid, week, mask, peopleOk ? allowed : [], s.DurationMinutes, needLab));
                    }
                }
                var bySession = new List<SessionPlan>();
                foreach (var m in option.Meetings)
                {
                    var sid = sessionIndex[m.SessionId!];
                    var rows = placements.Where(x => x.Session == sid).ToArray();
                    var needsLab = rows.Any(x => x.NeedLab);
                    var seen = new List<int>();
                    foreach (var x in rows)
                        foreach (var r in x.Allowed)
                            if (!seen.Contains(r) && (!needsLab || labRooms.Contains(r))) seen.Add(r);
                    bySession.Add(new SessionPlan(sid, rows, seen.ToArray()));
                }
                compiled.Add(new CompiledOption(option.Id, first, relationOk, placements.ToArray(), bySession.ToArray(),
                    placements.Count(x => x.Allowed.Length > 0)));
            }
            Options[c] = compiled.ToArray();
        }
        BaseOrder = Enumerable.Range(0, n)
            .OrderBy(c => Options[c].Sum(o => o.StaticPossible))
            .ThenBy(c => Options[c].Length)
            .ThenBy(c => -conflicts[c].Length)
            .ThenBy(c => ClassIds[c], StringComparer.Ordinal)
            .ToArray();
    }

    SlotSet NewSet() => SlotSet.ForWeeks(maxWeek);

    static Dictionary<string, int> Index(IEnumerable<string> ids)
    {
        var map = new Dictionary<string, int>();
        foreach (var id in ids) map[id] = map.Count;
        return map;
    }

    static HashSet<int> Bucket(Dictionary<string, HashSet<int>> table, string key) =>
        table.TryGetValue(key, out var set) ? set : table[key] = [];

    /// <summary>UniTime SAME_TIME: the shorter meeting lies inside the longer one (stable on equal duration).</summary>
    public static bool ContainedTime(Meeting a, Meeting b)
    {
        var (shorter, longer) = b.DurationMinutes < a.DurationMinutes ? (b, a) : (a, b);
        return longer.StartMinute <= shorter.StartMinute && shorter.EndMinute <= longer.EndMinute;
    }

    public static bool Available(Meeting m, Room room) =>
        room.Availability.Any(w => w.Day == m.Day && w.StartMinute <= m.StartMinute && m.EndMinute <= w.EndMinute);

    public Genome InitialGenome() => new((int[])BaseOrder.Clone(), new int[ClassIds.Length]);

    public Genome RandomGenome(PyRandom rng)
    {
        var order = Enumerable.Range(0, ClassIds.Length).ToList();
        rng.Shuffle(order);
        var preferences = new int[ClassIds.Length];
        for (var c = 0; c < preferences.Length; c++) preferences[c] = rng.RandRange(Options[c].Length);
        return new Genome(order.ToArray(), preferences);
    }

    public Genome Mutate(Genome genome, PyRandom rng, double rate = 1.0)
    {
        var order = (int[])genome.Order.Clone();
        var preferences = (int[])genome.TimePreferences.Clone();
        if (order.Length > 1 && rng.Random() < rate)
        {
            var pair = rng.SampleRange(order.Length, 2);
            (order[pair[0]], order[pair[1]]) = (order[pair[1]], order[pair[0]]);
        }
        if (order.Length > 0 && rng.Random() < rate)
        {
            var c = rng.Choice(order);
            preferences[c] = rng.RandRange(Options[c].Length);
        }
        return new Genome(order, preferences);
    }

    readonly record struct Record(int Session, int Week, int Room, SlotRange Mask);

    List<Record> FixedRecords(CompiledOption option, SlotSet peopleBusy, SlotSet[] roomBusy, out long localLab)
    {
        var records = new List<Record>();
        localLab = 0;
        foreach (var plan in option.BySession)
        {
            (int Weeks, long Lab, int Capacity, int Rank)? bestKey = null;
            int bestRoom = -1;
            List<(int Week, SlotRange Mask)>? bestWeeks = null;
            foreach (var r in plan.Rooms)
            {
                var busy = roomBusy[r];
                var isLab = Rooms[r].IsLab;
                var weeks = new List<(int, SlotRange)>();
                long lab = 0;
                foreach (var row in plan.Rows)
                {
                    if (peopleBusy.Intersects(row.Mask) || busy.Intersects(row.Mask) || Array.IndexOf(row.Allowed, r) < 0) continue;
                    weeks.Add((row.Week, row.Mask));
                    if (isLab && !row.NeedLab) lab += row.Duration;
                }
                if (weeks.Count == 0) continue;
                var key = (-weeks.Count, lab, Rooms[r].Capacity, roomRank[r]);
                if (bestKey is null || key.CompareTo(bestKey.Value) < 0)
                {
                    bestKey = key; bestRoom = r; bestWeeks = weeks;
                }
            }
            if (bestKey is not null)
            {
                localLab += bestKey.Value.Lab;
                foreach (var (week, mask) in bestWeeks!) records.Add(new Record(plan.Session, week, bestRoom, mask));
            }
        }
        return records;
    }

    /// <summary>Port of Problem.decode. <paramref name="deadline"/> is a Stopwatch timestamp or null.</summary>
    public Candidate Decode(Genome genome, long? deadline = null, string roomMode = RoomModes.Weekly)
    {
        if (!RoomModes.IsValid(roomMode)) throw new ArgumentException("room_mode must be one of weekly, fixed");
        var fixedMode = roomMode == RoomModes.Fixed;
        int n = ClassIds.Length;
        var order = genome.Order;
        if (order.Length != n || order.Distinct().Count() != n || order.Any(c => c < 0 || c >= n))
            throw new ArgumentException("Genome order must be a permutation of all target class IDs");
        var preferences = genome.TimePreferences;
        if (preferences.Length != n) throw new ArgumentException("time_preferences must contain every target class");
        for (var c = 0; c < n; c++)
            if (preferences[c] < 0 || preferences[c] >= Options[c].Length)
                throw new ArgumentException("Invalid time preference for " + ClassIds[c]);

        var roomBusy = Rooms.Select(_ => NewSet()).ToArray();
        var classBusy = new SlotSet?[n];
        var selected = new CompiledOption?[n];
        var decided = new bool[n];
        var assignments = new List<Assignment>();
        long assigned = 0, labMinutes = 0, changes = 0;
        var peopleBusy = NewSet();
        var previous = new Dictionary<int, int>();
        foreach (var c in order)
        {
            if (deadline is long d && Stopwatch.GetTimestamp() >= d) throw new SearchStoppedException("time_limit");
            peopleBusy.Clear();
            foreach (var other in conflicts[c])
                if (classBusy[other] is { } busy) peopleBusy.UnionWith(busy);
            (long Records, long Lab, long Changes)? bestKey = null;
            CompiledOption? bestOption = null;
            List<Record>? bestRecords = null;
            var options = Options[c];
            var start = preferences[c];
            for (var offset = 0; offset < options.Length; offset++)
            {
                var option = options[(start + offset) % options.Length];
                if (!option.RelationOk) continue;
                var sameTimeBroken = false;
                foreach (var other in sameTimes[c])
                    if (decided[other] && selected[other] is { } o && !ContainedTime(option.First, o.First)) { sameTimeBroken = true; break; }
                if (sameTimeBroken) continue;
                List<Record> records;
                long localLab = 0, localChanges = 0;
                if (fixedMode)
                {
                    records = FixedRecords(option, peopleBusy, roomBusy, out localLab);
                }
                else
                {
                    records = [];
                    previous.Clear();
                    foreach (var p in option.Placements)
                    {
                        if (peopleBusy.Intersects(p.Mask)) continue;
                        int best = -1;
                        (int Lab, int Changed, int Capacity, int Rank) bestRoomKey = default;
                        foreach (var r in p.Allowed)
                        {
                            if (roomBusy[r].Intersects(p.Mask)) continue;
                            var key = (!p.NeedLab && Rooms[r].IsLab ? 1 : 0,
                                       previous.TryGetValue(p.Session, out var prev) && prev != r ? 1 : 0,
                                       Rooms[r].Capacity, roomRank[r]);
                            if (best < 0 || key.CompareTo(bestRoomKey) < 0) { best = r; bestRoomKey = key; }
                        }
                        if (best < 0) continue;
                        localLab += p.Duration * bestRoomKey.Lab;
                        localChanges += bestRoomKey.Changed;
                        previous[p.Session] = best;
                        records.Add(new Record(p.Session, p.Week, best, p.Mask));
                    }
                }
                var candidateKey = ((long)-records.Count, localLab, localChanges);
                if (bestKey is null || candidateKey.CompareTo(bestKey.Value) < 0)
                {
                    bestKey = candidateKey; bestOption = option; bestRecords = records;
                }
            }
            decided[c] = true;
            if (bestKey is null || bestRecords!.Count == 0) { selected[c] = null; continue; }
            selected[c] = bestOption;
            // used_mask in Python is the union of the chosen records' masks.
            var used = NewSet();
            classBusy[c] = used;
            foreach (var rec in bestRecords)
            {
                used.Add(rec.Mask);
                roomBusy[rec.Room].Add(rec.Mask);
                assignments.Add(new Assignment(SessionIds[rec.Session], rec.Week, Rooms[rec.Room].Id));
            }
            assigned += bestRecords.Count;
            labMinutes += bestKey.Value.Lab;
            changes += bestKey.Value.Changes;
        }
        var objectives = new Objectives(TotalWeekly - assigned, labMinutes, changes);
        var energy = objectives.Unassigned * UnassignedWeight + objectives.LabMinutes * MinuteWeight + objectives.RoomChanges;
        var timeOptions = new Dictionary<string, string?>();
        for (var c = 0; c < n; c++) timeOptions[ClassIds[c]] = selected[c]?.Id;
        var solution = new Solution { DatasetId = Data.DatasetId, RoomMode = roomMode, ClassTimeOptions = timeOptions, WeeklyRoomAssignments = assignments };
        return new Candidate(genome.Copy(), solution, objectives, energy);
    }
}
