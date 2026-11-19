"""Tune HC / SA / GA on the tuning seeds only (docs/protocol.md section 5). Standard library only.

    dotnet build -c Release dotnet/src/Timetabling.Cli
    python engine/tune.py --output experiments/tuning --workers 10

Runs every candidate setting with the C# engine on seeds 1-10 in weekly mode with the protocol
budget, picks the best setting per method by the lexicographic order of the
mean (unassigned, unnecessary Lab minutes, room changes), widens the search
while a chosen value sits on the edge of what was tried (the edge rule), and writes
``selected-parameters.json`` (usable with ``--parameters``), a CSV of every
setting and a Markdown summary. Re-running resumes from stored runs.
"""
import argparse
import csv
import gzip
import json
import random
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TUNING_SEEDS = list(range(1, 11))
BUDGET = 500
SECONDS = 3600
DEFAULTS = {'hc': {'restart_patience': 20},
            'sa': {'initial_acceptance': 0.8, 'cooling_rate': 0.97},
            'ga': {'population_size': 12, 'mutation_rate': 0.3, 'crossover_rate': 0.9,
                   'tournament_size': 3, 'elites': 1}}
LABELS = {'hc': 'Hill Climbing', 'sa': 'Simulated Annealing', 'ga': 'Genetic Algorithm'}


# Section 5 of the protocol: the values tried first, and the ladder each grid axis may be extended
# along. A ladder ends where a further step has no meaning (restart_patience = budget never
# restarts; initial_acceptance near 0 is hill climbing, near 1 a random walk).
START = {'hc': {'restart_patience': (5, 10, 20, 50, 100, 200, 500)},
         'sa': {'initial_acceptance': (0.01, 0.05, 0.2, 0.5, 0.8), 'cooling_rate': (0.8, 0.9, 0.97, 0.99)}}
LADDERS = {'hc': {'restart_patience': (1, 2, 5, 10, 20, 50, 100, 200, 500)},
           'sa': {'initial_acceptance': (0.001, 0.01, 0.05, 0.2, 0.5, 0.8, 0.95, 0.99),
                  'cooling_rate': (0.6, 0.7, 0.8, 0.9, 0.97, 0.99, 0.995, 0.999)}}
GA_RANGES = {'population_size': (6, 40), 'mutation_rate': (0.1, 1.0), 'crossover_rate': (0.5, 1.0)}
GA_LIMITS = {'population_size': (4, 60), 'mutation_rate': (0.02, 1.0), 'crossover_rate': (0.3, 1.0)}
GA_FIRST_SEED, GA_EXTRA = 4, 10


def grid(method, values):
    """Every combination of the axis values, as (config_id, method, parameters)."""
    if method == 'hc':
        return [(f'hc-p{p}', 'hc', {'restart_patience': p}) for p in values['restart_patience']]
    return [(f'sa-a{a}-c{c}', 'sa', {'initial_acceptance': a, 'cooling_rate': c})
            for a in values['initial_acceptance'] for c in values['cooling_rate']]


def draw_ga(seed, ranges, count, existing):
    """Random-search settings for GA, numbered after the existing ones."""
    rng, out = random.Random(seed), []
    while len(out) < count:
        pop = rng.randint(*ranges['population_size'])
        params = {'population_size': pop, 'mutation_rate': round(rng.uniform(*ranges['mutation_rate']), 2),
                  'crossover_rate': round(rng.uniform(*ranges['crossover_rate']), 2),
                  'tournament_size': rng.randint(2, min(5, pop)), 'elites': rng.randint(1, 3)}
        if params in existing or params in [p for _, _, p in out]:
            continue
        out.append((f'ga-{len(existing) + len(out):02d}', 'ga', params))
    return out


def candidates():
    """The settings of the first round, as (config_id, method, parameters)."""
    out = grid('hc', START['hc']) + grid('sa', START['sa'])
    out.append(('ga-00', 'ga', dict(DEFAULTS['ga'])))
    return out + draw_ga(GA_FIRST_SEED, GA_RANGES, 19, [DEFAULTS['ga']])


