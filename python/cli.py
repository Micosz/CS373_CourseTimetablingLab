"""Run the same experiment engine without a browser. No third-party packages."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from runner import prepare, run_one, check_configuration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path(__file__).resolve().parents[1]/'data/fall-cs.json.gz')
    parser.add_argument('--methods', nargs='+', choices=['greedy','hc','sa','ga'], default=['greedy','hc','sa','ga'])
    parser.add_argument('--budget', type=int, default=50)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--room-modes', nargs='+', choices=['weekly','fixed'], default=['weekly'],
                        help='Room policy: weekly (default) lets rooms change by week; fixed books one room all term. '
                             'Give both to compare them on the same seeds.')
    parser.add_argument('--name', default='Native Fall CS experiment')
    parser.add_argument('--parameters', type=Path, help='Optional JSON with hc, sa, ga parameter objects')
    parser.add_argument('--output', type=Path, default=Path('results'))
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100 or not 0 <= args.seed <= args.seed+args.repeats-1 <= 2**32-1:
        parser.error('Invalid repeats or seed range')
    text = gzip.decompress(args.dataset.read_bytes()).decode() if args.dataset.suffix=='.gz' else args.dataset.read_text()
    room_modes = list(dict.fromkeys(args.room_modes))
    config = {'budget':args.budget,'seconds':args.seconds,'methods':args.methods,'room_modes':room_modes,
              'seeds':list(range(args.seed,args.seed+args.repeats)),
              'parameters':json.loads(args.parameters.read_text()) if args.parameters else {}}
    check_configuration(config)
    problem, meta = prepare(text)
    now = lambda: datetime.now(timezone.utc).isoformat()
    code = {name:(Path(__file__).parent/name).read_text() for name in
            ['input_validation.py','solution_validator.py','lab_core.py','algorithms.py','runner.py']}
    batch = {'id':str(uuid.uuid4()),'name':args.name,'created_at':now(),'status':'running',
             'dataset_hash':meta['dataset_sha256'],'dataset_id':problem.data['dataset_id'],
             'dataset_label':args.dataset.name,'config':config,'preparation':meta,'code_snapshot':code,
             'engine_sha256':hashlib.sha256(json.dumps(code,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),
             'run_order':[{'algorithm':method,'room_mode':mode,'seed':seed} for mode in room_modes
                          for seed in config['seeds'] for method in args.methods], 'results':[]}
    args.output.mkdir(parents=True,exist_ok=True)
    target = args.output/f"experiment-{batch['id']}.json"
    def save():
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'format':'timetable-lab-experiment/v1','exported_at':now(),
                                         'batch':batch,'dataset_text':text},ensure_ascii=False,indent=2))
        temporary.replace(target)
    save()
    try:
        for job in batch['run_order']:
            result=run_one(problem,{**config,'room_mode':job['room_mode']},job['algorithm'],job['seed'],meta)
            result['run_index']=len(batch['results'])
            batch['results'].append(result)
            save()
            print(job['room_mode'],job['algorithm'],job['seed'],result['status'],result['metrics'],flush=True)
        batch['status']='completed'
    except KeyboardInterrupt:
        batch['status']='cancelled'
    finally:
        batch['finished_at']=now()
        save()
    fields=['room_mode','algorithm','seed','status','valid','evaluations','search_seconds','unassigned_weekly_sessions',
            'unnecessary_lab_hours','room_changes','hard_violations','dataset_sha256','code_sha256']
    with target.with_suffix('.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        for result in batch['results']:
            row={field:result.get(field) for field in fields}
            row.update({field:result['metrics'].get(field) for field in fields if field in (result['metrics'] or {})})
            row['room_mode']=result.get('room_mode','weekly')
            row['hard_violations']=result['validation']['violation_count']
            writer.writerow(row)
    print('Saved',target)


if __name__=='__main__':
    main()
