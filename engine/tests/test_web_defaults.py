"""The web form must open with the tuned parameters from experiments/tuning (README promise)."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELDS = {('hc', 'restart_patience'): 'hc-patience', ('sa', 'initial_acceptance'): 'sa-acceptance',
          ('sa', 'cooling_rate'): 'sa-cooling', ('ga', 'population_size'): 'ga-population',
          ('ga', 'tournament_size'): 'ga-tournament', ('ga', 'elites'): 'ga-elites',
          ('ga', 'crossover_rate'): 'ga-crossover', ('ga', 'mutation_rate'): 'ga-mutation'}


class WebDefaultsTest(unittest.TestCase):
    def test_form_defaults_match_tuned_parameters(self):
        html = (ROOT / 'apps/web/index.html').read_text(encoding='utf-8')
        tuned = json.loads((ROOT / 'experiments/tuning/selected-parameters.json').read_text(encoding='utf-8'))
        for (method, key), element in FIELDS.items():
            match = re.search(rf'id="{element}"[^>]*\bvalue="([^"]+)"', html)
            self.assertIsNotNone(match, element)
            self.assertEqual(float(match.group(1)), float(tuned[method][key]), element)
        self.assertEqual(set(FIELDS), {(m, k) for m in ('hc', 'sa', 'ga') for k in tuned[m]})


if __name__ == '__main__':
    unittest.main()