def extensions(settings, chosen, ga_ranges):
    """The edge rule: more settings when a chosen value sits on the edge of what was tried.

    Grid methods: if the chosen value of an axis is the lowest or highest tried and the ladder has
    a further step that way, that step is added, combined with every value tried on the other
    axes. GA: if the chosen population size, mutation rate or crossover rate lies in the outer 10%
    of its range and the range can still widen that way, the range is widened to its limit and
    GA_EXTRA more settings are drawn (seed = previous seed + 1). Returns (new settings, ga_ranges).
    """
    tried = [params for _, _, params in settings]
    new = []
    for method in ('hc', 'sa'):
        values = {axis: sorted({p[axis] for p in tried if axis in p}) for axis in LADDERS[method]}
        grown = {axis: list(v) for axis, v in values.items()}
        for axis, ladder in LADDERS[method].items():
            at = ladder.index(chosen[method]['parameters'][axis])
            if chosen[method]['parameters'][axis] == values[axis][0] and at > 0:
                grown[axis].append(ladder[at - 1])
            if chosen[method]['parameters'][axis] == values[axis][-1] and at < len(ladder) - 1:
                grown[axis].append(ladder[at + 1])
        new += [s for s in grid(method, {axis: sorted(v) for axis, v in grown.items()}) if s[2] not in tried]
    widened = dict(ga_ranges)
    for axis, (low, high) in ga_ranges.items():
        value, margin = chosen['ga']['parameters'][axis], (high - low) / 10
        if value <= low + margin and GA_LIMITS[axis][0] < low:
            widened[axis] = (GA_LIMITS[axis][0], widened[axis][1])
        if value >= high - margin and GA_LIMITS[axis][1] > high:
            widened[axis] = (widened[axis][0], GA_LIMITS[axis][1])
    if widened != ga_ranges:
        ga_tried = [p for _, m, p in settings if m == 'ga']
        rounds = (len(ga_tried) - 20) // GA_EXTRA
        new += draw_ga(GA_FIRST_SEED + 1 + rounds, widened, GA_EXTRA, ga_tried)
    return new, widened


def run_dotnet(settings, output, workers):
    """Run every setting with the C# engine, one folder per setting under ``configs/``.

    The C# CLI takes one parameter file per call, so each setting is its own small batch. A folder
    that already holds results is reused, which lets the edge rule add settings without rerunning.
    """
    cli = ['dotnet', 'run', '-c', 'Release', '--no-build', '--project',
           str(ROOT / 'dotnet' / 'src' / 'Timetabling.Cli'), '--', 'batch', 'run']
    seeds = f'{TUNING_SEEDS[0]}-{TUNING_SEEDS[-1]}'
    results = []
    for config_id, method, params in settings:
        folder = Path(output) / 'configs' / config_id
        if not (folder / 'experiment.json.gz').exists():
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'parameters.json').write_text(json.dumps({method: params}) + '\n', encoding='utf-8')
            subprocess.run(cli + ['--methods', method, '--room-modes', 'weekly', '--seeds', seeds,
                                  '--budget', str(BUDGET), '--seconds', str(SECONDS), '--slim',
                                  '--parameters', str(folder / 'parameters.json'), '--name', config_id,
                                  '--output', str(folder), '--workers', str(workers or len(TUNING_SEEDS))],
                           check=True, stdout=subprocess.DEVNULL)
        stored = json.loads(gzip.decompress((folder / 'experiment.json.gz').read_bytes()))['batch']['results']
        results += [{**r, 'config_id': config_id} for r in stored]
    return results


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
             'สร้างโดย `engine/tune.py` ห้ามแก้มือ ตัวเลขเป็นค่าเฉลี่ยบน 10 seed จูน', '',
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
    parser.add_argument('--output', type=Path, default=ROOT / 'experiments' / 'tuning')
    parser.add_argument('--workers', type=int, default=None)
    args = parser.parse_args()
    settings, ga_ranges = candidates(), dict(GA_RANGES)
    run = lambda: run_dotnet(settings, args.output, args.workers)
    while True:
        rows = summarize(run(), settings)
        chosen = select(rows)
        extra, ga_ranges = extensions(settings, chosen, ga_ranges)
        if not extra:
            break
        print('edge rule adds', [cid for cid, _, _ in extra])
        settings += extra
    write_outputs(args.output, rows, chosen)
    for method in DEFAULTS:
        print(method, chosen[method]['config_id'], chosen[method]['parameters'])


if __name__ == '__main__':
    main()
