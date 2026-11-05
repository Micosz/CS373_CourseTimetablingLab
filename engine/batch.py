"""Parallel, resumable experiment runner on the same engine as cli.py. Standard library only.

Every run is written to its own JSON file under ``<output>/runs`` as soon as it
finishes, so an interrupted batch continues with the same command: finished
runs are skipped after checking that they were produced by the same dataset,
engine code and configuration. ``merge`` then writes one web-importable
experiment JSON (gzipped) and a CSV.

Example (final experiment, see docs/protocol.md):
    python engine/batch.py run --methods greedy hc sa ga --room-modes weekly fixed \
        --seeds 1001-1030 --budget 500 --seconds 3600 \
        --parameters experiments/tuning/selected-parameters.json \
        --output experiments/final --workers 18
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_DATASET = ROOT / 'data' / 'fall-cs.json.gz'
ENGINE_FILES = ['input_validation.py', 'solution_validator.py', 'lab_core.py', 'algorithms.py', 'runner.py']
CSV_FIELDS = ['config_id', 'room_mode', 'algorithm', 'seed', 'status', 'valid', 'evaluations', 'budget',
              'search_seconds', 'unassigned_weekly_sessions', 'unnecessary_lab_hours', 'room_changes',
              'hard_violations', 'dataset_sha256', 'engine_sha256']


def now():
    return datetime.now(timezone.utc).isoformat()


def read_dataset_text(path):
    path = Path(path)
    raw = path.read_bytes()
    return gzip.decompress(raw).decode() if path.suffix == '.gz' else raw.decode()


def engine_snapshot():
    code = {name: (HERE / name).read_text(encoding='utf-8') for name in ENGINE_FILES}
    digest = hashlib.sha256(json.dumps(code, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    return code, digest


def parse_seeds(spec):
    seeds = []
    for part in str(spec).split(','):
        part = part.strip()
        if '-' in part:
            lo, hi = (int(x) for x in part.split('-', 1))
            seeds.extend(range(lo, hi + 1))
        elif part:
            seeds.append(int(part))
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError('Seed list is empty or has duplicates: ' + str(spec))
    return seeds


def job_key(job):
    return f"{job['config_id']}__{job['room_mode']}__{job['algorithm']}__{job['seed']}"


def job_fingerprint(job, dataset_sha, engine_sha):
    """Everything that determines a run's result; a stored run is reused only if this matches."""
    keep = {k: job[k] for k in ('config_id', 'room_mode', 'algorithm', 'seed', 'budget', 'seconds')}
    keep['parameters'] = job['parameters'].get(job['algorithm'], {})
    keep['dataset_sha256'] = dataset_sha
    keep['engine_sha256'] = engine_sha
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()


# --- worker side -----------------------------------------------------------
_PROBLEMS = {}


def _problem(dataset_path):
    if dataset_path not in _PROBLEMS:
        sys.path.insert(0, str(HERE))
        from runner import prepare
        _PROBLEMS[dataset_path] = prepare(read_dataset_text(dataset_path))
    return _PROBLEMS[dataset_path]


def _slim(result):
    """Drop the full schedule and violation list (tuning runs); metrics and trace stay."""
    result = dict(result)
    result['solution'] = None
    validation = dict(result.get('validation') or {})
    validation.pop('violations', None)
    result['validation'] = validation
    return result


def execute(job, dataset_path, target, fingerprint, slim):
    sys.path.insert(0, str(HERE))
    from runner import run_one
    problem, meta = _problem(dataset_path)
    config = {'budget': job['budget'], 'seconds': job['seconds'], 'room_mode': job['room_mode'],
              'parameters': job['parameters']}
    started = now()
    result = run_one(problem, config, job['algorithm'], job['seed'], meta)
    result.update({'config_id': job['config_id'], 'fingerprint': fingerprint, 'started_at': started,
                   'finished_at': now(), 'worker_pid': os.getpid()})
    if slim:
        result = _slim(result)
    target = Path(target)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    temporary.replace(target)
    m = result['metrics'] or {}
    return (job_key(job), result['status'], result['valid'], m.get('unassigned_weekly_sessions'),
            m.get('unnecessary_lab_hours'), m.get('room_changes'), round(result['search_seconds'], 1))


