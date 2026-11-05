"""Follow-up studies on the test-seed subset 1001-1010 (docs/protocol.md section 1). Standard library only.

    python python/studies.py budget   --final experiments/final/experiment.json.gz
    python python/studies.py scarcity --final experiments/final/experiment.json.gz --method sa

``budget`` (#8): HC, SA and GA at 50, 200 and 1000 evaluations with the tuned
parameters; the final experiment supplies the 500 point.
``scarcity`` (#13): the chosen method in both room modes on the 3- and 2-Lab
variants from dataset_tools/make_lab_variants.py; the final experiment
supplies the 4-Lab point.
Both resume from stored runs and write raw results, a CSV, an SVG and summary.md.
"""
import argparse
import csv
import json
import statistics
from pathlib import Path

import analyze
import batch

ROOT = batch.ROOT
SEEDS = list(range(1001, 1011))
PARAMS = ROOT / 'experiments' / 'tuning' / 'selected-parameters.json'
SECONDS = 3600


def tuned():
    data = json.loads(PARAMS.read_text(encoding='utf-8'))
    return {k: v for k, v in data.items() if not k.startswith('_')}


def final_runs(path, seeds=SEEDS):
    results, _ = analyze.load([path])
    return [r for r in results if r['seed'] in seeds]


def mean_or_none(values):
    return statistics.fmean(values) if values else None


