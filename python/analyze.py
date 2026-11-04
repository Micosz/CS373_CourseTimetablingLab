"""Tables, statistics and SVG charts from raw experiment results (docs/protocol.md). Standard library only.

    python python/analyze.py experiments/final/experiment.json.gz --output experiments/final/analysis

Reads one or more experiment files (``.json`` or ``.json.gz`` from cli.py,
batch.py or the web), and writes:

- ``runs.csv``: one row per run with room_changes next to room_change_lower_bound (#10)
- ``summary.csv`` / ``summary.json``: mean / median / std / best / worst of every
  metric and the success rate per (room mode, method)
- ``stats.json``: Friedman test, Holm-adjusted paired Wilcoxon tests, weekly vs
  fixed tests, and the room-change lower bound analysis (#10)
- ``report.md``: the same numbers as tables plus plain-language sentences
- ``convergence.svg``, ``lab-hours-boxplot.svg``, ``weekly-vs-fixed.svg``,
  ``room-changes.svg``

Slides and the report should take numbers from these files, not retype them.
"""
import argparse
import csv
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ALPHA = 0.05
METHODS = ['greedy', 'hc', 'sa', 'ga']
LABEL = {'greedy': 'Greedy', 'hc': 'HC', 'sa': 'SA', 'ga': 'GA'}
LONG = {'greedy': 'Greedy', 'hc': 'Hill Climbing', 'sa': 'Simulated Annealing', 'ga': 'Genetic Algorithm'}
MODE_TH = {'weekly': 'รายสัปดาห์ (weekly)', 'fixed': 'ห้องคงที่ (fixed)'}
METRICS = [('unassigned_weekly_sessions', 'คาบที่ยังจัดไม่ได้', 1),
           ('unnecessary_lab_hours', 'Lab ไม่จำเป็น (ชม.)', 1),
           ('room_changes', 'เปลี่ยนห้อง (ครั้ง)', 1),
           ('search_seconds', 'เวลาค้นหา (วินาที)', 1)]


# --- loading ---------------------------------------------------------------
def load(paths):
    """Return (results, dataset) from experiment files; refuses duplicate (mode, method, seed, config)."""
    results, dataset, seen = [], None, set()
    for path in paths:
        path = Path(path)
        raw = path.read_bytes()
        if path.suffix == '.gz':
            raw = gzip.decompress(raw)
        payload = json.loads(raw.decode())
        batch = payload.get('batch', payload)
        text = payload.get('dataset_text')
        if text:
            data = json.loads(text)
            if dataset is not None and data['dataset_id'] != dataset['dataset_id']:
                raise ValueError('Experiment files use different datasets')
            dataset = data
        for r in batch['results']:
            r.setdefault('room_mode', batch.get('config', {}).get('room_mode') or 'weekly')
            key = (r.get('config_id', 'main'), r['room_mode'], r['algorithm'], r['seed'])
            if key in seen:
                raise ValueError(f'Duplicate run {key}')
            seen.add(key)
            results.append(r)
    return results, dataset


def ok(run):
    return bool(run.get('valid')) and run.get('status') in ('completed', 'evaluation_budget') and run.get('metrics')


def objectives(run):
    m = run['metrics']
    return (m['unassigned_weekly_sessions'], m['unnecessary_lab_minutes'], m['room_changes'])


def energy(run):
    w = run['energy_weights']
    u, minutes, changes = objectives(run)
    return u * w['unassigned'] + minutes * w['lab_minute'] + changes * w['room_change']


def value(run, key):
    return run['search_seconds'] if key == 'search_seconds' else run['metrics'][key]


