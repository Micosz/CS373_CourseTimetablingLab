import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
import analyze  # noqa: E402

WEIGHTS = {'unassigned': 10 ** 9, 'lab_minute': 10 ** 4, 'room_change': 1}


def fake(method, seed, unassigned, lab_minutes, changes, mode='weekly'):
    return {'algorithm': method, 'seed': seed, 'room_mode': mode, 'status': 'evaluation_budget', 'valid': True,
            'evaluations': 10, 'budget': 10, 'search_seconds': 1.0, 'energy_weights': WEIGHTS,
            'metrics': {'unassigned_weekly_sessions': unassigned, 'unnecessary_lab_minutes': lab_minutes,
                        'unnecessary_lab_hours': lab_minutes / 60, 'room_changes': changes},
            'trace': [{'evaluations': 1, 'objectives': [unassigned + 1, lab_minutes, changes]},
                      {'evaluations': 5, 'objectives': [unassigned, lab_minutes, changes]}]}


class StatisticsTests(unittest.TestCase):
    def test_average_ranks_with_ties(self):
        self.assertEqual(analyze.average_ranks([3, 1, 3, 2]), [3.5, 1, 3.5, 2])

    def test_chi_square_tail(self):
        for x in (0.5, 3.0, 9.0):  # df = 2 has the closed form exp(-x/2)
            self.assertAlmostEqual(analyze.chi2_sf(x, 2), math.exp(-x / 2), places=12)
        self.assertAlmostEqual(analyze.chi2_sf(7.814728, 3), 0.05, places=5)
        self.assertAlmostEqual(analyze.chi2_sf(3.841459, 1), 0.05, places=5)

    def test_friedman_by_hand(self):
        # Three blocks that all rank the treatments 1, 2, 3: R = 3, 6, 9 -> chi2 = 12/36 * 126 - 36 = 6.
        result = analyze.friedman([[1, 2, 3]] * 3)
        self.assertAlmostEqual(result['statistic'], 6.0)
        self.assertAlmostEqual(result['p_value'], math.exp(-3))
        self.assertEqual(result['mean_ranks'], [1, 2, 3])
        self.assertEqual(analyze.friedman([[1.5, 1.5]] * 4)['p_value'], 1.0)

    def test_wilcoxon_by_hand(self):
        # d = 1, 2, 3, -4, 5 -> W+ = 11, W- = 4, n = 5, mean 7.5, var 13.75, z = (3.5 - 0.5) / sqrt(13.75).
        result = analyze.wilcoxon([11, 12, 13, 6, 15], [10, 10, 10, 10, 10])
        self.assertEqual((result['n_nonzero'], result['w_plus'], result['w_minus']), (5, 11, 4))
        self.assertAlmostEqual(result['z'], 3 / math.sqrt(13.75))
        # Exact: subsets of {1..5} with sum <= 4 are {}, {1}, {2}, {3}, {1,2}, {4}, {1,3} -> 7 of 32; p = 2 * 7/32.
        self.assertEqual(result['method'], 'exact')
        self.assertAlmostEqual(result['p_value'], 14 / 32)
        # All 10 differences positive: p = 2 / 2^10.
        self.assertAlmostEqual(analyze.wilcoxon(list(range(2, 12)), [0] * 10)['p_value'], 2 / 1024)
        # Tied |d| fall back to the normal approximation: d = 1, 1, 2, -3 -> ranks 1.5, 1.5, 3, 4.
        tied = analyze.wilcoxon([1, 1, 2, -3], [0, 0, 0, 0])
        self.assertEqual((tied['method'], tied['w_plus'], tied['w_minus']), ('normal', 6, 4))
        var = 4 * 5 * 9 / 24 - 6 / 48
        z = (6 - 5 - 0.5) / math.sqrt(var)
        self.assertAlmostEqual(tied['p_value'], math.erfc(z / math.sqrt(2)))
        self.assertEqual(analyze.wilcoxon([1, 2], [1, 2])['p_value'], 1.0)

    def test_holm_by_hand(self):
        adjusted = analyze.holm([0.01, 0.04, 0.03])
        for got, want in zip(adjusted, [0.03, 0.06, 0.06]):
            self.assertAlmostEqual(got, want)

    def test_room_change_bound_by_hand(self):
        data = {'recurring_sessions': [
            {'id': 'a', 'class_id': 'A', 'active_weeks': [1, 2, 3, 4], 'lab_weeks': [2]},    # in and out: 2
            {'id': 'b', 'class_id': 'B', 'active_weeks': [1, 2, 3, 4], 'lab_weeks': [1]},    # only out: 1
            {'id': 'c', 'class_id': 'C', 'active_weeks': [1, 2, 3], 'lab_weeks': []},        # none: 0
            {'id': 'd', 'class_id': 'D', 'active_weeks': [1, 3, 5], 'lab_weeks': [1, 5]}]}   # 2
        total, per_session = analyze.room_change_bound(data)
        self.assertEqual(total, 5)
        self.assertEqual(per_session, {'a': 2, 'b': 1, 'c': 0, 'd': 2})


class ReportTests(unittest.TestCase):
    def test_tables_match_raw_results(self):
        results = []
        for seed in range(1, 7):
            results.append(fake('greedy', seed, 2, 600, 50))
            results.append(fake('hc', seed, 0, 300 + seed * 60, 40 + seed))
            results.append(fake('sa', seed, 0, 240 + seed * 60, 45))
        results.append({**fake('sa', 7, 0, 0, 0), 'valid': False})
        rows = {r['algorithm']: r for r in analyze.summary_rows(results)}
        self.assertEqual(rows['hc']['unnecessary_lab_hours']['mean'], (sum(300 + s * 60 for s in range(1, 7)) / 6) / 60)
        self.assertEqual(rows['hc']['room_changes']['median'], 43.5)
        self.assertEqual(rows['greedy']['success_rate'], 0)
        self.assertEqual(rows['sa']['valid_runs'], 6)
        self.assertEqual(rows['sa']['failed_runs'], 1)
        self.assertAlmostEqual(rows['sa']['success_rate'], 6 / 7)
        tests = analyze.method_tests(results)
        self.assertEqual(tests['seeds'], list(range(1, 7)))  # seed 7 lacks valid runs for every method
        pairs = {(p['a'], p['b']): p for p in tests['pairwise']}
        self.assertEqual(pairs[('greedy', 'hc')]['b_better'], 6)
        self.assertEqual(pairs[('hc', 'sa')]['b_better'], 6)  # SA always 60 lab minutes lower
        self.assertEqual(pairs[('hc', 'sa')]['median_difference_a_minus_b']['unnecessary_lab_hours'], 1.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'experiment.json'
            path.write_text(json.dumps({'batch': {'results': results}}), encoding='utf-8')
            analyze.analyze([path], Path(tmp) / 'out')
            report = (Path(tmp) / 'out' / 'report.md').read_text(encoding='utf-8')
            self.assertIn('| weekly | Hill Climbing | 6/6 | 100% |', report)
            self.assertTrue((Path(tmp) / 'out' / 'convergence.svg').exists())
            stats = json.loads((Path(tmp) / 'out' / 'stats.json').read_text(encoding='utf-8'))
            self.assertEqual(stats['methods']['friedman']['n'], 6)

    def test_duplicate_runs_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.json'
            path.write_text(json.dumps({'batch': {'results': [fake('hc', 1, 0, 0, 0)]}}), encoding='utf-8')
            with self.assertRaises(ValueError):
                analyze.load([path, path])


if __name__ == '__main__':
    unittest.main()
