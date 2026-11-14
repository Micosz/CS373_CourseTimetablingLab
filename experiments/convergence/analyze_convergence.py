"""When do HC, SA and GA stop improving? (issue #33) Standard library only.

    python3 experiments/convergence/analyze_convergence.py

None of the methods uses its budget to schedule the search (SA's calibration only differs below
9 evaluations), so the best-so-far trace of one long run gives the result the same seed would have
reached with any smaller budget. This script reads the budget-50,000 runs, checks that claim against
the stored budget-500 (experiments/final) and budget-1000 (experiments/budget) runs of the same
seeds, and writes:

- ``convergence.csv``: best-so-far per run at each budget level
- ``summary.csv`` / ``summary.json``: means per method and budget, convergence points, and the
  paired tests at the largest budget
- ``convergence.svg``: mean unnecessary Lab hours against the budget (log scale)

Convergence criterion (fixed before looking at the curves): a run has converged at evaluation E when
its best-so-far does not improve at all during the next WINDOW evaluations. We report the first such
E per run, or "not converged" when no window of that length without improvement fits in the budget.
"""
import csv
import gzip
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
import analyze  # noqa: E402

LEVELS = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]
WINDOWS = [5000, 10000]
METHODS = ['hc', 'sa', 'ga']
COLOR = {'hc': '#4d4d4d', 'sa': '#8f8f8f', 'ga': '#0a72ef'}


def load_runs(path):
    payload = json.loads(gzip.decompress(Path(path).read_bytes()))
    return payload['batch']['results']


def best_at(trace, budget):
    best = None
    for point in trace:
        if point['evaluations'] > budget:
            break
        best = point['objectives']
    return best


def improvements(trace):
    """Evaluations at which best-so-far strictly improved (the first point counts as the start)."""
    out, best = [], None
    for point in trace:
        if best is None or point['objectives'] < best:
            out.append(point['evaluations'])
            best = point['objectives']
    return out


def converged_at(trace, budget, window):
    steps = improvements(trace) + [budget + 1]
    for here, nxt in zip(steps, steps[1:]):
        if nxt - here > window and here + window <= budget:
            return here
    return None


def check_prefix(runs):
    """Prefix of the long run == stored shorter runs (Python engine) on the same seeds."""
    checked = 0
    for path, budget in ((ROOT / 'experiments/final/experiment.json.gz', 500),
                         (ROOT / 'experiments/budget/experiment.json.gz', 1000)):
        stored = {(r['algorithm'], r['seed']): r for r in load_runs(path)
                  if r['room_mode'] == 'weekly' and r['budget'] == budget and r['algorithm'] in METHODS}
        for r in runs:
            other = stored.get((r['algorithm'], r['seed']))
            if other is None:
                continue
            got = best_at(r['trace'], budget)
            want = analyze.objectives(other)
            if tuple(got) != tuple(want):
                raise SystemExit(f"prefix mismatch {r['algorithm']} {r['seed']} @ {budget}: {got} vs {want}")
            checked += 1
    return checked


def log_x(budget, x0, x1):
    import math
    lo, hi = math.log10(LEVELS[0]), math.log10(LEVELS[-1])
    return x0 + (math.log10(budget) - lo) / (hi - lo) * (x1 - x0)


def svg(means):
    w, h, left, right, top, bottom = 1100, 420, 70, 1070, 20, 360
    y_max = 150
    sy = lambda v: bottom - v / y_max * (bottom - top)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" '
             'aria-label="Lab ไม่จำเป็นเฉลี่ยของ HC SA GA ตามงบ 50 ถึง 50,000 evaluations แกนนอนแบบ log">']
    for v in (0, 50, 100, 150):
        parts.append(f'<line x1="{left}" y1="{sy(v):.1f}" x2="{right}" y2="{sy(v):.1f}" stroke="#efefef" stroke-width="2"/>'
                     f'<text x="{left - 12}" y="{sy(v) + 8:.1f}" text-anchor="end" font-size="22" fill="#666">{v}</text>')
    for b in LEVELS:
        x = log_x(b, left, right)
        parts.append(f'<text x="{x:.1f}" y="{bottom + 40}" text-anchor="middle" font-size="20" fill="#666">{b:,}</text>')
    for m in METHODS:
        pts = ' '.join(f'{log_x(b, left, right):.1f},{sy(means[m][b]):.1f}' for b in LEVELS)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{COLOR[m]}" stroke-width="{6 if m == "ga" else 4}"'
                     f'{" stroke-dasharray=\"12 8\"" if m == "sa" else ""}/>')
    parts.append('</svg>')
    return '\n'.join(parts)


