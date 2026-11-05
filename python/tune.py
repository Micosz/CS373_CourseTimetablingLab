"""Tune HC / SA / GA on the tuning seeds only (docs/protocol.md section 5). Standard library only.

    python python/tune.py --output experiments/tuning --workers 18

Runs every candidate setting on seeds 1-10 in weekly mode with the protocol
budget, picks the best setting per method by the lexicographic order of the
mean (unassigned, unnecessary Lab minutes, room changes), and writes
``selected-parameters.json`` (usable with ``--parameters``), a CSV of every
setting and a Markdown summary. Re-running resumes from stored runs.
"""
import argparse
import csv
import json
import random
import statistics
from pathlib import Path

import batch

TUNING_SEEDS = list(range(1, 11))
BUDGET = 500
SECONDS = 3600
DEFAULTS = {'hc': {'restart_patience': 20},
            'sa': {'initial_acceptance': 0.8, 'cooling_rate': 0.97},
            'ga': {'population_size': 12, 'mutation_rate': 0.3, 'crossover_rate': 0.9,
                   'tournament_size': 3, 'elites': 1}}
LABELS = {'hc': 'Hill Climbing', 'sa': 'Simulated Annealing', 'ga': 'Genetic Algorithm'}


def candidates():
    """Every setting from the protocol, as (config_id, method, parameters)."""
    out = [(f'hc-p{p}', 'hc', {'restart_patience': p}) for p in (5, 10, 20, 50, 100, 200, 500)]
    out += [(f'sa-a{a}-c{c}', 'sa', {'initial_acceptance': a, 'cooling_rate': c})
            for a in (0.2, 0.5, 0.8, 0.95) for c in (0.9, 0.97, 0.99, 0.995, 0.999)]
    out.append(('ga-00', 'ga', dict(DEFAULTS['ga'])))
    rng = random.Random(4)
    while len(out) < 7 + 20 + 20:
        pop = rng.randint(6, 40)
        params = {'population_size': pop, 'mutation_rate': round(rng.uniform(0.1, 1.0), 2),
                  'crossover_rate': round(rng.uniform(0.5, 1.0), 2),
                  'tournament_size': rng.randint(2, min(5, pop)), 'elites': rng.randint(1, 3)}
        if any(p == params for _, m, p in out if m == 'ga'):
            continue
        out.append((f'ga-{len(out) - 27:02d}', 'ga', params))
    return out


def summarize(results, settings):
    by_config = {}
    for r in results:
        by_config.setdefault(r['config_id'], []).append(r)
    rows = []
    for config_id, method, params in settings:
        runs = by_config[config_id]
        ok = [r for r in runs if r['valid'] and r['status'] == 'evaluation_budget']
        m = [r['metrics'] for r in ok]
        mean = lambda key: statistics.fmean(x[key] for x in m) if m else float('inf')
        rows.append({'config_id': config_id, 'method': method, 'parameters': params,
                     'is_default': params == DEFAULTS[method], 'runs': len(runs), 'valid_runs': len(ok),
                     'time_limited': sum(r['status'] == 'time_limit' for r in runs),
                     'mean_unassigned': mean('unassigned_weekly_sessions'),
                     'mean_unnecessary_lab_minutes': mean('unnecessary_lab_minutes'),
                     'mean_room_changes': mean('room_changes'),
                     'success_rate': sum(x['unassigned_weekly_sessions'] == 0 for x in m) / len(runs),
                     'median_unnecessary_lab_hours': statistics.median(x['unnecessary_lab_hours'] for x in m) if m else None,
                     'mean_search_seconds': statistics.fmean(r['search_seconds'] for r in runs)})
    return rows


def rank_key(row):
    """Lexicographic on means; complete settings first; ties go to the default setting."""
    return (row['valid_runs'] < row['runs'], row['mean_unassigned'], row['mean_unnecessary_lab_minutes'],
            row['mean_room_changes'], not row['is_default'])


def select(rows):
    return {method: min((r for r in rows if r['method'] == method), key=rank_key) for method in DEFAULTS}


def fmt(x, d=1):
    return f'{x:,.{d}f}'


