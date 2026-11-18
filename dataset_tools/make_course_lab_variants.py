"""Build course-level Lab variants of the main dataset. Standard library only.

    python dataset_tools/make_course_lab_variants.py

The main dataset draws Lab need per recurring session (assumption A10): 60% of sessions, each with
its own 4 random Lab weeks. That spreads Lab need over 42 of the 44 courses and gives sections of
one course different Lab weeks. These variants decide Lab need per course instead:

- courses are shuffled with a fixed seed and taken in that order until the number of sessions with
  Lab need is as close as possible to the main dataset's (134 of 223);
- every session of a chosen course shares that course's Lab weeks; other courses never need a Lab;
- each chosen course gets one random order of the 15 weeks, and level ``n`` uses the first ``n`` of
  it, so the levels are nested (the Lab weeks at level 4 are a subset of those at level 6).

Levels are the number of Lab weeks per Lab course. Everything else (classes, rooms, Labs, time
options, background classes, constraints) is unchanged.
Output: data/variants/fall-cs-course-labs-w{NN}.json.gz
"""
import gzip
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from input_validation import validate  # noqa: E402

SOURCE = ROOT / 'data' / 'fall-cs.json.gz'
OUT = ROOT / 'data' / 'variants'
SEED = 20261118
LEVELS = (1, 2, 4, 6, 8, 10, 12, 15)


def plan(data):
    """Return {course_id: week order} for the courses that need a Lab."""
    course_of = {c['id']: c['course_id'] for c in data['classes']}
    sessions = {}
    for s in data['recurring_sessions']:
        sessions[course_of[s['class_id']]] = sessions.get(course_of[s['class_id']], 0) + 1
    target = sum(1 for s in data['recurring_sessions'] if s['lab_weeks'])
    rng = random.Random(SEED)
    order = sorted(sessions)
    rng.shuffle(order)
    totals = [sum(sessions[c] for c in order[:k]) for k in range(len(order) + 1)]
    count = min(range(len(totals)), key=lambda k: (abs(totals[k] - target), k))
    weeks = sorted(data['calendar']['week_ids'])
    return {c: rng.sample(weeks, len(weeks)) for c in sorted(order[:count])}


def variant(data, level):
    out = json.loads(json.dumps(data))
    course_of = {c['id']: c['course_id'] for c in out['classes']}
    lab_courses = plan(data)
    for s in out['recurring_sessions']:
        order = lab_courses.get(course_of[s['class_id']])
        s['lab_weeks'] = sorted(order[:level]) if order else []
        assert set(s['lab_weeks']) <= set(s['active_weeks'])
        if order:
            s['lab_requirement_origin'] = 'synthetic_A10_course_level'
        else:
            s.pop('lab_requirement_origin', None)
    out['dataset_id'] = f"{data['dataset_id']}-course-labs-w{level:02d}"
    out['generator'] = {**data.get('generator', {}), 'course_lab_variant': {
        'base_dataset_id': data['dataset_id'], 'lab_weeks_per_course': level, 'seed': SEED,
        'lab_course_ids': sorted(lab_courses),
        'rule': 'Lab need is decided per course: all sessions of a Lab course share its Lab weeks; '
                'levels are nested prefixes of one week order per course'}}
    return out


def main():
    data = json.loads(gzip.decompress(SOURCE.read_bytes()).decode())
    OUT.mkdir(parents=True, exist_ok=True)
    for level in LEVELS:
        out = variant(data, level)
        report = validate(out)
        if report['errors']:
            raise SystemExit(f'w{level:02d}: invalid: {report["errors"][:5]}')
        body = json.dumps(out, ensure_ascii=False, indent=1)
        path = OUT / f'fall-cs-course-labs-w{level:02d}.json.gz'
        path.write_bytes(gzip.compress(body.encode(), mtime=0))
        mixed = [s for s in out['recurring_sessions'] if s['lab_weeks']]
        hours = sum(s['duration_minutes'] * len(s['lab_weeks']) for s in mixed) / 60
        print(path.relative_to(ROOT), 'sha256', hashlib.sha256(body.encode()).hexdigest()[:16],
              'lab sessions', len(mixed), 'lab hours/term', hours, 'warnings', len(report['warnings']))


if __name__ == '__main__':
    main()
