"""Mean metrics per SA setting of the extended grid (issue #32) -> summary.csv, printed as a Markdown table."""
import csv, statistics, sys
from pathlib import Path

here = Path(__file__).resolve().parent
rows = []
for d in sorted((here / 'configs').iterdir()):
    runs = list(csv.DictReader(open(d / 'experiment.csv', encoding='utf-8-sig')))
    ok = [r for r in runs if r['valid'] == 'True' and r['status'] == 'evaluation_budget']
    mean = lambda k: statistics.fmean(float(r[k]) for r in ok)
    a, c = d.name.removeprefix('sa-a').split('-c')
    rows.append({'config_id': d.name, 'initial_acceptance': float(a), 'cooling_rate': float(c), 'runs': len(runs),
                 'valid_runs': len(ok), 'mean_unassigned': mean('unassigned_weekly_sessions'),
                 'mean_unnecessary_lab_hours': mean('unnecessary_lab_hours'), 'mean_room_changes': mean('room_changes')})
rows.sort(key=lambda r: (r['mean_unassigned'], r['mean_unnecessary_lab_hours'], r['mean_room_changes']))
with open(here / 'summary.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
print('| อันดับ | acceptance | cooling | Lab ไม่จำเป็นเฉลี่ย (ชม.) | เปลี่ยนห้องเฉลี่ย | รันผ่าน |')
print('|---:|---:|---:|---:|---:|---:|')
for i, r in enumerate(rows, 1):
    print(f"| {i} | {r['initial_acceptance']:g} | {r['cooling_rate']:g} | {r['mean_unnecessary_lab_hours']:.1f} | "
          f"{r['mean_room_changes']:.1f} | {r['valid_runs']}/{r['runs']} |")
