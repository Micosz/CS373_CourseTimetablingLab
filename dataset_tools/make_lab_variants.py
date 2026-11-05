"""Build the Lab-shortage variants of the main dataset (issue #13). Standard library only.

    python dataset_tools/make_lab_variants.py

Removes the smallest simulated computer Labs one at a time (4 -> 3 -> 2 Labs)
and keeps everything else identical: classes, sessions, Lab weeks, lecture
rooms, background classes and constraints. Each variant must pass the same
input validation as the main dataset. Output: data/variants/fall-cs-labs{N}.json.gz
"""
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from input_validation import validate  # noqa: E402

SOURCE = ROOT / 'data' / 'fall-cs.json.gz'
OUT = ROOT / 'data' / 'variants'


def variant(data, keep):
    labs = sorted((r for r in data['rooms'] if r['kind'] == 'computer_lab'), key=lambda r: (-r['capacity'], r['id']))
    removed = {r['id'] for r in labs[keep:]}
    out = json.loads(json.dumps(data))
    out['dataset_id'] = f"{data['dataset_id']}-labs{keep}"
    out['rooms'] = [r for r in out['rooms'] if r['id'] not in removed]
    for c in out['classes']:
        c['lab_room_ids'] = [rid for rid in c['lab_room_ids'] if rid not in removed]
        if any(s['lab_weeks'] for s in out['recurring_sessions'] if s['class_id'] == c['id']) and not c['lab_room_ids']:
            raise ValueError(f"{c['id']} would have no Lab left")
    out['generator'] = {**data.get('generator', {}), 'lab_variant': {
        'base_dataset_id': data['dataset_id'], 'labs_kept': keep, 'removed_room_ids': sorted(removed),
        'rule': 'remove the smallest simulated computer Labs; everything else unchanged (issue #13)'}}
    return out


def main():
    text = gzip.decompress(SOURCE.read_bytes()).decode()
    data = json.loads(text)
    OUT.mkdir(parents=True, exist_ok=True)
    for keep in (3, 2):
        out = variant(data, keep)
        report = validate(out)
        if report['errors']:
            raise SystemExit(f'labs{keep}: invalid: {report["errors"][:5]}')
        body = json.dumps(out, ensure_ascii=False, indent=1)
        path = OUT / f'fall-cs-labs{keep}.json.gz'
        path.write_bytes(gzip.compress(body.encode(), mtime=0))
        labs = [(r['id'], r['capacity']) for r in out['rooms'] if r['kind'] == 'computer_lab']
        print(path.relative_to(ROOT), labs, 'sha256', hashlib.sha256(body.encode()).hexdigest(),
              'warnings', len(report['warnings']))


if __name__ == '__main__':
    main()
