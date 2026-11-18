"""Room-change vs unnecessary-Lab trade-off study. Standard library only.

    python experiments/room-change-tradeoff/run.py --workers 4

Weekly mode, test-seed subset 1001-1010, budget 500, tuned parameters (docs/protocol.md).
Each penalty level counts one room change as that many minutes of unnecessary Lab use
(engine/lab_core.py, ``change_penalty``); 0 is the original lexicographic order and
1,000,000 puts room changes before Lab minutes. Resumes from stored runs.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
import batch  # noqa: E402

PENALTIES = [0, 30, 60, 90, 120, 300, 1000000]
SEEDS = list(range(1001, 1011))
BUDGET, SECONDS = 500, 3600
NAME = 'Room-change penalty study (weekly, seeds 1001-1010, budget 500)'


def jobs(penalties, methods):
    data = json.loads((ROOT / 'experiments/tuning/selected-parameters.json').read_text(encoding='utf-8'))
    params = {k: v for k, v in data.items() if not k.startswith('_')}
    out = []
    for penalty in penalties:
        out += batch.build_jobs(methods, ['weekly'], SEEDS, BUDGET, SECONDS, params, config_id=f'p{penalty}',
                                change_penalty_minutes=penalty)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--penalties', type=int, nargs='+', default=PENALTIES)
    parser.add_argument('--methods', nargs='+', default=['greedy', 'hc', 'sa', 'ga'])
    parser.add_argument('--no-merge', action='store_true', help='leave per-run files in runs/ (to continue later)')
    args = parser.parse_args()
    batch.run_jobs(jobs(args.penalties, args.methods), HERE, workers=args.workers, slim=True, name=NAME)
    if not args.no_merge:
        print('Saved', batch.merge(HERE, name=NAME))


if __name__ == '__main__':
    main()