# --- driver side -----------------------------------------------------------
def run_jobs(jobs, output, dataset=DEFAULT_DATASET, workers=None, slim=False, name='batch', log=print):
    """Run ``jobs`` (dicts with config_id, algorithm, room_mode, seed, budget, seconds, parameters).

    Returns the list of stored result dicts in job order. Raises if a stored run
    belongs to a different configuration, dataset or engine.
    """
    sys.path.insert(0, str(HERE))
    from runner import check_configuration
    output = Path(output)
    runs_dir = output / 'runs'
    runs_dir.mkdir(parents=True, exist_ok=True)
    merged = output / 'experiment.json.gz'
    if merged.exists() and not any(runs_dir.glob('*.json')):
        # A finished, merged batch: unpack it so the same command resumes instead of starting over.
        for r in json.loads(gzip.decompress(merged.read_bytes()))['batch']['results']:
            r.pop('run_index', None)
            (runs_dir / (job_key({**r, 'config_id': r.get('config_id', 'main')}) + '.json')).write_text(
                json.dumps(r, ensure_ascii=False), encoding='utf-8')
    dataset = str(Path(dataset).resolve())
    text = read_dataset_text(dataset)
    dataset_sha = hashlib.sha256(text.encode()).hexdigest()
    _, engine_sha = engine_snapshot()
    keys = [job_key(j) for j in jobs]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate jobs in batch')
    pending = []
    for job in jobs:
        check_configuration({'budget': job['budget'], 'seconds': job['seconds'], 'room_mode': job['room_mode'],
                             'parameters': job['parameters']})
        fingerprint = job_fingerprint(job, dataset_sha, engine_sha)
        target = runs_dir / (job_key(job) + '.json')
        if target.exists():
            stored = json.loads(target.read_text(encoding='utf-8'))
            if stored.get('fingerprint') != fingerprint:
                raise RuntimeError(f'{target} was produced by a different configuration, dataset or engine; '
                                   'use a new --output directory or delete it deliberately')
            continue
        pending.append((job, str(target), fingerprint))
    manifest_path = output / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {
        'name': name, 'created_at': now(), 'sessions': []}
    log(f'{len(jobs) - len(pending)} / {len(jobs)} runs already done; running {len(pending)} '
        f'with {workers or os.cpu_count()} workers')
    session = {'started_at': now(), 'runs': len(pending), 'workers': workers or os.cpu_count()}
    wall = time.perf_counter()
    failures = []
    if pending:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(execute, job, dataset, target, fp, slim) for job, target, fp in pending]
            done = 0
            for future in as_completed(futures):
                try:
                    row = future.result()
                except Exception as exc:  # keep the other runs going; the failed one is retried next time
                    failures.append(repr(exc))
                    log('FAILED', repr(exc))
                    continue
                done += 1
                log(f'[{done}/{len(pending)}]', *row)
    session.update({'finished_at': now(), 'wall_seconds': time.perf_counter() - wall, 'failures': failures})
    manifest.update({'dataset': os.path.relpath(dataset, ROOT).replace(os.sep, '/'), 'dataset_sha256': dataset_sha,
                     'engine_sha256': engine_sha, 'python': sys.version.split()[0], 'platform': sys.platform,
                     'cpu_count': os.cpu_count(), 'total_runs': len(jobs)})
    if pending:
        manifest['sessions'].append(session)
    manifest['wall_seconds_total'] = sum(s['wall_seconds'] for s in manifest['sessions'])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    if failures:
        raise RuntimeError(f'{len(failures)} runs failed; rerun the same command to retry them')
    return [json.loads((runs_dir / (k + '.json')).read_text(encoding='utf-8')) for k in keys]


def load_runs(output):
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((Path(output) / 'runs').glob('*.json'))]