def write_outputs(output, rows, chosen):
    output = Path(output)
    selected = {method: chosen[method]['parameters'] for method in DEFAULTS}
    selected['_selection'] = {
        'protocol': 'docs/protocol.md section 5', 'tuning_seeds': TUNING_SEEDS, 'budget': BUDGET, 'room_mode': 'weekly',
        'criterion': 'lexicographic order of mean (unassigned, unnecessary Lab minutes, room changes); ties keep the default',
        'chosen_config_ids': {m: chosen[m]['config_id'] for m in DEFAULTS}}
    (output / 'selected-parameters.json').write_text(json.dumps(selected, indent=2) + '\n', encoding='utf-8')
    fields = ['config_id', 'method', 'parameters', 'is_default', 'runs', 'valid_runs', 'time_limited',
              'mean_unassigned', 'mean_unnecessary_lab_minutes', 'mean_room_changes', 'success_rate',
              'median_unnecessary_lab_hours', 'mean_search_seconds']
    with (output / 'tuning-summary.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in sorted(rows, key=lambda r: (r['method'], rank_key(r))):
            writer.writerow({**r, 'parameters': json.dumps(r['parameters'], sort_keys=True)})
    lines = ['# ผลการจูน (seed 1–10, weekly, งบ 500)', '',
             'สร้างโดย `python/tune.py` ห้ามแก้มือ ตัวเลขเป็นค่าเฉลี่ยบน 10 seed จูน', '',
             '## ค่าเริ่มต้นเทียบกับค่าที่เลือก', '',
             '| วิธี | ชุดค่า | พารามิเตอร์ | คาบที่ยังจัดไม่ได้ | Lab ไม่จำเป็น (ชม.) | เปลี่ยนห้อง | จัดครบทุกคาบ |',
             '|---|---|---|---:|---:|---:|---:|']
    for method in DEFAULTS:
        default = next(r for r in rows if r['method'] == method and r['is_default'])
        for tag, r in (('ค่าเริ่มต้น', default), ('**ที่เลือก**', chosen[method])):
            lines.append(f"| {LABELS[method]} | {tag} | `{json.dumps(r['parameters'], sort_keys=True)}` | "
                         f"{fmt(r['mean_unassigned'], 2)} | {fmt(r['mean_unnecessary_lab_minutes'] / 60)} | "
                         f"{fmt(r['mean_room_changes'])} | {r['success_rate']:.0%} |")
    lines += ['', '## ทุกชุดค่าที่ลอง (เรียงจากดีไปแย่ในแต่ละวิธี)', '',
              '| ชุดค่า | พารามิเตอร์ | รันที่ใช้ได้ | คาบที่ยังจัดไม่ได้ | Lab ไม่จำเป็น (ชม.) | เปลี่ยนห้อง | จัดครบ | วินาที/รัน |',
              '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in sorted(rows, key=lambda r: (list(DEFAULTS).index(r['method']), rank_key(r))):
        lines.append(f"| {r['config_id']}{' (ค่าเริ่มต้น)' if r['is_default'] else ''} | "
                     f"`{json.dumps(r['parameters'], sort_keys=True)}` | {r['valid_runs']}/{r['runs']} | "
                     f"{fmt(r['mean_unassigned'], 2)} | {fmt(r['mean_unnecessary_lab_minutes'] / 60)} | "
                     f"{fmt(r['mean_room_changes'])} | {r['success_rate']:.0%} | {fmt(r['mean_search_seconds'])} |")
    (output / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, default=batch.ROOT / 'experiments' / 'tuning')
    parser.add_argument('--workers', type=int, default=None)
    args = parser.parse_args()
    settings = candidates()
    jobs = [{'config_id': cid, 'algorithm': method, 'room_mode': 'weekly', 'seed': seed, 'budget': BUDGET,
             'seconds': SECONDS, 'parameters': {method: params}}
            for cid, method, params in settings for seed in TUNING_SEEDS]
    results = batch.run_jobs(jobs, args.output, workers=args.workers, slim=True, name='Parameter tuning (seeds 1-10)')
    rows = summarize(results, settings)
    chosen = select(rows)
    write_outputs(args.output, rows, chosen)
    batch.merge(args.output, name='Parameter tuning (seeds 1-10)')
    for method in DEFAULTS:
        print(method, chosen[method]['config_id'], chosen[method]['parameters'])


if __name__ == '__main__':
    main()
