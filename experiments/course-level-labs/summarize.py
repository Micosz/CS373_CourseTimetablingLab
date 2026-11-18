"""Summarise the course-level Lab experiment: summary.csv, a Markdown table and summary.svg.

    python experiments/course-level-labs/summarize.py
"""
import csv
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVELS = (1, 2, 4, 6, 8, 10, 12, 15)
METHODS = ('greedy', 'hc', 'sa', 'ga')
SEARCH = ('hc', 'sa', 'ga')
LABEL = {'greedy': 'Greedy', 'hc': 'HC', 'sa': 'SA', 'ga': 'GA'}

rows = []
for level in LEVELS:
    with open(HERE / f'w{level:02d}' / 'experiment.csv', encoding='utf-8-sig') as f:
        runs = list(csv.DictReader(f))
    assert len(runs) == 80 and all(r['valid'] == 'True' and r['hard_violations'] == '0' for r in runs), level
    by = defaultdict(list)
    for r in runs:
        by[(r['room_mode'], r['algorithm'])].append(r)
    for mode in ('weekly', 'fixed'):
        for method in METHODS:
            rs = by[(mode, method)]
            rows.append({
                'lab_weeks': level, 'room_mode': mode, 'algorithm': method, 'runs': len(rs),
                'complete_runs': sum(r['unassigned_weekly_sessions'] == '0' for r in rs),
                'mean_unassigned': round(statistics.fmean(float(r['unassigned_weekly_sessions']) for r in rs), 2),
                'mean_unnecessary_lab_hours': round(statistics.fmean(float(r['unnecessary_lab_hours']) for r in rs), 2),
                'mean_room_changes': round(statistics.fmean(float(r['room_changes']) for r in rs), 2)})
with open(HERE / 'summary.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

cell = {(r['lab_weeks'], r['room_mode'], r['algorithm']): r for r in rows}


def best(level, mode, key):
    """Lowest mean among the three search methods at this level."""
    return min(cell[(level, mode, m)][key] for m in SEARCH)


print('| สัปดาห์ Lab ต่อวิชา | Greedy: คาบที่จัดไม่ได้ | HC | SA | GA | รันที่จัดครบ (HC / SA / GA) | '
      'Lab ไม่จำเป็น ชม. (HC / SA / GA) | ห้องคงที่: คาบที่จัดไม่ได้ (HC / SA / GA) |')
print('|---:|---:|---:|---:|---:|---|---|---|')
for level in LEVELS:
    c = lambda mode, m, k: cell[(level, mode, m)][k]
    print(f"| {level} | {c('weekly', 'greedy', 'mean_unassigned'):.1f} | "
          + ' | '.join(f"{c('weekly', m, 'mean_unassigned'):.1f}" for m in SEARCH) + ' | '
          + ' / '.join(f"{c('weekly', m, 'complete_runs')}" for m in SEARCH) + ' | '
          + ' / '.join(f"{c('weekly', m, 'mean_unnecessary_lab_hours'):.0f}" for m in SEARCH) + ' | '
          + ' / '.join(f"{c('fixed', m, 'mean_unassigned'):.0f}" for m in SEARCH) + ' |')

# Two panels, one scale each. Series differ by dash pattern and marker shape, not by colour alone.
SERIES = [('ห้องคงที่ + ค้นหา', 'fixed', None, '#b45309', '7 5', 'square'),
          ('รายสัปดาห์ + Greedy', 'weekly', 'greedy', '#475569', '2 4', 'triangle'),
          ('รายสัปดาห์ + ค้นหา', 'weekly', None, '#1d4ed8', '', 'circle')]
PANELS = [('คาบที่จัดห้องไม่ได้ (เฉลี่ย 10 seed)', 'mean_unassigned'),
          ('Lab ที่ใช้โดยไม่จำเป็น ชม. ต่อเทอม', 'mean_unnecessary_lab_hours')]
W, H, L, T, PW, PH, GAP = 980, 400, 60, 70, 370, 250, 110


def marker(shape, x, y, color):
    if shape == 'square':
        return f'<rect x="{x - 4.5:.1f}" y="{y - 4.5:.1f}" width="9" height="9" fill="{color}"/>'
    if shape == 'triangle':
        return f'<path d="M{x:.1f} {y - 6:.1f} L{x + 5.5:.1f} {y + 4:.1f} L{x - 5.5:.1f} {y + 4:.1f} Z" fill="{color}"/>'
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{color}"/>'


svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="13">',
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
for i, (name, _, _, color, dash, shape) in enumerate(SERIES):
    x = L + i * 250
    svg.append(f'<line x1="{x}" y1="26" x2="{x + 44}" y2="26" stroke="{color}" stroke-width="2.5" stroke-dasharray="{dash}"/>')
    svg.append(marker(shape, x + 22, 26, color))
    svg.append(f'<text x="{x + 52}" y="30" fill="#111827">{name}</text>')
for p, (title, key) in enumerate(PANELS):
    x0 = L + p * (PW + GAP)
    data = [[(cell[(lv, mode, m)][key] if m else best(lv, mode, key)) for lv in LEVELS] for _, mode, m, *_ in SERIES]
    top = max(max(d) for d in data)
    step = next(s for s in (10, 25, 50, 100, 250, 500, 1000) if top / s <= 6)
    top = step * -(-top // step)
    px = lambda lv: x0 + (lv - 1) / 14 * PW
    py = lambda v: T + PH - v / top * PH
    svg.append(f'<text x="{x0}" y="{T - 14}" fill="#111827" font-weight="bold">{title}</text>')
    for k in range(int(top // step) + 1):
        y = py(k * step)
        svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + PW}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        svg.append(f'<text x="{x0 - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#4b5563">{k * step:,}</text>')
    for lv in LEVELS:
        svg.append(f'<text x="{px(lv):.1f}" y="{T + PH + 20}" text-anchor="middle" fill="#4b5563">{lv}</text>')
    svg.append(f'<text x="{x0 + PW / 2}" y="{T + PH + 44}" text-anchor="middle" fill="#111827">'
               'จำนวนสัปดาห์ที่วิชาใช้ Lab (จาก 15)</text>')
    for (_, _, _, color, dash, shape), d in zip(SERIES, data):
        pts = ' '.join(f'{px(lv):.1f},{py(v):.1f}' for lv, v in zip(LEVELS, d))
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" stroke-dasharray="{dash}"/>')
        svg += [marker(shape, px(lv), py(v), color) for lv, v in zip(LEVELS, d)]
svg.append('</svg>')
(HERE / 'summary.svg').write_text('\n'.join(svg), encoding='utf-8')
