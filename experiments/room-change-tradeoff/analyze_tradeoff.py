"""Summarise the room-change penalty study (run.py). Standard library only.

    python experiments/room-change-tradeoff/analyze_tradeoff.py

Reads the runs of this folder (``runs/`` while the batch is unmerged, otherwise
``experiment.json.gz``) and experiments/final for two things: a check that the
penalty-0 runs reproduce the stored final runs exactly, and the fixed-room
reference on the same seeds. Writes per-run.csv, summary.csv, summary.json,
tradeoff-by-penalty.svg and tradeoff-complete-runs.svg.
"""
import csv
import gzip
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
import analyze  # noqa: E402

METHODS = ['greedy', 'hc', 'sa', 'ga']
FIRST = 1000000  # penalty that puts room changes before Lab minutes


def penalty_label(p):
    return 'เปลี่ยนห้องก่อน' if p >= FIRST else str(p)


def load_runs():
    runs_dir = HERE / 'runs'
    if runs_dir.is_dir() and any(runs_dir.glob('*.json')):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(runs_dir.glob('*.json'))]
    return json.loads(gzip.decompress((HERE / 'experiment.json.gz').read_bytes()))['batch']['results']


def triple(run):
    m = run['metrics']
    return (m['unassigned_weekly_sessions'], m['unnecessary_lab_minutes'], m['room_changes'])


