"""Write validator_cases.json: hand-made invalid solutions and Python's audit of each.

    python dotnet/tests/Timetabling.Engine.Tests/Fixtures/make_validator_cases.py

Each case starts from a stored Greedy solution (experiments/final, seed 1001, weekly or fixed room mode)
and lists its edits (set_all_rooms, then set_rows, append_rows, set_options, set_fields), so the C#
test rebuilds the same solution. The expected value is the full output of
engine/solution_validator.py audit_solution.
"""
import copy
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'engine'))
from solution_validator import audit_solution  # noqa: E402


def load():
    with gzip.open(ROOT / 'experiments' / 'final' / 'experiment.json.gz', 'rt', encoding='utf-8') as f:
        batch = json.load(f)['batch']
    with gzip.open(ROOT / 'data' / 'fall-cs.json.gz', 'rt', encoding='utf-8') as f:
        data = json.load(f)
    bases = {}
    for r in batch['results']:
        if r['algorithm'] == 'greedy' and r['seed'] == 1001:
            bases[r['room_mode']] = r['solution']
    return data, bases


def apply(solution, case):
    s = copy.deepcopy(solution)
    rows = s['weekly_room_assignments']
    if 'set_all_rooms' in case:
        for row in rows:
            row['room_id'] = case['set_all_rooms']
    for index, row in case.get('set_rows', []):
        rows[index] = row
    rows.extend(case.get('append_rows', []))
    s['class_time_options'].update(case.get('set_options', {}))
    s.update(case.get('set_fields', {}))
    return s


class Finder:
    """Indexes a base solution so edits can target one violation at a time."""

    def __init__(self, data, solution):
        self.data = data
        self.solution = solution
        self.classes = {c['id']: c for c in data['classes']}
        self.sessions = {s['id']: s for s in data['recurring_sessions']}
        self.rooms = {r['id']: r for r in data['rooms']}
        self.meeting = {}
        for cid, oid in solution['class_time_options'].items():
            if oid is None:
                continue
            option = next(o for o in self.classes[cid]['time_options'] if o['id'] == oid)
            for m in option['meetings']:
                self.meeting[m['session_id']] = m
        self.busy = defaultdict(list)  # (room, week, day) -> [(start, end)]
        for row in solution['weekly_room_assignments']:
            m = self.meeting[row['session_id']]
            self.busy[(row['room_id'], row['week'], m['day'])].append((m['start_minute'], m['start_minute'] + m['duration_minutes']))
        for e in data['external_classes']:
            for week in e['active_weeks']:
                for m in e['meetings']:
                    for rid in e['room_ids']:
                        self.busy[(rid, week, m['day'])].append((m['start_minute'], m['start_minute'] + m['duration_minutes']))

    def free(self, rid, week, m):
        start, end = m['start_minute'], m['start_minute'] + m['duration_minutes']
        return all(e <= start or end <= s for s, e in self.busy[(rid, week, m['day'])])

    def available(self, rid, m):
        end = m['start_minute'] + m['duration_minutes']
        return any(w['day'] == m['day'] and w['start_minute'] <= m['start_minute'] and end <= w['end_minute']
                   for w in self.rooms[rid]['availability'])

    def rows(self):
        for index, row in enumerate(self.solution['weekly_room_assignments']):
            s = self.sessions[row['session_id']]
            yield index, row, s, self.classes[s['class_id']], self.meeting[row['session_id']]


def codes(result):
    return Counter(v['code'] for v in result['violations'])


