"""Build Lab-week pattern variants of the main dataset (issue #30). Standard library only.

    python dataset_tools/make_pattern_variants.py

The main dataset gives each Lab course 4 Lab weeks drawn at random from 15 (assumption A10). Real
courses often follow a pattern instead, so these variants keep the same sessions with Lab weeks
(and the same number of Lab weeks) and change only which weeks:

- ``consecutive``: weeks in a row, the first week drawn uniformly
- ``alternate``: every other week (s, s+2, s+4, ...), s drawn uniformly

The start is drawn once per course, so every section of a course still shares its Lab weeks.
Everything else (classes, rooms, Labs, time options, background classes, constraints) is
unchanged. Output: data/variants/fall-cs-pattern-{name}.json.gz
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
SEED = 20261114
PATTERNS = {
    'consecutive': lambda rng, n, last: [s + i for s in [rng.randint(1, last - n + 1)] for i in range(n)],
    'alternate': lambda rng, n, last: [s + 2 * i for s in [rng.randint(1, last - 2 * (n - 1))] for i in range(n)],
}


def variant(data, name):
    out = json.loads(json.dumps(data))
    rng = random.Random(f'{SEED}-{name}')
    course_of = {c['id']: c['course_id'] for c in out['classes']}
    by_course = {}
    for s in out['recurring_sessions']:
        if s['lab_weeks']:
            by_course.setdefault(course_of[s['class_id']], []).append(s)
    last = max(out['calendar']['week_ids'])
    for course in sorted(by_course):
        counts = {len(s['lab_weeks']) for s in by_course[course]}
        assert len(counts) == 1, course
        weeks = PATTERNS[name](rng, counts.pop(), last)
        for s in by_course[course]:
            assert set(weeks) <= set(s['active_weeks'])
            s['lab_weeks'] = list(weeks)
            s['lab_requirement_origin'] = f'synthetic_A10_pattern_{name}'
    out['dataset_id'] = f"{data['dataset_id']}-pattern-{name}"
    out['generator'] = {**data.get('generator', {}), 'lab_pattern_variant': {
        'base_dataset_id': data['dataset_id'], 'pattern': name, 'seed': f'{SEED}-{name}',
        'rule': 'same sessions with Lab weeks and same count; the Lab weeks follow the pattern, one start per course (issue #30)'}}
    return out


def main():
    data = json.loads(gzip.decompress(SOURCE.read_bytes()).decode())
    OUT.mkdir(parents=True, exist_ok=True)
    for name in PATTERNS:
        out = variant(data, name)
        report = validate(out)
        if report['errors']:
            raise SystemExit(f'{name}: invalid: {report["errors"][:5]}')
        body = json.dumps(out, ensure_ascii=False, indent=1)
        path = OUT / f'fall-cs-pattern-{name}.json.gz'
        path.write_bytes(gzip.compress(body.encode(), mtime=0))
        print(path.relative_to(ROOT), 'sha256', hashlib.sha256(body.encode()).hexdigest(),
              'warnings', len(report['warnings']))


if __name__ == '__main__':
    main()
