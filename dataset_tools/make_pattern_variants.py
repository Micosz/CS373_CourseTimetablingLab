"""Build Lab-week pattern variants of the main dataset (issue #30). Standard library only.

    python dataset_tools/make_pattern_variants.py

The main dataset gives 60% of recurring sessions 4 Lab weeks drawn at random from 15 (assumption
A10). Real courses often follow a pattern instead, so these variants keep the same sessions with
Lab weeks (and 4 Lab weeks each) and change only which weeks:

- ``consecutive``: 4 weeks in a row, the first week drawn uniformly from 1..12
- ``alternate``: every other week, 4 times (s, s+2, s+4, s+6), s drawn uniformly from 1..9

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
    'consecutive': lambda rng, n: [s + i for s in [rng.randint(1, 15 - n + 1)] for i in range(n)],
    'alternate': lambda rng, n: [s + 2 * i for s in [rng.randint(1, 15 - 2 * (n - 1))] for i in range(n)],
}


def variant(data, name):
    out = json.loads(json.dumps(data))
    rng = random.Random(f'{SEED}-{name}')
    for s in sorted(out['recurring_sessions'], key=lambda s: s['id']):
        if s['lab_weeks']:
            weeks = PATTERNS[name](rng, len(s['lab_weeks']))
            assert set(weeks) <= set(s['active_weeks'])
            s['lab_weeks'] = weeks
            s['lab_requirement_origin'] = f'synthetic_A10_pattern_{name}'
    out['dataset_id'] = f"{data['dataset_id']}-pattern-{name}"
    out['generator'] = {**data.get('generator', {}), 'lab_pattern_variant': {
        'base_dataset_id': data['dataset_id'], 'pattern': name, 'seed': f'{SEED}-{name}',
        'rule': 'same sessions with Lab weeks and same count; only the Lab weeks follow the pattern (issue #30)'}}
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
