import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
import batch  # noqa: E402


class BatchRunnerTests(unittest.TestCase):
    def test_parse_seeds(self):
        self.assertEqual(batch.parse_seeds('1-3,7'), [1, 2, 3, 7])
        with self.assertRaises(ValueError):
            batch.parse_seeds('1-3,2')

    def test_resume_refuses_mismatch_and_merges(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'b'
            jobs = batch.build_jobs(['greedy', 'hc'], ['weekly'], [5], 3, 600, {})
            first = batch.run_jobs(jobs, out, workers=1, log=lambda *a: None)
            self.assertEqual([r['algorithm'] for r in first], ['greedy', 'hc'])
            self.assertTrue(all(r['valid'] and r['evaluations'] <= 3 for r in first))
            stamps = {p.name: p.stat().st_mtime_ns for p in (out / 'runs').glob('*.json')}
            messages = []
            again = batch.run_jobs(jobs, out, workers=1, log=lambda *a: messages.append(' '.join(map(str, a))))
            self.assertIn('2 / 2 runs already done', messages[0])
            self.assertEqual(stamps, {p.name: p.stat().st_mtime_ns for p in (out / 'runs').glob('*.json')})
            self.assertEqual([r['metrics'] for r in again], [r['metrics'] for r in first])
            with self.assertRaises(RuntimeError):
                batch.run_jobs(batch.build_jobs(['hc'], ['weekly'], [5], 4, 600, {}), out, workers=1,
                               log=lambda *a: None)
            path = batch.merge(out)
            payload = json.loads(gzip.decompress(path.read_bytes()))
            self.assertEqual(payload['format'], 'timetable-lab-experiment/v1')
            self.assertEqual(len(payload['batch']['results']), 2)
            self.assertFalse((out / 'runs').exists())
            # The merged batch is unpacked again, so rerunning the command resumes instead of starting over.
            messages.clear()
            batch.run_jobs(jobs, out, workers=1, log=lambda *a: messages.append(' '.join(map(str, a))))
            self.assertIn('2 / 2 runs already done', messages[0])


if __name__ == '__main__':
    unittest.main()
