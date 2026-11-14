"""Build the final experiment with SA replaced by the retuned SA runs (issue #32), for engine/analyze.py.

    python3 experiments/sa-extended-tuning/combine.py /tmp/combined.json.gz
    python3 engine/analyze.py /tmp/combined.json.gz --output experiments/sa-extended-tuning/analysis
"""
import gzip, json, sys
from pathlib import Path

here = Path(__file__).resolve().parent
final = json.loads(gzip.decompress((here.parent / 'final' / 'experiment.json.gz').read_bytes()))
sa = json.loads(gzip.decompress((here / 'test-seeds-sa' / 'experiment.json.gz').read_bytes()))
assert json.loads(final['dataset_text'])['dataset_id'] == json.loads(sa['dataset_text'])['dataset_id']
batch = final['batch']
kept = [r for r in batch['results'] if r['algorithm'] != 'sa']
new = [dict(r, config_id='main') if 'config_id' in r else r for r in sa['batch']['results']]
batch['results'] = kept + new
batch['name'] = 'Final experiment with SA retuned to 0.01 / 0.8 (issue #32)'
Path(sys.argv[1]).write_bytes(gzip.compress(json.dumps(final).encode()))
print(len(kept), 'kept +', len(new), 'SA runs')