# --- #8 budget ---------------------------------------------------------------
def budget_study(final, output, workers):
    output = Path(output)
    params = tuned()
    budgets = [50, 200, 1000]
    jobs = []
    for b in budgets:
        jobs += batch.build_jobs(['hc', 'sa', 'ga'], ['weekly'], SEEDS, b, SECONDS, params, config_id=f'b{b}')
    runs = batch.run_jobs(jobs, output, workers=workers, slim=True, name='Budget study 50/200/1000 (seeds 1001-1010)')
    batch.merge(output, name='Budget study 50/200/1000 (seeds 1001-1010)')
    base = [r for r in final_runs(final) if r['room_mode'] == 'weekly' and r['algorithm'] in ('hc', 'sa', 'ga')]
    if {r['budget'] for r in base} != {500}:
        raise ValueError('The final experiment must use budget 500 (protocol)')
    allruns = runs + base
    bad = [r for r in allruns if not analyze.ok(r)]
    levels = sorted({r['budget'] for r in allruns})
    rows = []
    for method in ('hc', 'sa', 'ga'):
        for b in levels:
            rs = [r for r in allruns if r['algorithm'] == method and r['budget'] == b and analyze.ok(r)]
            rows.append({'algorithm': method, 'budget': b, 'runs': len(rs),
                         'mean_unassigned': mean_or_none([r['metrics']['unassigned_weekly_sessions'] for r in rs]),
                         'success_rate': sum(r['metrics']['unassigned_weekly_sessions'] == 0 for r in rs) / len(rs),
                         'mean_lab_hours': mean_or_none([r['metrics']['unnecessary_lab_hours'] for r in rs]),
                         'median_lab_hours': statistics.median(r['metrics']['unnecessary_lab_hours'] for r in rs),
                         'mean_room_changes': mean_or_none([r['metrics']['room_changes'] for r in rs]),
                         'mean_search_seconds': mean_or_none([r['search_seconds'] for r in rs])})
    # Paired step tests: does each larger budget beat the previous one on the same seeds?
    steps = []
    for method in ('hc', 'sa', 'ga'):
        for lo, hi in zip(levels, levels[1:]):
            a = {r['seed']: r for r in allruns if r['algorithm'] == method and r['budget'] == lo and analyze.ok(r)}
            b = {r['seed']: r for r in allruns if r['algorithm'] == method and r['budget'] == hi and analyze.ok(r)}
            seeds = sorted(set(a) & set(b))
            test = analyze.wilcoxon([analyze.energy(b[s]) for s in seeds], [analyze.energy(a[s]) for s in seeds])
            steps.append({'algorithm': method, 'from': lo, 'to': hi, 'n': len(seeds),
                          'improved': sum(analyze.objectives(b[s]) < analyze.objectives(a[s]) for s in seeds),
                          'worse': sum(analyze.objectives(b[s]) > analyze.objectives(a[s]) for s in seeds),
                          'mean_lab_hours_change': statistics.fmean(b[s]['metrics']['unnecessary_lab_hours'] -
                                                                    a[s]['metrics']['unnecessary_lab_hours'] for s in seeds),
                          **test})
    for row, adjusted in zip(steps, analyze.holm([s['p_value'] for s in steps])):
        row['p_holm'] = adjusted
        row['significant'] = adjusted < analyze.ALPHA
    write_csv(output / 'budget-summary.csv', rows)
    (output / 'budget-stats.json').write_text(json.dumps({'rows': rows, 'steps': steps, 'failed_runs': len(bad)},
                                                         indent=2), encoding='utf-8')
    (output / 'budget.svg').write_text(budget_svg(rows, levels), encoding='utf-8')
    lines = ['# งบ 50 / 200 / 500 / 1000 evaluations (#8)', '',
             'สร้างโดย `python/studies.py budget` · seed 1001–1010 · weekly · พารามิเตอร์ที่จูนแล้ว · '
             'จุด 500 มาจากการทดลองสุดท้าย', '',
             f'รันที่ล้มเหลว (ไม่ผ่านตัวตรวจหรือโดนตัดเวลา): {len(bad)}', '',
             'คอลัมน์วินาที/รันวัดตอนรันหลาย process พร้อมกันคนละชุด (งบ 500 รัน 18 process, งบอื่น 9 process พร้อมกับการทดลองอื่น) '
             'จึงใช้เทียบเวลาข้ามงบไม่ได้ ใช้ดูขนาดคร่าว ๆ เท่านั้น', '',
             '| วิธี | งบ | คาบที่ยังจัดไม่ได้ (เฉลี่ย) | จัดครบทุกคาบ | Lab ไม่จำเป็น (ชม., เฉลี่ย) | มัธยฐาน | เปลี่ยนห้อง | วินาที/รัน |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {analyze.LONG[r['algorithm']]} | {r['budget']} | {r['mean_unassigned']:.2f} | {r['success_rate']:.0%} | "
                     f"{r['mean_lab_hours']:.1f} | {r['median_lab_hours']:.1f} | {r['mean_room_changes']:.1f} | "
                     f"{r['mean_search_seconds']:.0f} |")
    lines += ['', 'เพิ่มงบแล้วดีขึ้นไหม (จับคู่ seed, Wilcoxon signed-rank บน energy แบบ exact เมื่อไม่มีค่าซ้ำ เพราะ n = 10, ปรับ Holm ทั้ง 9 คู่):', '',
              '| วิธี | งบ | seed ที่ดีขึ้น / แย่ลง | Δ Lab ไม่จำเป็น เฉลี่ย (ชม.) | p (Holm) |', '|---|---|---:|---:|---:|']
    for s in steps:
        lines.append(f"| {analyze.LONG[s['algorithm']]} | {s['from']} → {s['to']} | {s['improved']} / {s['worse']} | "
                     f"{s['mean_lab_hours_change']:+.1f} | {analyze.p_text(s['p_holm'])} |")
    lines += ['', '**สรุป:**', '']
    for method in ('hc', 'sa', 'ga'):
        ms = [s for s in steps if s['algorithm'] == method]
        last_sig = max((s['to'] for s in ms if s['significant']), default=None)
        top = [r for r in rows if r['algorithm'] == method]
        gain = top[-1]['mean_lab_hours'] - next(r for r in top if r['budget'] == 500)['mean_lab_hours']
        sig = [s for s in ms if s['significant']]
        if last_sig is None:
            text = 'ไม่มีขั้นไหนที่ดีขึ้นอย่างมีนัยสำคัญ'
        elif len(sig) == len(ms):
            text = f'ยังดีขึ้นอย่างมีนัยสำคัญทุกขั้นจนถึงงบ {last_sig} (ยังไม่หยุดดีขึ้นในช่วงที่ลอง)'
        else:
            text = f'ดีขึ้นอย่างมีนัยสำคัญจนถึงงบ {last_sig}'
        lines.append(f"- {analyze.LONG[method]}: {text}; จาก 500 → 1000 Lab ไม่จำเป็นเปลี่ยนเฉลี่ย {gain:+.1f} ชม.")
    lines += ['', '![budget](budget.svg)']
    (output / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return rows, steps


def budget_svg(rows, levels):
    import math
    width, height = 980, 440
    body = []
    panels = [('mean_unassigned', 'คาบที่ยังจัดไม่ได้ (เฉลี่ย)'), ('mean_lab_hours', 'Lab ไม่จำเป็น (ชม., เฉลี่ย)')]
    lx = {b: math.log10(b) for b in levels}
    for col, (key, title) in enumerate(panels):
        values = [r[key] for r in rows]
        p = analyze.Panel(70 + col * 480, 70, 360, 290, min(0, min(values)), max(values),
                          min(lx.values()), max(lx.values()))
        body.append(p.frame(title, 'งบ evaluations ต่อรัน (สเกล log)', [(lx[b], str(b)) for b in levels]))
        labels = []
        for method in ('hc', 'sa', 'ga'):
            pts = [(lx[r['budget']], r[key]) for r in rows if r['algorithm'] == method]
            line = ' '.join(f'{p.sx(x):.1f},{p.sy(y):.1f}' for x, y in pts)
            body.append(f'<polyline class="line s-{method}" style="fill:none" points="{line}"/>')
            for (x, y), r in zip(pts, [r for r in rows if r['algorithm'] == method]):
                body.append(f'<circle class="s-{method}" cx="{p.sx(x):.1f}" cy="{p.sy(y):.1f}" r="5" '
                            f'stroke="var(--surface)" stroke-width="2"><title>{analyze.LONG[method]} งบ {r["budget"]}: '
                            f'{y:.2f}</title></circle>')
            labels.append((p.sy(pts[-1][1]), analyze.LABEL[method]))
        body.append(analyze.end_labels(labels, p.x + p.w + 8))
    body.append(analyze.legend([(m, analyze.LONG[m]) for m in ('hc', 'sa', 'ga')], 70, 425))
    return analyze.svg_doc(width, height, 'Budget study', 'ค่าเฉลี่ยของคาบที่ยังจัดไม่ได้และ Lab ไม่จำเป็นตามงบ evaluations',
                           ''.join(body))


# --- #13 Lab scarcity --------------------------------------------------------------
def scarcity_study(final, output, method, workers):
    output = Path(output)
    params = tuned()
    base = [r for r in final_runs(final) if r['algorithm'] == method]
    budget = {r['budget'] for r in base}
    if len(budget) != 1:
        raise ValueError('Final runs for the chosen method must share one budget')
    budget = budget.pop()
    levels = {4: base}
    for labs in (3, 2):
        dataset = ROOT / 'data' / 'variants' / f'fall-cs-labs{labs}.json.gz'
        jobs = batch.build_jobs([method], ['weekly', 'fixed'], SEEDS, budget, SECONDS, params, config_id=f'labs{labs}')
        name = f'Lab scarcity: {labs} Labs, {method} (seeds 1001-1010)'
        levels[labs] = batch.run_jobs(jobs, output / f'labs{labs}', dataset, workers, slim=False, name=name)
        batch.merge(output / f'labs{labs}', name=name)
    rows = []
    for labs in (4, 3, 2):
        for mode in ('weekly', 'fixed'):
            rs = [r for r in levels[labs] if r['room_mode'] == mode]
            good = [r for r in rs if analyze.ok(r)]
            un = [r['metrics']['unassigned_weekly_sessions'] for r in good]
            q = statistics.quantiles(un, n=4, method='inclusive') if len(un) > 1 else un * 3
            rows.append({'labs': labs, 'room_mode': mode, 'algorithm': method, 'runs': len(rs), 'valid_runs': len(good),
                         'mean_unassigned': statistics.fmean(un), 'median_unassigned': statistics.median(un),
                         'q1_unassigned': q[0], 'q3_unassigned': q[2], 'min_unassigned': min(un),
                         'max_unassigned': max(un), 'success_rate': sum(u == 0 for u in un) / len(rs),
                         'mean_lab_hours': statistics.fmean(r['metrics']['unnecessary_lab_hours'] for r in good),
                         'mean_room_changes': statistics.fmean(r['metrics']['room_changes'] for r in good)})
    write_csv(output / 'scarcity-summary.csv', rows)
    (output / 'scarcity.svg').write_text(scarcity_svg(rows, method), encoding='utf-8')
    lines = [f'# Lab ขาดแคลน: 4 / 3 / 2 ห้อง (#13)', '',
             f'สร้างโดย `python/studies.py scarcity` · {analyze.LONG[method]} (วิธีที่ดีที่สุดจากการทดลองสุดท้าย) · '
             f'seed 1001–1010 · งบ {budget} · พารามิเตอร์ที่จูนแล้ว · 4 ห้องมาจากการทดลองสุดท้าย · '
             'ชุดข้อมูล 3/2 ห้องสร้างด้วย `dataset_tools/make_lab_variants.py` (ตัด Lab ที่เล็กที่สุดออก ที่เหลือเหมือนเดิม)', '',
             '| Lab | โหมด | ผ่านตัวตรวจ | คาบที่ยังจัดไม่ได้ เฉลี่ย (ต่ำสุด–สูงสุด) | จัดครบทุกคาบ | Lab ไม่จำเป็น (ชม.) | เปลี่ยนห้อง |',
             '|---:|---|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['labs']} | {r['room_mode']} | {r['valid_runs']}/{r['runs']} | {r['mean_unassigned']:.1f} "
                     f"({r['min_unassigned']}–{r['max_unassigned']}) | {r['success_rate']:.0%} | {r['mean_lab_hours']:,.1f} | "
                     f"{r['mean_room_changes']:.1f} |")

    def first_fail(mode):
        for labs in (4, 3, 2):
            row = next(r for r in rows if r['labs'] == labs and r['room_mode'] == mode)
            if row['success_rate'] < 1:
                return labs, row
        return None, None

    lines += ['', '**สรุป:**', '']
    for mode in ('fixed', 'weekly'):
        labs, row = first_fail(mode)
        if labs is None:
            lines.append(f'- {mode}: จัดครบทุกคาบทุก seed ได้แม้เหลือ Lab 2 ห้อง')
        else:
            lines.append(f"- {mode}: เริ่มจัดไม่ครบตั้งแต่ Lab {labs} ห้อง (จัดครบ {row['success_rate']:.0%} ของ seed, "
                         f"ยังจัดไม่ได้เฉลี่ย {row['mean_unassigned']:.1f} คาบ)")
    lines += ['', '![scarcity](scarcity.svg)']
    (output / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return rows


def scarcity_svg(rows, method):
    width, height = 720, 430
    top = max(r['max_unassigned'] for r in rows)
    p = analyze.Panel(80, 70, 540, 280, 0, top, 4.25, 1.75)  # x runs 4 -> 2 Labs, left to right
    body = [p.frame(f'คาบที่ยังจัดไม่ได้ ({analyze.LONG[method]}, 10 seeds)', 'จำนวนห้อง Lab',
                    [(n, f'{n} ห้อง') for n in (4, 3, 2)])]
    labels = []
    for mode, key in (('weekly', 'hc'), ('fixed', 'sa')):
        pts = [r for r in rows if r['room_mode'] == mode]
        line = ' '.join(f"{p.sx(r['labs']):.1f},{p.sy(r['mean_unassigned']):.1f}" for r in pts)
        body.append(f'<polyline class="line s-{key}" style="fill:none" points="{line}"/>')
        for r in pts:
            x = p.sx(r['labs'])
            body.append(f'<line class="s-{key}" x1="{x:.1f}" x2="{x:.1f}" y1="{p.sy(r["min_unassigned"]):.1f}" '
                        f'y2="{p.sy(r["max_unassigned"]):.1f}" stroke-width="2"/>'
                        f'<circle class="s-{key}" cx="{x:.1f}" cy="{p.sy(r["mean_unassigned"]):.1f}" r="5" '
                        f'stroke="var(--surface)" stroke-width="2"><title>{mode}, {r["labs"]} Labs: mean '
                        f'{r["mean_unassigned"]:.1f}, range {r["min_unassigned"]}–{r["max_unassigned"]}</title></circle>'
                        f'<text x="{x + 9:.1f}" y="{p.sy(r["mean_unassigned"]) - 8:.1f}" font-size="12">'
                        f'{r["mean_unassigned"]:.0f}</text>')
        labels.append((p.sy(pts[-1]['mean_unassigned']), mode))
    body.append(analyze.end_labels(labels, p.x + p.w + 12))
    body.append(analyze.legend([('hc', analyze.MODE_TH['weekly']), ('sa', analyze.MODE_TH['fixed'])], 80, 415))
    body.append('<text class="muted" x="640" y="415" font-size="12" text-anchor="end">จุด = ค่าเฉลี่ย, เส้นตั้ง = ต่ำสุด–สูงสุด</text>')
    return analyze.svg_doc(width, height, 'Lab scarcity', 'คาบที่ยังจัดไม่ได้เมื่อจำนวนห้อง Lab ลดลง แยกตามโหมดห้อง',
                           ''.join(body))


def write_csv(path, rows):
    with Path(path).open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('study', choices=['budget', 'scarcity'])
    parser.add_argument('--final', type=Path, default=ROOT / 'experiments' / 'final' / 'experiment.json.gz')
    parser.add_argument('--method', choices=['hc', 'sa', 'ga'], help='scarcity: method to run (best from #6)')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--workers', type=int)
    args = parser.parse_args()
    if args.study == 'budget':
        budget_study(args.final, args.output or ROOT / 'experiments' / 'budget', args.workers)
    else:
        if not args.method:
            parser.error('--method is required for scarcity')
        scarcity_study(args.final, args.output or ROOT / 'experiments' / 'lab-scarcity', args.method, args.workers)
    print('done')


if __name__ == '__main__':
    main()