def main():
    runs = [r for r in load_runs(HERE / 'b50000' / 'experiment.json.gz') if analyze.ok(r)]
    assert len(runs) == 30, len(runs)
    checked = check_prefix(runs)
    rows, per = [], defaultdict(dict)
    for r in sorted(runs, key=lambda r: (r['algorithm'], r['seed'])):
        row = {'algorithm': r['algorithm'], 'seed': r['seed']}
        for b in LEVELS:
            u, minutes, changes = best_at(r['trace'], b)
            row[f'unassigned_{b}'], row[f'lab_hours_{b}'], row[f'room_changes_{b}'] = u, minutes / 60, changes
            per[r['algorithm']].setdefault(b, []).append((u, minutes / 60, changes))
        row['last_improvement'] = improvements(r['trace'])[-1]
        for wdw in WINDOWS:
            row[f'converged_at_w{wdw}'] = converged_at(r['trace'], r['budget'], wdw)
        rows.append(row)
    with open(HERE / 'convergence.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    means = {m: {b: statistics.fmean(x[1] for x in per[m][b]) for b in LEVELS} for m in METHODS}
    summary = {'levels': LEVELS, 'prefix_checks': checked, 'methods': {}}
    for m in METHODS:
        mine = [x for x in rows if x['algorithm'] == m]
        conv = {}
        for wdw in WINDOWS:
            at = [x[f'converged_at_w{wdw}'] for x in mine]
            done = [a for a in at if a is not None]
            conv[str(wdw)] = {'converged_runs': len(done), 'runs': len(at),
                              'median_converged_at': statistics.median(done) if done else None,
                              'values': at}
        summary['methods'][m] = {
            'mean_lab_hours': means[m],
            'mean_room_changes': {b: statistics.fmean(x[2] for x in per[m][b]) for b in LEVELS},
            'all_assigned_runs': {b: sum(x[0] == 0 for x in per[m][b]) for b in LEVELS},
            'last_improvement': [x['last_improvement'] for x in mine],
            'convergence': conv,
        }
    # Paired tests on the same seeds at the largest budget (Holm over the three pairs).
    by_seed = defaultdict(dict)
    for r in runs:
        by_seed[r['seed']][r['algorithm']] = r
    tests = []
    for a, b in (('ga', 'hc'), ('ga', 'sa'), ('hc', 'sa')):
        seeds = sorted(s for s in by_seed if a in by_seed[s] and b in by_seed[s])
        ea = [analyze.energy(by_seed[s][a]) for s in seeds]
        eb = [analyze.energy(by_seed[s][b]) for s in seeds]
        test = analyze.wilcoxon(ea, eb)
        wins = sum(analyze.objectives(by_seed[s][a]) < analyze.objectives(by_seed[s][b]) for s in seeds)
        losses = sum(analyze.objectives(by_seed[s][a]) > analyze.objectives(by_seed[s][b]) for s in seeds)
        tests.append({'a': a, 'b': b, 'n': len(seeds), 'a_better': wins, 'b_better': losses, **test})
    for t, adj in zip(tests, analyze.holm([t['p_value'] for t in tests])):
        t['p_holm'] = adj
    summary['tests_at_50000'] = tests
    (HERE / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding='utf-8')
    with open(HERE / 'summary.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['algorithm', 'budget', 'mean_lab_hours', 'mean_room_changes', 'all_assigned_runs'])
        for m in METHODS:
            s = summary['methods'][m]
            for b in LEVELS:
                writer.writerow([m, b, round(s['mean_lab_hours'][b], 2), round(s['mean_room_changes'][b], 1), s['all_assigned_runs'][b]])
    (HERE / 'convergence.svg').write_text(svg(means), encoding='utf-8')

    print('prefix checks', checked)
    print('budget  ' + '  '.join(f'{b:>7}' for b in LEVELS))
    for m in METHODS:
        print(f'{m:6}  ' + '  '.join(f'{means[m][b]:7.1f}' for b in LEVELS))
    for m in METHODS:
        c = summary['methods'][m]['convergence']
        print(m, 'last improvement', sorted(summary['methods'][m]['last_improvement']),
              {w: (c[w]['converged_runs'], c[w]['median_converged_at']) for w in c})
    for t in tests:
        print(t['a'], 'vs', t['b'], f"{t['a_better']}/{t['n'] - t['a_better'] - t['b_better']}/{t['b_better']}",
              'p', round(t['p_value'], 4), 'holm', round(t['p_holm'], 4))


if __name__ == '__main__':
    main()
