import gzip
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dataset_tools'))
sys.path.insert(0, str(ROOT / 'engine'))
import make_lab_variants  # noqa: E402
from input_validation import validate  # noqa: E402


class LabVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(gzip.decompress(make_lab_variants.SOURCE.read_bytes()))

    def test_only_smallest_labs_are_removed(self):
        for keep, removed in ((3, {'SIM-LAB-04'}), (2, {'SIM-LAB-03', 'SIM-LAB-04'})):
            out = make_lab_variants.variant(self.base, keep)
            labs = {r['id'] for r in out['rooms'] if r['kind'] == 'computer_lab'}
            self.assertEqual(len(labs), keep)
            self.assertFalse(labs & removed)
            self.assertEqual(out['recurring_sessions'], self.base['recurring_sessions'])
            self.assertEqual(out['external_classes'], self.base['external_classes'])
            self.assertEqual([r for r in out['rooms'] if r['kind'] != 'computer_lab'],
                             [r for r in self.base['rooms'] if r['kind'] != 'computer_lab'])
            self.assertEqual(validate(out)['errors'], [])

    def test_committed_variants_match_the_script(self):
        for keep in (3, 2):
            committed = json.loads(gzip.decompress((make_lab_variants.OUT / f'fall-cs-labs{keep}.json.gz').read_bytes()))
            self.assertEqual(committed, make_lab_variants.variant(self.base, keep))


if __name__ == '__main__':
    unittest.main()