def build(data, bases):
    weekly, fixed = Finder(data, bases['weekly']), Finder(data, bases['fixed'])
    cases = []

    def add(name, base, case, want=None, audit_mode=None):
        case = {'name': name, 'base': base, 'audit_mode': audit_mode or base, **case}
        result = audit_solution(data, apply(bases[base], case), case['audit_mode'])
        found = set(codes(result))
        if want is not None and not set(want) <= found:
            raise SystemExit(f'{name}: expected {want}, audit found {sorted(found)}')
        case['expected'] = result
        cases.append(case)
        print(f'{name:28s} violation_count={result["violation_count"]:4d} {dict(codes(result))}')

    rows = bases['weekly']['weekly_room_assignments']
    add('duplicate_session_week', 'weekly', {'append_rows': [dict(rows[0])]}, {'DUPLICATE_SESSION_WEEK'})

    # A free, available, schedulable lecture room outside the class's room domain, in a non-Lab week.
    def wrong_domain():
        for index, row, s, c, m in weekly.rows():
            if row['week'] in s['lab_weeks']:
                continue
            domain = set(c['lecture_room_ids']) | set(c['lab_room_ids'])
            for rid, room in weekly.rooms.items():
                if (rid not in domain and room['schedulable'] and room['kind'] == 'lecture'
                        and room['capacity'] >= c['student_count'] and weekly.available(rid, m) and weekly.free(rid, row['week'], m)):
                    return index, {**row, 'room_id': rid}
        raise SystemExit('no wrong-domain room found')
    add('room_domain', 'weekly', {'set_rows': [wrong_domain()]}, {'ROOM_DOMAIN'})

    def too_small():
        for index, row, s, c, m in weekly.rows():
            if row['week'] in s['lab_weeks']:
                continue
            for rid, room in weekly.rooms.items():
                if (room['schedulable'] and room['kind'] == 'lecture' and room['capacity'] < c['student_count']
                        and weekly.available(rid, m) and weekly.free(rid, row['week'], m)):
                    return index, {**row, 'room_id': rid}
        raise SystemExit('no small room found')
    add('capacity', 'weekly', {'set_rows': [too_small()]}, {'CAPACITY'})

    # Move a row into a room that an external (background) class holds at the same time. The decoder never
    # does this, so prefer a room inside the class's domain and fall back to any room an external class uses.
    def onto_background(in_domain):
        for index, row, s, c, m in weekly.rows():
            if row['week'] in s['lab_weeks']:
                continue
            pool = c['lecture_room_ids'] if in_domain else sorted({r for e in data['external_classes'] for r in e['room_ids']})
            for rid in pool:
                if rid != row['room_id'] and rid in weekly.rooms and not weekly.free(rid, row['week'], m):
                    start, end = m['start_minute'], m['start_minute'] + m['duration_minutes']
                    for e in data['external_classes']:
                        if rid in e['room_ids'] and row['week'] in e['active_weeks'] and any(
                                f['day'] == m['day'] and f['start_minute'] < end and start < f['start_minute'] + f['duration_minutes']
                                for f in e['meetings']):
                            return index, {**row, 'room_id': rid}
        return None
    target = onto_background(True) or onto_background(False)
    if target is None:
        raise SystemExit('no background overlap found')
    add('room_overlap_background', 'weekly', {'set_rows': [target]}, {'ROOM_OVERLAP'})

    def fixed_change(lab_session):
        by_session = defaultdict(list)
        for index, row, s, c, m in fixed.rows():
            by_session[row['session_id']].append((index, row, s, c, m))
        for sid, items in by_session.items():
            s = items[0][2]
            if len(items) < 2 or bool(s['lab_weeks']) != lab_session:
                continue
            for index, row, s, c, m in items:
                if row['week'] in s['lab_weeks']:
                    continue
                pool = c['lecture_room_ids'] if lab_session else c['lecture_room_ids'] + c['lab_room_ids']
                for rid in pool:
                    if rid != row['room_id'] and fixed.available(rid, m) and fixed.free(rid, row['week'], m):
                        return index, {**row, 'room_id': rid}
        raise SystemExit('no fixed-mode change found')
    add('fixed_room_changed', 'fixed', {'set_rows': [fixed_change(False)]}, {'FIXED_ROOM_CHANGED'})
    add('fixed_room_not_lab', 'fixed', {'set_rows': [fixed_change(True)]}, {'FIXED_ROOM_NOT_LAB', 'FIXED_ROOM_CHANGED'})

    # Reference and schema problems.
    first_class = data['classes'][0]['id']
    session_rows = [i for i, row, s, c, m in weekly.rows() if s['class_id'] == first_class]
    add('references', 'weekly', {
        'set_options': {'NO_SUCH_CLASS': 'x', data['classes'][1]['id']: 'NO_SUCH_OPTION'},
        'append_rows': [{'session_id': 'NO_SUCH_SESSION', 'week': 1, 'room_id': rows[0]['room_id']},
                        {'session_id': rows[0]['session_id'], 'week': 1, 'room_id': 'NO_SUCH_ROOM'},
                        {'session_id': rows[0]['session_id'], 'week': 99, 'room_id': rows[0]['room_id']}],
        'set_fields': {'dataset_id': 'another-dataset'},
    }, {'UNKNOWN_CLASS', 'TIME_OPTION', 'ASSIGNMENT_REFERENCE', 'INACTIVE_WEEK', 'DATASET_ID', 'MISSING_TIME'})
    add('missing_time', 'weekly', {'set_options': {first_class: None}}, {'MISSING_TIME'} if session_rows else None)

    # Every row in one Lab room: the 200-entry cap and violations_truncated.
    lab = next(r['id'] for r in data['rooms'] if r['kind'] == 'computer_lab')
    add('one_room_truncated', 'weekly', {'set_all_rooms': lab}, {'ROOM_OVERLAP'})
    # A weekly solution audited as fixed: declared-mode mismatch plus per-session room changes.
    add('weekly_audited_as_fixed', 'weekly', {}, {'ROOM_MODE', 'FIXED_ROOM_CHANGED'}, audit_mode='fixed')
    add('unknown_room_mode', 'weekly', {}, {'ROOM_MODE'}, audit_mode='nightly')
    return cases


def main():
    data, bases = load()
    cases = build(data, bases)
    null_case = audit_solution(data, None, 'weekly')
    path = Path(__file__).with_name('validator_cases.json')
    path.write_text(json.dumps({'cases': cases, 'null_solution': null_case}, indent=1) + '\n', encoding='utf-8')
    print('Saved', path)


if __name__ == '__main__':
    main()
