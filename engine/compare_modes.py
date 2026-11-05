"""Paired weekly vs fixed-room summary from a native or web experiment JSON.

Runs are paired by (algorithm, seed): both modes start from the same initial
genome and seed, so the difference fixed - weekly isolates the room policy.
Only runs that passed the independent validator are summarized.
"""
import argparse
import gzip
import json
import statistics
from collections import defaultdict
from pathlib import Path

METRICS = [('unassigned_weekly_sessions', 'คาบที่ยังจัดไม่ได้'),
           ('unnecessary_lab_hours', 'Lab ไม่จำเป็น (ชม.)'),
           ('room_changes', 'เปลี่ยนห้อง (ครั้ง)')]
ORDER = ['greedy', 'hc', 'sa', 'ga', 'custom']


def load(path):
    raw = path.read_bytes()
    if path.suffix == '.gz':
        raw = gzip.decompress(raw)
    payload = json.loads(raw.decode())
    return payload.get('batch', payload)


def fmt(value, digits=1):
    return '-' if value is None else f'{value:,.{digits}f}'


def summarize(batch):
    runs = defaultdict(dict)
    counts = defaultdict(lambda: [0, 0])
    for r in batch['results']:
        mode = r.get('room_mode') or batch.get('config', {}).get('room_mode') or 'weekly'
        counts[(r['algorithm'], mode)][1] += 1
        if r.get('valid') and r.get('metrics'):
            counts[(r['algorithm'], mode)][0] += 1
            runs[(r['algorithm'], r['seed'])][mode] = r['metrics']
    methods = sorted({a for a, _ in counts}, key=lambda m: (ORDER.index(m) if m in ORDER else 99, m))
    lines = ['| วิธี | โหมด | ผ่านตัวตรวจ | ' + ' | '.join(f'{label} mean (median)' for _, label in METRICS) + ' |',
             '|---|---|---:|' + '---:|' * len(METRICS)]
    for method in methods:
        for mode in ('weekly', 'fixed'):
            if (method, mode) not in counts:
                continue
            rows = [m[mode] for (a, _), m in runs.items() if a == method and mode in m]
            cells = []
            for key, _ in METRICS:
                values = [row[key] for row in rows]
                cells.append(f"{fmt(statistics.mean(values))} ({fmt(statistics.median(values))})" if values else '-')
            ok, total = counts[(method, mode)]
            lines.append(f'| {method} | {mode} | {ok} / {total} | ' + ' | '.join(cells) + ' |')
    lines += ['', '**ผลต่างแบบจับคู่ fixed − weekly** (seed เดียวกัน, initial genome เดียวกัน)', '',
              '| วิธี | คู่ที่ใช้ได้ | ' + ' | '.join(f'Δ {label} mean' for _, label in METRICS) +
              ' | seed ที่ fixed ใช้ Lab ไม่จำเป็นมากกว่า |',
              '|---|---:|' + '---:|' * len(METRICS) + '---:|']
    for method in methods:
        pairs = [m for (a, _), m in runs.items() if a == method and {'weekly', 'fixed'} <= set(m)]
        if not pairs:
            continue
        deltas = [fmt(statistics.mean(p['fixed'][k] - p['weekly'][k] for p in pairs)) for k, _ in METRICS]
        more_lab = sum(p['fixed']['unnecessary_lab_minutes'] > p['weekly']['unnecessary_lab_minutes'] for p in pairs)
        lines.append(f'| {method} | {len(pairs)} | ' + ' | '.join(deltas) + f' | {more_lab} / {len(pairs)} |')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiments', type=Path, nargs='+',
                        help='One or more experiment-*.json(.gz) files from cli.py or the web export; results are pooled')
    parser.add_argument('--output', type=Path, help='Write the Markdown table here instead of stdout')
    args = parser.parse_args()
    batches = [load(path) for path in args.experiments]
    pooled = {'results': [{**r, 'room_mode': r.get('room_mode') or b.get('config', {}).get('room_mode') or 'weekly'}
                          for b in batches for r in b['results']]}
    keys = [(r['algorithm'], r['room_mode'], r['seed']) for r in pooled['results']]
    if len(keys) != len(set(keys)):
        parser.error('The same (algorithm, room_mode, seed) appears in more than one run')
    text = summarize(pooled) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