def merge(output, dataset=DEFAULT_DATASET, name=None, keep_runs=False):
    """Write experiment.json.gz (web-importable after gunzip) and experiment.csv from stored runs."""
    output = Path(output)
    results = load_runs(output)
    if not results:
        raise ValueError('No runs found in ' + str(output / 'runs'))
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    text = read_dataset_text(ROOT / manifest['dataset'])
    code, engine_sha = engine_snapshot()
    if engine_sha != manifest['engine_sha256'] or any(r.get('engine_version') is None for r in results):
        raise RuntimeError('Engine code changed since these runs were made; merge with the original code')
    order = {'greedy': 0, 'hc': 1, 'sa': 2, 'ga': 3}
    results.sort(key=lambda r: (r.get('config_id', ''), r['room_mode'], r['seed'], order.get(r['algorithm'], 9)))
    for i, r in enumerate(results):
        r['run_index'] = i
    modes = list(dict.fromkeys(r['room_mode'] for r in results))
    first = results[0]
    sys.path.insert(0, str(HERE))
    from runner import prepare
    _, meta = prepare(text)
    batch = {'id': str(uuid.uuid5(uuid.NAMESPACE_URL, str(output.resolve()))), 'name': name or manifest.get('name'),
             'created_at': manifest['created_at'], 'finished_at': manifest['sessions'][-1]['finished_at'] if
             manifest['sessions'] else manifest['created_at'], 'status': 'completed',
             'dataset_hash': manifest['dataset_sha256'], 'dataset_id': first['dataset_id'],
             'dataset_label': Path(manifest['dataset']).name,
             'config': {'budget': first['budget'], 'seconds': first['time_limit_seconds'],
                        'methods': list(dict.fromkeys(r['algorithm'] for r in results)), 'room_modes': modes,
                        'room_mode': modes[0] if len(modes) == 1 else None,
                        'seeds': sorted({r['seed'] for r in results}),
                        'parameters': {r['algorithm']: r['parameters'] for r in results if r['parameters']}},
             'preparation': meta, 'code_snapshot': code, 'engine_sha256': engine_sha,
             'run_order': [{'algorithm': r['algorithm'], 'room_mode': r['room_mode'], 'seed': r['seed']}
                           for r in results], 'results': results}
    payload = {'format': 'timetable-lab-experiment/v1', 'exported_at': now(), 'batch': batch, 'dataset_text': text}
    blob = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    # mtime=0 keeps the gzip bytes reproducible for the same content.
    (output / 'experiment.json.gz').write_bytes(gzip.compress(blob, mtime=0))
    with (output / 'experiment.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in results:
            m = r['metrics'] or {}
            writer.writerow({'config_id': r.get('config_id'), 'room_mode': r['room_mode'], 'algorithm': r['algorithm'],
                             'seed': r['seed'], 'status': r['status'], 'valid': r['valid'],
                             'evaluations': r['evaluations'], 'budget': r['budget'],
                             'search_seconds': round(r['search_seconds'], 3),
                             'unassigned_weekly_sessions': m.get('unassigned_weekly_sessions'),
                             'unnecessary_lab_hours': m.get('unnecessary_lab_hours'),
                             'room_changes': m.get('room_changes'),
                             'hard_violations': (r.get('validation') or {}).get('violation_count'),
                             'dataset_sha256': r['dataset_sha256'], 'engine_sha256': engine_sha})
    if not keep_runs:
        for p in (output / 'runs').glob('*.json'):
            p.unlink()
        (output / 'runs').rmdir()
    return output / 'experiment.json.gz'


def build_jobs(methods, room_modes, seeds, budget, seconds, parameters, config_id='main'):
    return [{'config_id': config_id, 'algorithm': method, 'room_mode': mode, 'seed': seed, 'budget': budget,
             'seconds': seconds, 'parameters': parameters}
            for mode in room_modes for seed in seeds for method in methods]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run', help='run (or resume) a batch, then merge it')
    run.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    run.add_argument('--methods', nargs='+', choices=['greedy', 'hc', 'sa', 'ga'], default=['greedy', 'hc', 'sa', 'ga'])
    run.add_argument('--room-modes', nargs='+', choices=['weekly', 'fixed'], default=['weekly'])
    run.add_argument('--seeds', required=True, help='e.g. 1001-1030 or 1,2,5-9')
    run.add_argument('--budget', type=int, required=True)
    run.add_argument('--seconds', type=float, default=3600)
    run.add_argument('--parameters', type=Path, help='JSON with hc, sa, ga parameter objects')
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 2))
    run.add_argument('--name', default='Native batch experiment')
    run.add_argument('--slim', action='store_true', help='do not store full schedules (smaller files)')
    run.add_argument('--keep-runs', action='store_true', help='keep per-run files after merging')
    mg = sub.add_parser('merge', help='merge stored runs without running anything')
    mg.add_argument('--output', type=Path, required=True)
    mg.add_argument('--name')
    mg.add_argument('--keep-runs', action='store_true')
    args = parser.parse_args()
    if args.command == 'merge':
        print('Saved', merge(args.output, name=args.name, keep_runs=args.keep_runs))
        return
    parameters = json.loads(args.parameters.read_text(encoding='utf-8')) if args.parameters else {}
    parameters = parameters.get('parameters', parameters)
    jobs = build_jobs(args.methods, list(dict.fromkeys(args.room_modes)), parse_seeds(args.seeds), args.budget,
                      args.seconds, parameters)
    run_jobs(jobs, args.output, args.dataset, args.workers, args.slim, args.name)
    print('Saved', merge(args.output, args.dataset, args.name, args.keep_runs))


if __name__ == '__main__':
    main()