def main():
    runs = load_runs()
    bad = [r for r in runs if not analyze.ok(r)]
    if bad:
        raise SystemExit(f'{len(bad)} runs are invalid or unfinished')
    seeds = sorted({r['seed'] for r in runs})
    penalties = sorted({r['change_penalty_minutes'] for r in runs})
    final, _ = analyze.load([ROOT / 'experiments/final/experiment.json.gz'])
    final = {(r['room_mode'], r['algorithm'], r['seed']): r for r in final if r['seed'] in seeds}

    # 1. Penalty 0 must be the original engine: same metrics and same best-so-far trace as experiments/final.
    zero = [r for r in runs if r['change_penalty_minutes'] == 0]
    same = sum(triple(r) == triple(final[('weekly', r['algorithm'], r['seed'])]) and
               [p['objectives'] for p in r['trace']] ==
               [p['objectives'] for p in final[('weekly', r['algorithm'], r['seed'])]['trace']] for r in zero)
    reproduction = {'penalty_0_runs': len(zero), 'identical_to_final': same}
    if same != len(zero):
        raise SystemExit(f'Penalty 0 does not reproduce experiments/final: {same} / {len(zero)}')

    # 2. Per-run table.
    order = {m: i for i, m in enumerate(METHODS)}
    runs.sort(key=lambda r: (r['change_penalty_minutes'], order[r['algorithm']], r['seed']))
    with (HERE / 'per-run.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(['change_penalty_minutes', 'algorithm', 'seed', 'unassigned_weekly_sessions',
                         'unnecessary_lab_hours', 'room_changes', 'evaluations'])
        for r in runs:
            m = r['metrics']
            writer.writerow([r['change_penalty_minutes'], r['algorithm'], r['seed'], m['unassigned_weekly_sessions'],
                             m['unnecessary_lab_hours'], m['room_changes'], r['evaluations']])

    # 3. Summary per (method, penalty): all runs, and the runs with no unassigned session.
    rows = []
    for method in METHODS:
        for p in penalties:
            rs = [r for r in runs if r['algorithm'] == method and r['change_penalty_minutes'] == p]
            if not rs:
                continue
            done = [r for r in rs if r['metrics']['unassigned_weekly_sessions'] == 0]
            mean = lambda group, key: statistics.fmean(r['metrics'][key] for r in group) if group else None
            rows.append({'algorithm': method, 'change_penalty_minutes': p, 'runs': len(rs),
                         'mean_unassigned': mean(rs, 'unassigned_weekly_sessions'),
                         'max_unassigned': max(r['metrics']['unassigned_weekly_sessions'] for r in rs),
                         'mean_lab_hours': mean(rs, 'unnecessary_lab_hours'),
                         'mean_room_changes': mean(rs, 'room_changes'),
                         'complete_runs': len(done),
                         'complete_mean_lab_hours': mean(done, 'unnecessary_lab_hours'),
                         'complete_mean_room_changes': mean(done, 'room_changes')})
    with (HERE / 'summary.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in row.items()})

    # 4. Complete weekly runs that no other complete run beats on both Lab hours and room changes.
    done = [r for r in runs if r['metrics']['unassigned_weekly_sessions'] == 0]
    point = lambda r: (r['metrics']['room_changes'], r['metrics']['unnecessary_lab_minutes'])
    front = [r for r in done if not any(
        point(o) != point(r) and point(o)[0] <= point(r)[0] and point(o)[1] <= point(r)[1] for o in done)]
    front.sort(key=point)
    front_rows = [{'algorithm': r['algorithm'], 'change_penalty_minutes': r['change_penalty_minutes'],
                   'seed': r['seed'], 'room_changes': r['metrics']['room_changes'],
                   'unnecessary_lab_hours': r['metrics']['unnecessary_lab_hours']} for r in front]

    # 5. Fixed-room reference on the same seeds (stored final runs; the penalty cannot affect fixed mode).
    fixed = []
    for method in METHODS:
        rs = [final[('fixed', method, s)] for s in seeds]
        fixed.append({'algorithm': method, 'runs': len(rs),
                      'mean_unassigned': statistics.fmean(r['metrics']['unassigned_weekly_sessions'] for r in rs),
                      'complete_runs': sum(r['metrics']['unassigned_weekly_sessions'] == 0 for r in rs),
                      'mean_lab_hours': statistics.fmean(r['metrics']['unnecessary_lab_hours'] for r in rs),
                      'mean_room_changes': statistics.fmean(r['metrics']['room_changes'] for r in rs)})

    (HERE / 'summary.json').write_text(json.dumps({
        'seeds': seeds, 'penalties': penalties, 'budget': sorted({r['budget'] for r in runs if r['algorithm'] != 'greedy'}),
        'reproduction_check': reproduction, 'by_method_and_penalty': rows,
        'complete_runs': len(done), 'non_dominated_complete_runs': front_rows,
        'fixed_room_reference_from_final': fixed}, ensure_ascii=False, indent=2), encoding='utf-8')
    (HERE / 'tradeoff-by-penalty.svg').write_text(by_penalty_svg(rows, penalties), encoding='utf-8')
    (HERE / 'tradeoff-complete-runs.svg').write_text(complete_svg(done, front), encoding='utf-8')

    print('penalty 0 identical to final:', same, '/', len(zero))
    print('| วิธี | ค่าปรับ (นาที/ครั้ง) | คาบที่ยังจัดไม่ได้ (เฉลี่ย) | รันที่จัดครบ | Lab ไม่จำเป็น (ชม.) | เปลี่ยนห้อง |')
    print('|---|---:|---:|---:|---:|---:|')
    for row in rows:
        print(f"| {analyze.LABEL[row['algorithm']]} | {penalty_label(row['change_penalty_minutes'])} | "
              f"{row['mean_unassigned']:.1f} | {row['complete_runs']} / {row['runs']} | "
              f"{row['mean_lab_hours']:,.1f} | {row['mean_room_changes']:,.1f} |")
    print('non-dominated complete runs:', len(front), 'of', len(done))
    for row in front_rows:
        print(' ', row)
    print('fixed reference:', fixed)


def by_penalty_svg(rows, penalties):
    width, height = 1180, 450
    body = []
    panels = [('mean_unassigned', 'คาบที่ยังจัดไม่ได้ (เฉลี่ย)'), ('mean_lab_hours', 'Lab ไม่จำเป็น (ชม., เฉลี่ย)'),
              ('mean_room_changes', 'เปลี่ยนห้อง (ครั้ง, เฉลี่ย)')]
    xs = {p: i for i, p in enumerate(penalties)}
    for col, (key, title) in enumerate(panels):
        values = [r[key] for r in rows]
        p = analyze.Panel(70 + col * 380, 70, 280, 290, 0, max(values), -0.3, len(penalties) - 0.7)
        body.append(p.frame(title, 'ค่าปรับต่อการเปลี่ยนห้อง 1 ครั้ง (นาทีของ Lab ไม่จำเป็น)',
                            [(xs[q], 'ก่อน' if q >= FIRST else str(q)) for q in penalties]))
        labels = []
        for method in METHODS:
            pts = [(xs[r['change_penalty_minutes']], r[key], r) for r in rows if r['algorithm'] == method]
            line = ' '.join(f'{p.sx(x):.1f},{p.sy(y):.1f}' for x, y, _ in pts)
            body.append(f'<polyline class="line s-{method}" style="fill:none" points="{line}"/>')
            for x, y, r in pts:
                body.append(f'<circle class="s-{method}" cx="{p.sx(x):.1f}" cy="{p.sy(y):.1f}" r="4.5" '
                            f'stroke="var(--surface)" stroke-width="2"><title>{analyze.LONG[method]} ค่าปรับ '
                            f'{penalty_label(r["change_penalty_minutes"])}: {y:,.1f}</title></circle>')
            labels.append((p.sy(pts[-1][1]), analyze.LABEL[method]))
        body.append(analyze.end_labels(labels, p.x + p.w + 6))
    body.append(analyze.legend([(m, analyze.LONG[m]) for m in METHODS], 70, 435))
    body.append('<text class="muted" x="1110" y="435" font-size="12" text-anchor="end">'
                '"ก่อน" = ลดการเปลี่ยนห้องก่อน Lab ไม่จำเป็น · เฉลี่ย 10 seed</text>')
    return analyze.svg_doc(width, height, 'Room-change penalty study',
                           'ค่าเฉลี่ยของคาบที่ยังจัดไม่ได้ Lab ไม่จำเป็น และการเปลี่ยนห้อง ตามค่าปรับการเปลี่ยนห้อง',
                           ''.join(body))


def complete_svg(done, front):
    width, height = 860, 520
    xs = [r['metrics']['room_changes'] for r in done]
    ys = [r['metrics']['unnecessary_lab_hours'] for r in done]
    ticks = analyze.nice_ticks(min(xs), max(xs))
    p = analyze.Panel(80, 70, 700, 360, 0, max(ys), ticks[0], ticks[-1])
    body = [p.frame('Lab ไม่จำเป็น (ชม.) ของรันที่จัดครบทุกคาบ', 'จำนวนครั้งที่เปลี่ยนห้องทั้งเทอม',
                    [(t, analyze.fmt_num(t)) for t in ticks])]
    if len(front) > 1:
        line = ' '.join(f'{p.sx(r["metrics"]["room_changes"]):.1f},{p.sy(r["metrics"]["unnecessary_lab_hours"]):.1f}'
                        for r in front)
        body.append(f'<polyline points="{line}" style="fill:none;stroke:var(--axis);stroke-width:1.5;'
                    'stroke-dasharray:5 4"/>')
    for r in done:
        m = r['metrics']
        body.append(f'<circle class="s-{r["algorithm"]}" cx="{p.sx(m["room_changes"]):.1f}" '
                    f'cy="{p.sy(m["unnecessary_lab_hours"]):.1f}" r="4.5" fill-opacity=".75" stroke="var(--surface)" '
                    f'stroke-width="1"><title>{analyze.LONG[r["algorithm"]]} ค่าปรับ '
                    f'{penalty_label(r["change_penalty_minutes"])} seed {r["seed"]}: เปลี่ยนห้อง {m["room_changes"]} ครั้ง '
                    f'Lab ไม่จำเป็น {m["unnecessary_lab_hours"]:.1f} ชม.</title></circle>')
    used = [m for m in METHODS if any(r['algorithm'] == m for r in done)]
    body.append(analyze.legend([(m, analyze.LONG[m]) for m in used], 80, 500))
    body.append('<text class="muted" x="780" y="500" font-size="12" text-anchor="end">'
                'เส้นประ = รันที่ไม่มีรันอื่นดีกว่าทั้งสองแกน</text>')
    return analyze.svg_doc(width, height, 'Complete weekly runs: room changes vs unnecessary Lab hours',
                           'แต่ละจุดคือหนึ่งรันโหมด weekly ที่จัดครบทุกคาบ แกนนอนคือจำนวนครั้งที่เปลี่ยนห้อง '
                           'แกนตั้งคือชั่วโมง Lab ไม่จำเป็น', ''.join(body))


if __name__ == '__main__':
    main()
