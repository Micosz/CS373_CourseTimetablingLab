"""Build the Lab-weeks variants of the main dataset. Standard library only.

    python dataset_tools/make_lab_week_variants.py

The main dataset decides Lab need per course (assumption A10): every section of the practice part
of a Lab course shares that course's Lab weeks, 4 of the 15 teaching weeks. These variants keep the
same Lab courses and practice parts and change only how many weeks each Lab course needs a Lab.

The main dataset stores one random order of the 15 weeks per Lab course (``generator.lab_plan``),
and level ``n`` uses the first ``n`` weeks of it. So the levels are nested (the Lab weeks at
level 4 are a subset of those at level 6) and level 4 has the Lab weeks of the main dataset.

Everything else (classes, rooms, Labs, time options, background classes, constraints) is unchanged.
Output: data/variants/fall-cs-labweeks-w{NN}.json.gz
"""
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from input_validation import validate  # noqa: E402

SOURCE = ROOT / 'data' / 'fall-cs.json.gz'
OUT = ROOT / 'data' / 'variants'
LEVELS = (1, 2, 4, 6, 8, 10, 12, 15)


def variant(data, level):
    out = json.loads(json.dumps(data))
    plan = data['generator']['lab_plan']
    practice = {c['id'] for c in out['classes']
                if plan['practice_subparts'].get(c['course_id']) == c['source_subpart_id']}
    course_of = {c['id']: c['course_id'] for c in out['classes']}
    for s in out['recurring_sessions']:
        order = plan['lab_courses'].get(course_of[s['class_id']])
        s['lab_weeks'] = sorted(order[:level]) if order and s['class_id'] in practice else []
        assert set(s['lab_weeks']) <= set(s['active_weeks'])
    out['dataset_id'] = f"{data['dataset_id']}-labweeks-w{level:02d}"
    out['generator'] = {**data['generator'], 'lab_week_variant': {
        'base_dataset_id': data['dataset_id'], 'lab_weeks_per_lab_course': level,
        'rule': 'same Lab courses and practice parts as the base dataset; each Lab course uses the '
                'first n weeks of its week order in generator.lab_plan, so levels are nested'}}
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
        path = OUT / f'fall-cs-labweeks-w{level:02d}.json.gz'
        path.write_bytes(gzip.compress(body.encode(), mtime=0))
        mixed = [s for s in out['recurring_sessions'] if s['lab_weeks']]
        hours = sum(s['duration_minutes'] * len(s['lab_weeks']) for s in mixed) / 60
        print(path.relative_to(ROOT), 'sha256', hashlib.sha256(body.encode()).hexdigest()[:16],
              'lab sessions', len(mixed), 'lab hours/term', hours, 'warnings', len(report['warnings']))


if __name__ == '__main__':
    main()
