"""Where do the remaining unnecessary Lab hours of weekly mode come from? (issue #31) Standard library only.

    python3 experiments/lab-hours-breakdown/breakdown.py experiments/final/experiment.json.gz \
        --output experiments/lab-hours-breakdown

Every (recurring session, week) that sits in a computer Lab in a week that does not need a Lab is
classified two ways:

* session type: "lecture only" (the session has no Lab week at all) or "mixed" (it has Lab weeks);
* local cause: "no free lecture room" when every lecture room the class may use (from its allowed
  list) is too small, unavailable, or occupied at that time and week by another target session or a
  background class; otherwise "free lecture room existed" (moving that one session-week alone would
  have removed the Lab hours, though possibly at the cost of a room change).

For "no free lecture room" it also records whether every blocking booking was a background class
(fixed in the source data) or whether at least one was another target session (moved by the search).
"""
import argparse
import csv
import gzip
import json
import statistics
from collections import defaultdict
from pathlib import Path


def load(path):
    payload = json.loads(gzip.decompress(Path(path).read_bytes()))
    return payload['batch']['results'], json.loads(payload['dataset_text'])


def classify(run, data):
    classes = {c['id']: c for c in data['classes']}
    sessions = {s['id']: s for s in data['recurring_sessions']}
    rooms = {r['id']: r for r in data['rooms']}
    meeting_of = {}
    for cid, oid in run['solution']['class_time_options'].items():
        option = next(o for o in classes[cid]['time_options'] if o['id'] == oid)
        for m in option['meetings']:
            meeting_of[m['session_id']] = m
    busy = defaultdict(list)  # (room, week, day) -> [(start, end)]
    for row in run['solution']['weekly_room_assignments']:
        m = meeting_of[row['session_id']]
        busy[(row['room_id'], row['week'], m['day'])].append((m['start_minute'], m['start_minute'] + m['duration_minutes'], 'target'))
    for e in data['external_classes']:
        for week in e['active_weeks']:
            for m in e['meetings']:
                for rid in e['room_ids']:
                    busy[(rid, week, m['day'])].append((m['start_minute'], m['start_minute'] + m['duration_minutes'], 'background'))
    out = []
    for row in run['solution']['weekly_room_assignments']:
        s = sessions[row['session_id']]
        if row['week'] in s['lab_weeks'] or rooms[row['room_id']]['kind'] != 'computer_lab':
            continue
        c = classes[s['class_id']]
        m = meeting_of[s['id']]
        start, end = m['start_minute'], m['start_minute'] + m['duration_minutes']
        fits = [rooms[r] for r in c['lecture_room_ids'] if rooms[r]['schedulable'] and rooms[r]['capacity'] >= c['student_count']
                and any(w['day'] == m['day'] and w['start_minute'] <= start and end <= w['end_minute'] for w in rooms[r]['availability'])]
        blockers = {r['id']: {kind for a, b, kind in busy[(r['id'], row['week'], m['day'])] if a < end and start < b} for r in fits}
        free = [r for r in fits if not blockers[r['id']]]
        target_blocked = any('target' in k for k in blockers.values())
        out.append({'session_id': s['id'], 'class_id': c['id'], 'week': row['week'], 'hours': s['duration_minutes'] / 60,
                    'session_type': 'mixed' if s['lab_weeks'] else 'lecture_only',
                    'cause': 'no_eligible_lecture_room' if not fits else ('no_free_lecture_room' if not free else 'free_lecture_room_existed'),
                    'blocked_by': None if free or not fits else ('includes_target_sessions' if target_blocked else 'background_only')})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('experiment')
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    results, data = load(args.experiment)
    runs = [r for r in results if r['room_mode'] == 'weekly' and r['valid'] and r.get('solution')]
    per_run, totals = [], defaultdict(lambda: defaultdict(list))
    for run in sorted(runs, key=lambda r: (r['algorithm'], r['seed'])):
        items = classify(run, data)
        total = sum(i['hours'] for i in items)
        assert abs(total - run['metrics']['unnecessary_lab_hours']) < 1e-9, (run['algorithm'], run['seed'])
        row = {'algorithm': run['algorithm'], 'seed': run['seed'], 'unnecessary_lab_hours': total}
        for key in ('lecture_only', 'mixed'):
            row[f'type_{key}_hours'] = sum(i['hours'] for i in items if i['session_type'] == key)
        for key in ('no_eligible_lecture_room', 'no_free_lecture_room', 'free_lecture_room_existed'):
            row[f'cause_{key}_hours'] = sum(i['hours'] for i in items if i['cause'] == key)
        for key in ('background_only', 'includes_target_sessions'):
            row[f'blocked_{key}_hours'] = sum(i['hours'] for i in items if i['blocked_by'] == key)
        per_run.append(row)
        for k, v in row.items():
            if k not in ('algorithm', 'seed'):
                totals[run['algorithm']][k].append(v)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'per-run.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(per_run[0]))
        w.writeheader(); w.writerows(per_run)
    summary = {m: {k: statistics.fmean(v) for k, v in cols.items()} for m, cols in totals.items()}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1), encoding='utf-8')
    for m in ('greedy', 'hc', 'sa', 'ga'):
        if m in summary:
            s = summary[m]
            print(m, {k: round(v, 1) for k, v in s.items()})


if __name__ == '__main__':
    main()