# --- statistics (stdlib) ----------------------------------------------------
def average_ranks(values, key=None):
    """1-based ranks, ties get the average rank."""
    key = key or (lambda x: x)
    order = sorted(range(len(values)), key=lambda i: key(values[i]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and key(values[order[j + 1]]) == key(values[order[i]]):
            j += 1
        for t in range(i, j + 1):
            ranks[order[t]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def _gamma_q(a, x):
    """Regularized upper incomplete gamma Q(a, x) (Numerical Recipes series / continued fraction)."""
    if x <= 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1:
        term = total = 1.0 / a
        n = a
        for _ in range(10000):
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return max(0.0, 1.0 - total * math.exp(-x + a * math.log(x) - gln))
    b = x + 1 - a
    c = 1 / 1e-300
    d = 1 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def chi2_sf(x, df):
    return _gamma_q(df / 2, x / 2)


def friedman(blocks):
    """blocks: list of per-block lists of ranks (already ranked within block, ties averaged)."""
    n, k = len(blocks), len(blocks[0])
    sums = [sum(b[j] for b in blocks) for j in range(k)]
    statistic = 12 / (n * k * (k + 1)) * sum(s * s for s in sums) - 3 * n * (k + 1)
    ties = 0
    for b in blocks:
        for t in Counter(b).values():
            ties += t ** 3 - t
    denominator = 1 - ties / (n * (k ** 3 - k))
    if denominator <= 0:  # every block is a complete tie
        return {'statistic': 0.0, 'df': k - 1, 'p_value': 1.0, 'mean_ranks': [s / n for s in sums], 'n': n}
    statistic /= denominator
    return {'statistic': statistic, 'df': k - 1, 'p_value': chi2_sf(statistic, k - 1),
            'mean_ranks': [s / n for s in sums], 'n': n}


def wilcoxon(x, y):
    """Two-sided paired Wilcoxon signed-rank test on x - y.

    Zero differences are dropped and tied |d| get average ranks. With at most
    ``EXACT_MAX_N`` non-zero pairs and no tied |d|, the p-value is exact (the
    null distribution of W+ over all 2^n sign patterns); otherwise it uses the
    normal approximation with tie and continuity correction. ``method`` says which.
    """
    d = [a - b for a, b in zip(x, y) if a != b]
    n = len(d)
    if n == 0:
        return {'n_nonzero': 0, 'w_plus': 0.0, 'w_minus': 0.0, 'z': 0.0, 'p_value': 1.0, 'method': 'none'}
    ranks = average_ranks([abs(v) for v in d])
    w_plus = sum(r for r, v in zip(ranks, d) if v > 0)
    w_minus = sum(r for r, v in zip(ranks, d) if v < 0)
    mean = n * (n + 1) / 4
    ties = sum(t ** 3 - t for t in Counter(abs(v) for v in d).values())
    var = n * (n + 1) * (2 * n + 1) / 24 - ties / 48
    diff = w_plus - mean
    z = (diff - math.copysign(0.5, diff)) / math.sqrt(var) if diff and var > 0 else 0.0
    if n <= EXACT_MAX_N and ties == 0:
        return {'n_nonzero': n, 'w_plus': w_plus, 'w_minus': w_minus, 'z': z,
                'p_value': exact_signed_rank_p(n, min(w_plus, w_minus)), 'method': 'exact'}
    if var <= 0:
        return {'n_nonzero': n, 'w_plus': w_plus, 'w_minus': w_minus, 'z': 0.0, 'p_value': 1.0, 'method': 'normal'}
    return {'n_nonzero': n, 'w_plus': w_plus, 'w_minus': w_minus, 'z': z,
            'p_value': math.erfc(abs(z) / math.sqrt(2)), 'method': 'normal'}


EXACT_MAX_N = 25


def exact_signed_rank_p(n, w_small):
    """Two-sided exact p = 2 * P(W+ <= w_small) for ranks 1..n without ties."""
    counts = [1] + [0] * (n * (n + 1) // 2)
    for rank in range(1, n + 1):
        for total in range(len(counts) - 1, rank - 1, -1):
            counts[total] += counts[total - rank]
    tail = sum(counts[:int(w_small) + 1])
    return min(1.0, 2 * tail / 2 ** n)


def holm(p_values):
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for position, i in enumerate(order):
        running = max(running, min(1.0, (m - position) * p_values[i]))
        adjusted[i] = running
    return adjusted


# --- descriptive -------------------------------------------------------------
def describe(values):
    if not values:
        return {'n': 0, 'mean': None, 'median': None, 'std': None, 'best': None, 'worst': None, 'q1': None, 'q3': None}
    q = statistics.quantiles(values, n=4, method='inclusive') if len(values) > 1 else [values[0]] * 3
    return {'n': len(values), 'mean': statistics.fmean(values), 'median': statistics.median(values),
            'std': statistics.stdev(values) if len(values) > 1 else 0.0, 'best': min(values), 'worst': max(values),
            'q1': q[0], 'q3': q[2]}


def summary_rows(results):
    groups = defaultdict(list)
    for r in results:
        groups[(r['room_mode'], r['algorithm'])].append(r)
    rows = []
    for (mode, method) in sorted(groups, key=lambda g: (g[0] != 'weekly', METHODS.index(g[1]) if g[1] in METHODS else 9)):
        runs = groups[(mode, method)]
        good = [r for r in runs if ok(r)]
        row = {'room_mode': mode, 'algorithm': method, 'runs': len(runs), 'valid_runs': len(good),
               'failed_runs': len(runs) - len(good),
               'time_limited_runs': sum(r['status'] == 'time_limit' for r in runs),
               'success_rate': sum(r['metrics']['unassigned_weekly_sessions'] == 0 for r in good) / len(runs),
               'mean_evaluations': statistics.fmean(r['evaluations'] for r in runs)}
        for key, _, _ in METRICS:
            row[key] = describe([value(r, key) for r in good])
        rows.append(row)
    return rows


# --- room changes (#10) -----------------------------------------------------
def room_change_bound(dataset):
    """Minimum room changes of any complete schedule with zero unnecessary Lab use.

    Between two consecutive active weeks of a session where one needs a Lab and
    the other does not, the room kind must switch (Lab vs non-Lab), so the room
    must change. Summed over sessions this is a lower bound for schedules that
    assign every week and never use a Lab without need.
    """
    total, per_session = 0, {}
    for s in dataset['recurring_sessions']:
        weeks, labs = sorted(s['active_weeks']), set(s['lab_weeks'])
        switches = sum((a in labs) != (b in labs) for a, b in zip(weeks, weeks[1:]))
        per_session[s['id']] = switches
        total += switches
    return total, per_session


def run_kind_switches(run, dataset):
    """Room-kind switches forced inside this run's own schedule (a per-run lower bound on its changes)."""
    kinds = {r['id']: r['kind'] == 'computer_lab' for r in dataset['rooms']}
    rooms = {(a['session_id'], a['week']): a['room_id'] for a in run['solution']['weekly_room_assignments']}
    total = 0
    for s in dataset['recurring_sessions']:
        used = [kinds[rooms[(s['id'], w)]] for w in sorted(s['active_weeks']) if (s['id'], w) in rooms]
        total += sum(a != b for a, b in zip(used, used[1:]))
    return total


def per_class_changes(run, dataset):
    rooms = {(a['session_id'], a['week']): a['room_id'] for a in run['solution']['weekly_room_assignments']}
    by_class = Counter()
    for s in dataset['recurring_sessions']:
        used = [rooms[(s['id'], w)] for w in sorted(s['active_weeks']) if (s['id'], w) in rooms]
        by_class[s['class_id']] += sum(a != b for a, b in zip(used, used[1:]))
    for c in dataset['classes']:
        by_class.setdefault(c['id'], 0)
    return by_class


BUCKETS = [('0', lambda v: v == 0), ('1–2', lambda v: 1 <= v <= 2), ('3–4', lambda v: 3 <= v <= 4),
           ('5–8', lambda v: 5 <= v <= 8), ('มากกว่า 8', lambda v: v > 8)]


def bucket_counts(by_class):
    return {name: sum(test(v) for v in by_class.values()) for name, test in BUCKETS}


def room_change_analysis(results, dataset):
    bound, per_session = room_change_bound(dataset)
    target = {c['id'] for c in dataset['classes']}
    class_bound = Counter()
    for s in dataset['recurring_sessions']:
        if s['class_id'] in target:
            class_bound[s['class_id']] += per_session[s['id']]
    for cid in target:
        class_bound.setdefault(cid, 0)
    out = {'dataset_lower_bound': bound, 'lower_bound_class_buckets': bucket_counts(class_bound), 'methods': {}}
    for mode in ('weekly', 'fixed'):
        for method in METHODS:
            runs = [r for r in results if r['room_mode'] == mode and r['algorithm'] == method and ok(r)
                    and r.get('solution')]
            if not runs:
                continue
            changes = [r['metrics']['room_changes'] for r in runs]
            kind = [run_kind_switches(r, dataset) for r in runs]
            buckets = defaultdict(list)
            for r in runs:
                for name, count in bucket_counts(per_class_changes(r, dataset)).items():
                    buckets[name].append(count)
            out['methods'][f'{mode}:{method}'] = {
                'room_mode': mode, 'algorithm': method, 'runs': len(runs),
                'room_changes': describe(changes), 'kind_switches': describe(kind),
                'ratio_to_dataset_bound': describe([c / bound for c in changes]) if bound else None,
                'changes_above_own_kind_switches': describe([c - k for c, k in zip(changes, kind)]),
                'unnecessary_lab_hours': describe([r['metrics']['unnecessary_lab_hours'] for r in runs]),
                'mean_class_buckets': {k: statistics.fmean(v) for k, v in buckets.items()}}
    return out


# --- tests --------------------------------------------------------------------
def paired_by_seed(results, mode, methods):
    by = defaultdict(dict)
    for r in results:
        if r['room_mode'] == mode and r['algorithm'] in methods and ok(r):
            by[r['seed']][r['algorithm']] = r
    seeds = sorted(s for s, row in by.items() if all(m in row for m in methods))
    return seeds, by


def method_tests(results, mode='weekly'):
    methods = [m for m in METHODS if any(r['algorithm'] == m and r['room_mode'] == mode for r in results)]
    seeds, by = paired_by_seed(results, mode, methods)
    if len(methods) < 2 or not seeds:
        return None
    blocks = [average_ranks([by[s][m] for m in methods], key=objectives) for s in seeds]
    fr = friedman(blocks)
    fr['methods'] = methods
    fr['significant'] = fr['p_value'] < ALPHA
    pairs = []
    for a, b in combinations(methods, 2):
        ea = [energy(by[s][a]) for s in seeds]
        eb = [energy(by[s][b]) for s in seeds]
        test = wilcoxon(ea, eb)
        wins = sum(objectives(by[s][a]) < objectives(by[s][b]) for s in seeds)
        losses = sum(objectives(by[s][a]) > objectives(by[s][b]) for s in seeds)
        medians = {key: statistics.median(value(by[s][a], key) - value(by[s][b], key) for s in seeds)
                   for key, _, _ in METRICS}
        pairs.append({'a': a, 'b': b, 'n': len(seeds), 'a_better': wins, 'ties': len(seeds) - wins - losses,
                      'b_better': losses, 'median_difference_a_minus_b': medians, **test})
    for pair, adjusted in zip(pairs, holm([p['p_value'] for p in pairs])):
        pair['p_holm'] = adjusted
        pair['significant'] = fr['significant'] and adjusted < ALPHA
    return {'room_mode': mode, 'seeds': seeds, 'alpha': ALPHA, 'friedman': fr, 'pairwise': pairs}


def mode_tests(results):
    out = []
    for key in ('unnecessary_lab_hours', 'unassigned_weekly_sessions'):
        rows = []
        for method in METHODS:
            w = {r['seed']: r for r in results if r['algorithm'] == method and r['room_mode'] == 'weekly' and ok(r)}
            f = {r['seed']: r for r in results if r['algorithm'] == method and r['room_mode'] == 'fixed' and ok(r)}
            seeds = sorted(set(w) & set(f))
            if not seeds:
                continue
            fx = [f[s]['metrics'][key] for s in seeds]
            wx = [w[s]['metrics'][key] for s in seeds]
            rows.append({'metric': key, 'algorithm': method, 'n': len(seeds),
                         'fixed_higher': sum(a > b for a, b in zip(fx, wx)),
                         'equal': sum(a == b for a, b in zip(fx, wx)),
                         'mean_fixed_minus_weekly': statistics.fmean(a - b for a, b in zip(fx, wx)),
                         'median_fixed_minus_weekly': statistics.median(a - b for a, b in zip(fx, wx)),
                         **wilcoxon(fx, wx)})
        for row, adjusted in zip(rows, holm([r['p_value'] for r in rows])):
            row['p_holm'] = adjusted
            row['significant'] = adjusted < ALPHA
        out.extend(rows)
    return out


# --- SVG ----------------------------------------------------------------------
COLOR = {'greedy': '#8a8984', 'hc': '#2a78d6', 'sa': '#eb6834', 'ga': '#1baf7a'}
COLOR_DARK = {'greedy': '#9a9992', 'hc': '#3987e5', 'sa': '#d95926', 'ga': '#199e70'}
MODE_COLOR = {'weekly': 'hc', 'fixed': 'sa'}
FONT = "'Noto Sans Thai','Leelawadee UI','Sarabun',Tahoma,system-ui,sans-serif"


def esc(text):
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def svg_doc(width, height, title, desc, body):
    series = ''.join(f'.s-{k}{{fill:{v};stroke:{v}}}' for k, v in COLOR.items())
    dark = ''.join(f'.s-{k}{{fill:{v};stroke:{v}}}' for k, v in COLOR_DARK.items())
    style = (f"text{{font-family:{FONT};fill:var(--ink)}}"
             ":root{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--axis:#a3a29c}"
             f"{series}.bg{{fill:var(--surface)}}.grid{{stroke:var(--grid);stroke-width:1}}"
             ".axis{stroke:var(--axis);stroke-width:1}.muted{fill:var(--ink2)}.line{fill:none;stroke-width:2}"
             ".band{stroke:none;opacity:.18}.ref{fill:none;stroke-width:2;stroke-dasharray:6 4}"
             f"@media (prefers-color-scheme:dark){{:root{{--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;"
             f"--grid:#33332f;--axis:#6b6a64}}{dark}}}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" role="img" aria-labelledby="t d"><title id="t">{esc(title)}</title>'
            f'<desc id="d">{esc(desc)}</desc><style>{style}</style>'
            f'<rect class="bg" width="{width}" height="{height}"/>{body}</svg>\n')


def nice_ticks(lo, hi, count=5):
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / count
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks = []
    t = start
    while t <= hi + step * 1e-9:
        ticks.append(round(t, 10))
        t += step
    if ticks[-1] < hi:
        ticks.append(ticks[-1] + step)
    return ticks


def fmt_num(v):
    return f'{v:,.0f}' if abs(v) >= 100 or float(v).is_integer() else f'{v:,.1f}'


class Panel:
    """A plot area with a linear y axis (and linear or categorical x)."""

    def __init__(self, x, y, w, h, y_lo, y_hi, x_lo=0, x_hi=1):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.ticks = nice_ticks(y_lo, y_hi)
        self.y_lo, self.y_hi = self.ticks[0], self.ticks[-1]
        self.x_lo, self.x_hi = x_lo, x_hi

    def sx(self, v):
        return self.x + (v - self.x_lo) / ((self.x_hi - self.x_lo) or 1) * self.w

    def sy(self, v):
        return self.y + self.h - (v - self.y_lo) / ((self.y_hi - self.y_lo) or 1) * self.h

    def frame(self, y_title, x_title=None, x_ticks=None):
        parts = []
        for t in self.ticks:
            yy = self.sy(t)
            parts.append(f'<line class="grid" x1="{self.x}" x2="{self.x + self.w}" y1="{yy:.1f}" y2="{yy:.1f}"/>'
                         f'<text class="muted" x="{self.x - 8}" y="{yy + 4:.1f}" font-size="12" '
                         f'text-anchor="end">{fmt_num(t)}</text>')
        parts.append(f'<line class="axis" x1="{self.x}" x2="{self.x + self.w}" y1="{self.y + self.h}" '
                     f'y2="{self.y + self.h}"/>')
        parts.append(f'<text x="{self.x - 50}" y="{self.y - 22}" font-size="13" font-weight="600">{esc(y_title)}</text>')
        for v, label in (x_ticks or []):
            parts.append(f'<text class="muted" x="{self.sx(v):.1f}" y="{self.y + self.h + 18}" font-size="12" '
                         f'text-anchor="middle">{esc(label)}</text>')
        if x_title:
            parts.append(f'<text class="muted" x="{self.x + self.w / 2}" y="{self.y + self.h + 38}" font-size="12" '
                         f'text-anchor="middle">{esc(x_title)}</text>')
        return ''.join(parts)


def legend(items, x, y):
    out, cx = [], x
    for key, label in items:
        out.append(f'<rect class="s-{key}" x="{cx}" y="{y - 10}" width="12" height="12" rx="3"/>'
                   f'<text x="{cx + 18}" y="{y}" font-size="13">{esc(label)}</text>')
        cx += 30 + 8.5 * len(label)
    return ''.join(out)


def end_labels(items, x, gap=15):
    """Direct labels at the right end of lines, nudged apart so they never overlap."""
    items = sorted(items, key=lambda t: t[0])
    placed = []
    for y, text in items:
        if placed and y - placed[-1][0] < gap:
            y = placed[-1][0] + gap
        placed.append((y, text))
    return ''.join(f'<text x="{x}" y="{y + 4:.1f}" font-size="12">{esc(t)}</text>' for y, t in placed)


def best_so_far(run, e):
    best = None
    for point in run.get('trace') or []:
        if point['evaluations'] <= e:
            best = point['objectives']
        else:
            break
    return best


def convergence_svg(results, mode='weekly'):
    runs = defaultdict(list)
    for r in results:
        if r['room_mode'] == mode and ok(r) and r.get('trace'):
            runs[r['algorithm']].append(r)
    if not runs:
        return None
    budget = max(r['budget'] for rs in runs.values() for r in rs)
    grid = sorted({1, *range(5, budget + 1, 5), budget})
    panels = [(0, 'คาบที่ยังจัดไม่ได้ของคำตอบดีสุด', 1), (1, 'Lab ไม่จำเป็นของคำตอบดีสุด (ชม.)', 1 / 60)]
    series = {}
    for method, rs in runs.items():
        for idx, _, scale in panels:
            pts = []
            for e in grid:
                vals = [b[idx] * scale for b in (best_so_far(r, e) for r in rs) if b is not None]
                if vals:
                    q = statistics.quantiles(vals, n=4, method='inclusive') if len(vals) > 1 else [vals[0]] * 3
                    pts.append((e, q[0], statistics.median(vals), q[2]))
            series[(method, idx)] = pts
    width, height = 980, 440
    body = []
    for col, (idx, title, _) in enumerate(panels):
        # Zoom the x axis when every search method has settled (upper quartile flat) well before the budget.
        span = budget
        settled = [max((e for e, lo, med, hi in pts if hi != pts[-1][3]), default=0)
                   for (m, i), pts in series.items() if i == idx and m != 'greedy']
        if settled and max(settled) * 4 < budget:
            span = int(max(20, nice_ticks(0, max(settled) * 2, 4)[-1]))
        values = [v for (m, i), pts in series.items() if i == idx for q in pts if q[0] <= span for v in q[1:]]
        p = Panel(70 + col * 480, 70, 360, 290, min(0, min(values)), max(values), 0, span)
        labels = []
        xt = [(t, fmt_num(t)) for t in nice_ticks(0, span, 5) if t <= span]
        x_title = 'จำนวน evaluations' + (f' ({span} ครั้งแรกจาก {budget})' if span < budget else '')
        body.append(p.frame(title, x_title, xt))
        for method in METHODS:
            pts = [q for q in series.get((method, idx)) or [] if q[0] <= span]
            if not pts:
                continue
            if method != 'greedy':
                upper = ' '.join(f'{p.sx(e):.1f},{p.sy(hi):.1f}' for e, lo, med, hi in pts)
                lower = ' '.join(f'{p.sx(e):.1f},{p.sy(lo):.1f}' for e, lo, med, hi in reversed(pts))
                body.append(f'<polygon class="band s-{method}" points="{upper} {lower}"/>')
                line = ' '.join(f'{p.sx(e):.1f},{p.sy(med):.1f}' for e, lo, med, hi in pts)
                body.append(f'<polyline class="line s-{method}" style="fill:none" points="{line}">'
                            f'<title>{LONG[method]}: median {fmt_num(pts[-1][2])} ที่ {budget} evaluations</title>'
                            f'</polyline>')
            else:
                yy = p.sy(pts[0][2])
                body.append(f'<line class="ref s-greedy" x1="{p.x}" x2="{p.x + p.w}" y1="{yy:.1f}" y2="{yy:.1f}">'
                            f'<title>Greedy: {fmt_num(pts[0][2])}</title></line>')
            labels.append((p.sy(pts[-1][2]), LABEL[method]))
        body.append(end_labels(labels, p.x + p.w + 6))
    present = [m for m in METHODS if m in runs]
    body.append(legend([(m, LONG[m] + (' (เส้นประ)' if m == 'greedy' else '')) for m in present], 70, 420))
    body.append(f'<text class="muted" x="{width - 20}" y="420" font-size="12" text-anchor="end">'
                f'เส้น = มัธยฐาน, แถบ = IQR ของ {len(next(iter(runs.values())))} seeds</text>')
    return svg_doc(width, height, f'Convergence ({mode})',
                   'มัธยฐานและช่วงควอไทล์ของคำตอบดีสุดตามจำนวน evaluations แยกตามวิธี', ''.join(body))


def boxplot_svg(results, key='unnecessary_lab_hours', mode='weekly', title='Lab ไม่จำเป็น (ชม.) ต่อรัน'):
    groups = [(m, [value(r, key) for r in results if r['algorithm'] == m and r['room_mode'] == mode and ok(r)])
              for m in METHODS]
    groups = [(m, v) for m, v in groups if v]
    if not groups:
        return None
    allv = [x for _, v in groups for x in v]
    width, height = 720, 420
    p = Panel(80, 60, 600, 290, min(allv), max(allv) + (max(allv) - min(allv)) * 0.08, -0.5, len(groups) - 0.5)
    body = [p.frame(f'{title} · โหมด {mode}', None, [(i, LONG[m]) for i, (m, _) in enumerate(groups)])]
    for i, (m, v) in enumerate(groups):
        d = describe(v)
        cx, half = p.sx(i), 34
        iqr = d['q3'] - d['q1']
        lo = min(x for x in v if x >= d['q1'] - 1.5 * iqr)
        hi = max(x for x in v if x <= d['q3'] + 1.5 * iqr)
        tip = (f"{LONG[m]}: median {d['median']:.1f}, IQR {d['q1']:.1f}–{d['q3']:.1f}, "
               f"min {d['best']:.1f}, max {d['worst']:.1f}, n={d['n']}")
        body.append(f'<g><title>{esc(tip)}</title>'
                    f'<line class="s-{m}" x1="{cx}" x2="{cx}" y1="{p.sy(lo):.1f}" y2="{p.sy(d["q1"]):.1f}" stroke-width="2"/>'
                    f'<line class="s-{m}" x1="{cx}" x2="{cx}" y1="{p.sy(d["q3"]):.1f}" y2="{p.sy(hi):.1f}" stroke-width="2"/>'
                    f'<rect class="s-{m}" x="{cx - half}" y="{p.sy(d["q3"]):.1f}" width="{2 * half}" '
                    f'height="{max(2, p.sy(d["q1"]) - p.sy(d["q3"])):.1f}" rx="4" fill-opacity=".25" stroke-width="2"/>'
                    f'<line class="s-{m}" x1="{cx - half}" x2="{cx + half}" y1="{p.sy(d["median"]):.1f}" '
                    f'y2="{p.sy(d["median"]):.1f}" stroke-width="3"/>')
        for x in v:
            if x < lo or x > hi:
                body.append(f'<circle class="s-{m}" cx="{cx}" cy="{p.sy(x):.1f}" r="4"/>')
        body.append(f'</g><text x="{cx + half + 6}" y="{p.sy(d["median"]) + 4:.1f}" font-size="12">'
                    f'{d["median"]:.1f}</text>')
    body.append(f'<text class="muted" x="80" y="400" font-size="12">กล่อง = IQR, เส้นกลาง = มัธยฐาน, '
                f'หนวด = 1.5×IQR, จุด = ค่าที่อยู่นอกหนวด</text>')
    return svg_doc(width, height, title, f'Box plot ของ {title} แยกตามวิธี', ''.join(body))


def mode_svg(results):
    keys = [('unassigned_weekly_sessions', 'คาบที่ยังจัดไม่ได้ (ค่าเฉลี่ย)'),
            ('unnecessary_lab_hours', 'Lab ไม่จำเป็น (ชม., ค่าเฉลี่ย)')]
    methods = [m for m in METHODS if any(r['algorithm'] == m and r['room_mode'] == 'fixed' for r in results)]
    if not methods:
        return None
    width, height = 960, 430
    body = []
    for col, (key, title) in enumerate(keys):
        means = {(m, mode): statistics.fmean(value(r, key) for r in results if r['algorithm'] == m
                                             and r['room_mode'] == mode and ok(r))
                 for m in methods for mode in ('weekly', 'fixed')}
        p = Panel(80 + col * 470, 60, 390, 290, 0, max(means.values()), -0.5, len(methods) - 0.5)
        body.append(p.frame(title, None, [(i, LABEL[m]) for i, m in enumerate(methods)]))
        bw = 30
        for i, m in enumerate(methods):
            for j, mode in enumerate(('weekly', 'fixed')):
                v = means[(m, mode)]
                x = p.sx(i) - bw - 1 + j * (bw + 2)
                y0, y1 = p.sy(0), p.sy(v)
                hgt = max(0.0, y0 - y1)
                r = min(4, hgt / 2, bw / 2)
                path = (f'M{x},{y0} V{y1 + r} Q{x},{y1} {x + r},{y1} H{x + bw - r} Q{x + bw},{y1} {x + bw},{y1 + r} '
                        f'V{y0} Z')
                body.append(f'<path class="s-{MODE_COLOR[mode]}" d="{path}"><title>{LONG[m]} · {mode}: '
                            f'{v:,.1f}</title></path>')
                body.append(f'<text x="{x + bw / 2}" y="{y1 - 6:.1f}" font-size="11" text-anchor="middle">'
                            f'{fmt_num(v)}</text>')
    body.append(legend([('hc', MODE_TH['weekly']), ('sa', MODE_TH['fixed'])], 80, 410))
    return svg_doc(width, height, 'Weekly vs fixed', 'ค่าเฉลี่ยของคาบที่ยังจัดไม่ได้และ Lab ไม่จำเป็นต่อวิธี แยกโหมดห้อง',
                   ''.join(body))


def room_change_svg(analysis):
    rows = [v for v in analysis['methods'].values() if v['room_mode'] == 'weekly']
    if not rows:
        return None
    bound = analysis['dataset_lower_bound']
    width, height = 720, 420
    top = max(max(r['room_changes']['worst'] for r in rows), bound)
    p = Panel(80, 60, 600, 290, 0, top, -0.5, len(rows) - 0.5)
    body = [p.frame('จำนวนเปลี่ยนห้อง (ครั้ง/เทอม) · weekly', None,
                    [(i, LONG[r['algorithm']]) for i, r in enumerate(rows)])]
    bw = 56
    for i, r in enumerate(rows):
        d = r['room_changes']
        x, y0, y1 = p.sx(i) - bw / 2, p.sy(0), p.sy(d['mean'])
        path = f'M{x},{y0} V{y1 + 4} Q{x},{y1} {x + 4},{y1} H{x + bw - 4} Q{x + bw},{y1} {x + bw},{y1 + 4} V{y0} Z'
        body.append(f'<path class="s-{r["algorithm"]}" d="{path}"><title>{LONG[r["algorithm"]]}: mean '
                    f'{d["mean"]:.1f} (min {d["best"]}, max {d["worst"]})</title></path>'
                    f'<line class="axis" x1="{p.sx(i)}" x2="{p.sx(i)}" y1="{p.sy(d["best"]):.1f}" '
                    f'y2="{p.sy(d["worst"]):.1f}" stroke-width="2"/>'
                    f'<text x="{p.sx(i)}" y="{p.sy(d["worst"]) - 8:.1f}" font-size="12" text-anchor="middle">'
                    f'{d["mean"]:.0f} ({d["mean"] / bound:.2f}×)</text>')
    yy = p.sy(bound)
    body.append(f'<line class="ref" style="stroke:var(--ink)" x1="{p.x}" x2="{p.x + p.w}" y1="{yy:.1f}" y2="{yy:.1f}"/>'
                f'<text x="{p.x + p.w + 6}" y="{yy + 4:.1f}" font-size="12">{bound}</text>')
    body.append(f'<text class="muted" x="80" y="392" font-size="12">แท่ง = ค่าเฉลี่ย, เส้นตั้ง = ต่ำสุด–สูงสุด, '
                f'ตัวเลขในวงเล็บ = เท่าของ lower bound</text><text class="muted" x="80" y="410" font-size="12">'
                f'เส้นประ = lower bound {bound} ครั้ง (ถ้าจัดครบทุกคาบและไม่ใช้ Lab เกินจำเป็น)</text>')
    return svg_doc(width, height, 'Room changes vs lower bound',
                   'จำนวนการเปลี่ยนห้องต่อเทอมของแต่ละวิธีเทียบกับ lower bound ของข้อมูล', ''.join(body))


# --- report ------------------------------------------------------------------
def f1(v, d=1):
    return '-' if v is None else f'{v:,.{d}f}'


def p_text(p):
    return '< 0.001' if p < 0.001 else f'{p:.3f}'


def report(rows, tests, modes, changes, charts):
    lines = ['# ผลวิเคราะห์การทดลอง', '',
             'สร้างโดย `python/analyze.py` จากผลดิบ ห้ามแก้ตัวเลขด้วยมือ กติกาอยู่ใน [docs/protocol.md](../../../docs/protocol.md)', '']
    lines += ['## ตารางสรุปต่อวิธี', '',
              'ค่าเฉลี่ย ± ส่วนเบี่ยงเบนมาตรฐาน · มัธยฐาน · ดีสุด–แย่สุด จากรันที่ผ่านตัวตรวจ', '',
              '| โหมด | วิธี | ผ่านตัวตรวจ | จัดครบทุกคาบ | ' + ' | '.join(label for _, label, _ in METRICS) + ' |',
              '|---|---|---:|---:|' + '---|' * len(METRICS)]
    for r in rows:
        cells = []
        for key, _, _ in METRICS:
            d = r[key]
            cells.append('-' if not d['n'] else f"{f1(d['mean'])} ± {f1(d['std'])} · {f1(d['median'])} · "
                                                f"{f1(d['best'])}–{f1(d['worst'])}")
        lines.append(f"| {r['room_mode']} | {LONG.get(r['algorithm'], r['algorithm'])} | {r['valid_runs']}/{r['runs']} | "
                     f"{r['success_rate']:.0%} | " + ' | '.join(cells) + ' |')
    if tests:
        fr = tests['friedman']
        names = ', '.join(f"{LONG[m]} {rk:.2f}" for m, rk in zip(fr['methods'], fr['mean_ranks']))
        lines += ['', '## สถิติ (โหมด weekly)', '',
                  f"**Friedman test** (n = {fr['n']} seeds, {len(fr['methods'])} วิธี, จัดอันดับแบบ lexicographic): "
                  f"χ² = {fr['statistic']:.2f}, df = {fr['df']}, p = {p_text(fr['p_value'])}. "
                  f"อันดับเฉลี่ย (น้อย = ดี): {names}.", '',
                  ('→ อย่างน้อยหนึ่งวิธีให้ผลต่างจากวิธีอื่นอย่างมีนัยสำคัญที่ α = 0.05 จึงเทียบรายคู่ต่อ'
                   if fr['significant'] else '→ ไม่พบความต่างอย่างมีนัยสำคัญระหว่างวิธีที่ α = 0.05 '
                                             '(ผลรายคู่ด้านล่างแสดงไว้เพื่ออ้างอิง ไม่ใช้สรุป)'), '',
                  '| คู่ (A vs B) | A ดีกว่า / เสมอ / B ดีกว่า | Δ มัธยฐาน คาบที่ยังจัดไม่ได้ | Δ มัธยฐาน Lab ไม่จำเป็น (ชม.) | '
                  'Δ มัธยฐาน เปลี่ยนห้อง | z | p (Holm) | สรุป |',
                  '|---|---:|---:|---:|---:|---:|---:|---|']
        for pr in tests['pairwise']:
            md = pr['median_difference_a_minus_b']
            a, b = LONG[pr['a']], LONG[pr['b']]
            if pr['significant']:
                better = a if pr['a_better'] > pr['b_better'] else b
                verdict = f'{better} ดีกว่าอย่างมีนัยสำคัญ'
            else:
                verdict = 'ไม่ต่างอย่างมีนัยสำคัญ'
            lines.append(f"| {a} vs {b} | {pr['a_better']} / {pr['ties']} / {pr['b_better']} | "
                         f"{md['unassigned_weekly_sessions']:+.1f} | {md['unnecessary_lab_hours']:+.1f} | "
                         f"{md['room_changes']:+.1f} | {pr['z']:.2f} | {p_text(pr['p_holm'])} | {verdict} |")
        lines += ['', 'Δ = A − B (ติดลบ = A ดีกว่าใน metric นั้น) · Wilcoxon signed-rank แบบจับคู่ตาม seed บน energy '
                      '(คงลำดับ lexicographic) ปรับ p ด้วย Holm ทั้ง 6 คู่', '', '**อ่านแบบสั้น:**', '']
        for pr in tests['pairwise']:
            a, b = LONG[pr['a']], LONG[pr['b']]
            if pr['significant']:
                win, lose = (a, b) if pr['a_better'] > pr['b_better'] else (b, a)
                n_win = max(pr['a_better'], pr['b_better'])
                lines.append(f"- {win} ให้ตารางดีกว่า {lose} ใน {n_win} จาก {pr['n']} seed และความต่างนี้ไม่น่าเกิดจากความบังเอิญ "
                             f"(p ปรับแล้ว = {p_text(pr['p_holm'])})")
            else:
                lines.append(f"- {a} กับ {b}: ชนะกันไปมา ({pr['a_better']} ต่อ {pr['b_better']} seed, เสมอ {pr['ties']}) "
                             f"ยังสรุปไม่ได้ว่าวิธีไหนดีกว่า (p ปรับแล้ว = {p_text(pr['p_holm'])})")
    if modes:
        lines += ['', '## ห้องรายสัปดาห์ (weekly) เทียบ ห้องคงที่ (fixed)', '',
                  'จับคู่ตาม seed (initial genome เดียวกัน) · Δ = fixed − weekly · Wilcoxon แบบจับคู่ ปรับ Holm ภายในแต่ละ metric', '',
                  '| metric | วิธี | คู่ | fixed มากกว่า | Δ เฉลี่ย | Δ มัธยฐาน | p (Holm) |',
                  '|---|---|---:|---:|---:|---:|---:|']
        names = {'unnecessary_lab_hours': 'Lab ไม่จำเป็น (ชม.)', 'unassigned_weekly_sessions': 'คาบที่ยังจัดไม่ได้'}
        for m in modes:
            lines.append(f"| {names[m['metric']]} | {LONG[m['algorithm']]} | {m['n']} | {m['fixed_higher']} / {m['n']} | "
                         f"{m['mean_fixed_minus_weekly']:+,.1f} | {m['median_fixed_minus_weekly']:+,.1f} | "
                         f"{p_text(m['p_holm'])} |")
        lab = [m for m in modes if m['metric'] == 'unnecessary_lab_hours']
        if lab:
            lo = min(m['mean_fixed_minus_weekly'] for m in lab)
            hi = max(m['mean_fixed_minus_weekly'] for m in lab)
            all_higher = all(m['fixed_higher'] == m['n'] for m in lab)
            lines += ['', f"**อ่านแบบสั้น:** ห้องคงที่ทำให้ Lab ถูกครองโดยไม่ได้ใช้เพิ่มขึ้นเฉลี่ย {lo:,.0f}–{hi:,.0f} ชม. ต่อเทอม"
                          f"{' ทุกวิธีและทุก seed' if all_higher else ''} ส่วนโหมด weekly แลกด้วยการเปลี่ยนห้อง "
                          f"(fixed = 0 ตามนิยาม)"]
    if changes and changes['methods']:
        bound = changes['dataset_lower_bound']
        lines += ['', '## จำนวนการเปลี่ยนห้องเทียบกับค่าต่ำสุดที่เป็นไปได้ (#10)', '',
                  f"**Lower bound ของข้อมูล = {bound:,} ครั้ง**: ทุกคาบที่สลับระหว่างสัปดาห์ที่ต้องใช้ Lab กับสัปดาห์ที่ไม่ต้องใช้ "
                  "ต้องเปลี่ยนประเภทห้อง จึงต้องเปลี่ยนห้องอย่างน้อยหนึ่งครั้งต่อการสลับ ถ้าจะจัดครบทุกคาบและไม่ใช้ Lab เกินจำเป็น "
                  "(ถ้ายอมใช้ Lab เกินจำเป็น ค่านี้ลดลงได้จนเป็น 0 แบบห้องคงที่)", '',
                  '| โหมด | วิธี | เปลี่ยนห้อง เฉลี่ย (ต่ำสุด–สูงสุด) | เท่าของ lower bound | '
                  'เปลี่ยนเกินจากการสลับประเภทห้องในตารางนั้นเอง | Lab ไม่จำเป็น (ชม.) |',
                  '|---|---|---:|---:|---:|---:|']
        for v in changes['methods'].values():
            d, ratio = v['room_changes'], v['ratio_to_dataset_bound']
            lines.append(f"| {v['room_mode']} | {LONG[v['algorithm']]} | {d['mean']:,.1f} ({d['best']}–{d['worst']}) | "
                         f"{ratio['mean']:.2f}× | {v['changes_above_own_kind_switches']['mean']:,.1f} | "
                         f"{v['unnecessary_lab_hours']['mean']:,.1f} |")
        lines += ['', 'จำนวนคลาส (174 คลาส) ตามจำนวนครั้งที่เปลี่ยนห้องทั้งเทอม (ค่าเฉลี่ยต่อรัน):', '',
                  '| | ' + ' | '.join(name for name, _ in BUCKETS) + ' |', '|---|' + '---:|' * len(BUCKETS),
                  '| lower bound ของข้อมูล | ' + ' | '.join(str(changes['lower_bound_class_buckets'][n]) for n, _ in BUCKETS) + ' |']
        for v in changes['methods'].values():
            lines.append(f"| {v['room_mode']} · {LONG[v['algorithm']]} | " +
                         ' | '.join(f"{v['mean_class_buckets'][n]:.1f}" for n, _ in BUCKETS) + ' |')
        weekly = [v for v in changes['methods'].values() if v['room_mode'] == 'weekly' and v['algorithm'] != 'greedy']
        fixed = [v for v in changes['methods'].values() if v['room_mode'] == 'fixed']
        if weekly:
            lo = min(v['ratio_to_dataset_bound']['mean'] for v in weekly)
            hi = max(v['ratio_to_dataset_bound']['mean'] for v in weekly)
            extra = statistics.fmean(v['changes_above_own_kind_switches']['mean'] for v in weekly)
            text = (f"**สรุปสำหรับสไลด์:** ตัวเลขเปลี่ยนห้องราว {statistics.fmean(v['room_changes']['mean'] for v in weekly):,.0f} "
                    f"ครั้งต่อเทอมดูเยอะ แต่ส่วนใหญ่หลีกเลี่ยงไม่ได้ ข้อมูลนี้บังคับให้เปลี่ยนอย่างน้อย {bound:,} ครั้ง "
                    f"เพราะ 134 คาบต้องสลับเข้าออก Lab ตามสัปดาห์ คำตอบของ HC/SA/GA อยู่ที่ {lo:.2f}–{hi:.2f} เท่าของค่าต่ำสุดนี้ "
                    f"และเปลี่ยนเกินจากการสลับประเภทห้องที่ตารางนั้นบังคับเองเฉลี่ยเพียง {extra:,.0f} ครั้ง")
            if fixed:
                lab_w = statistics.fmean(v['unnecessary_lab_hours']['mean'] for v in weekly)
                lab_f = statistics.fmean(v['unnecessary_lab_hours']['mean'] for v in fixed)
                text += (f" ถ้าใช้ห้องคงที่ การเปลี่ยนห้องเป็น 0 แต่ต้องแลกกับ Lab ที่ถูกครองโดยไม่ได้ใช้เพิ่มจากราว "
                         f"{lab_w:,.0f} เป็น {lab_f:,.0f} ชม. ต่อเทอม (เพิ่มราว {lab_f - lab_w:,.0f} ชม.)")
            lines += ['', text]
    lines += ['', '## กราฟ', ''] + [f'![{name}]({name})' for name in charts]
    return '\n'.join(lines) + '\n'


def analyze(paths, output):
    results, dataset = load(paths)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = summary_rows(results)
    tests = method_tests(results, 'weekly')
    modes = mode_tests(results) if any(r['room_mode'] == 'fixed' for r in results) else []
    changes = room_change_analysis(results, dataset) if dataset else None
    with (output / 'summary.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(['room_mode', 'algorithm', 'runs', 'valid_runs', 'time_limited_runs', 'success_rate', 'metric',
                         'mean', 'median', 'std', 'best', 'worst', 'q1', 'q3'])
        for r in rows:
            for key, _, _ in METRICS:
                d = r[key]
                writer.writerow([r['room_mode'], r['algorithm'], r['runs'], r['valid_runs'], r['time_limited_runs'],
                                 r['success_rate'], key, d['mean'], d['median'], d['std'], d['best'], d['worst'],
                                 d['q1'], d['q3']])
    bound = room_change_bound(dataset)[0] if dataset else None
    with (output / 'runs.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(['config_id', 'room_mode', 'algorithm', 'seed', 'budget', 'status', 'valid',
                         'unassigned_weekly_sessions', 'unnecessary_lab_hours', 'room_changes',
                         'room_change_lower_bound', 'room_changes_to_lower_bound', 'room_kind_switches', 'energy',
                         'search_seconds'])
        for r in sorted(results, key=lambda r: (r['room_mode'] != 'weekly', METHODS.index(r['algorithm'])
                                                if r['algorithm'] in METHODS else 9, r['seed'])):
            good = ok(r)
            m = r.get('metrics') or {}
            kind = run_kind_switches(r, dataset) if good and dataset and r.get('solution') else None
            writer.writerow([r.get('config_id', 'main'), r['room_mode'], r['algorithm'], r['seed'], r.get('budget'),
                             r['status'], r.get('valid'), m.get('unassigned_weekly_sessions'),
                             m.get('unnecessary_lab_hours'), m.get('room_changes'), bound,
                             round(m['room_changes'] / bound, 4) if good and bound else None, kind,
                             energy(r) if good else None, round(r['search_seconds'], 3)])
    (output / 'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'stats.json').write_text(json.dumps({'methods': tests, 'weekly_vs_fixed': modes, 'room_changes': changes},
                                                  ensure_ascii=False, indent=2), encoding='utf-8')
    charts = {}
    for name, svg in [('convergence.svg', convergence_svg(results)), ('lab-hours-boxplot.svg', boxplot_svg(results)),
                      ('weekly-vs-fixed.svg', mode_svg(results)),
                      ('room-changes.svg', room_change_svg(changes) if changes else None)]:
        if svg:
            (output / name).write_text(svg, encoding='utf-8')
            charts[name] = True
    (output / 'report.md').write_text(report(rows, tests, modes, changes, charts), encoding='utf-8')
    return {'rows': rows, 'tests': tests, 'modes': modes, 'changes': changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    analyze(args.inputs, args.output)
    print('Saved', args.output)


if __name__ == '__main__':
    main()
