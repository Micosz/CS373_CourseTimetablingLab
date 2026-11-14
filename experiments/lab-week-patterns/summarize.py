"""Compare the Lab-week pattern variants with the main dataset on seeds 1001-1010 (issue #30).

    python3 experiments/lab-week-patterns/summarize.py
"""
import csv, json, statistics, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
import analyze  # noqa: E402

SEEDS = range(1001, 1011)
SETS = [('random (ชุดหลัก)', ROOT / 'experiments/final/experiment.json.gz'),
        ('consecutive', HERE / 'consecutive/experiment.json.gz'),
        ('alternate', HERE / 'alternate/experiment.json.gz')]
rows, ranks = [], {}
for name, path in SETS:
    results, _ = analyze.load([path])
    results = [r for r in results if r['seed'] in SEEDS and analyze.ok(r)]
    by = defaultdict(list)
    for r in results:
        by[(r['room_mode'], r['algorithm'])].append(r['metrics'])
    for (mode, method), ms in sorted(by.items()):
        rows.append({'pattern': name, 'room_mode': mode, 'algorithm': method, 'runs': len(ms),
                     'mean_unassigned': statistics.fmean(m['unassigned_weekly_sessions'] for m in ms),
                     'mean_unnecessary_lab_hours': statistics.fmean(m['unnecessary_lab_hours'] for m in ms),
                     'mean_room_changes': statistics.fmean(m['room_changes'] for m in ms)})
    t = analyze.method_tests(results, 'weekly')
    ranks[name] = {'friedman_p': t['friedman']['p_value'],
                   'mean_ranks': dict(zip(t['friedman']['methods'], t['friedman']['mean_ranks']))} if t else None
with open(HERE / 'summary.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
(HERE / 'ranks.json').write_text(json.dumps(ranks, indent=1, ensure_ascii=False), encoding='utf-8')
print('| รูปแบบสัปดาห์ Lab | โหมด | วิธี | คาบที่ยังจัดไม่ได้ | Lab ไม่จำเป็น (ชม.) | เปลี่ยนห้อง |')
print('|---|---|---|---:|---:|---:|')
for r in rows:
    print(f"| {r['pattern']} | {r['room_mode']} | {analyze.LABEL[r['algorithm']]} | {r['mean_unassigned']:.1f} | "
          f"{r['mean_unnecessary_lab_hours']:.1f} | {r['mean_room_changes']:.1f} |")
for k, v in ranks.items():
    print(k, {m: round(x, 2) for m, x in v['mean_ranks'].items()}, 'Friedman p', round(v['friedman_p'], 5))
