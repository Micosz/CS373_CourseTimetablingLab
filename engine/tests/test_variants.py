import gzip
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dataset_tools'))
sys.path.insert(0, str(ROOT / 'engine'))
import make_course_lab_variants  # noqa: E402
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


class CourseLabVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(gzip.decompress(make_course_lab_variants.SOURCE.read_bytes()))
        cls.course_of = {c['id']: c['course_id'] for c in cls.base['classes']}

    def lab_weeks_by_course(self, data):
        by_course = {}
        for s in data['recurring_sessions']:
            by_course.setdefault(self.course_of[s['class_id']], set()).add(tuple(s['lab_weeks']))
        return by_course

    def test_sessions_of_a_course_share_lab_weeks_and_levels_are_nested(self):
        previous = None
        for level in make_course_lab_variants.LEVELS:
            out = make_course_lab_variants.variant(self.base, level)
            by_course = self.lab_weeks_by_course(out)
            self.assertTrue(all(len(v) == 1 for v in by_course.values()))
            weeks = {c: set(next(iter(v))) for c, v in by_course.items()}
            self.assertEqual({len(w) for w in weeks.values()}, {0, level})
            if previous:
                self.assertTrue(all(previous[c] <= weeks[c] for c in weeks))
            previous = weeks
            self.assertEqual(out['classes'], self.base['classes'])
            self.assertEqual(out['rooms'], self.base['rooms'])
            self.assertEqual(validate(out)['errors'], [])

    def test_committed_variants_match_the_script(self):
        for level in make_course_lab_variants.LEVELS:
            path = make_course_lab_variants.OUT / f'fall-cs-course-labs-w{level:02d}.json.gz'
            self.assertEqual(json.loads(gzip.decompress(path.read_bytes())),
                             make_course_lab_variants.variant(self.base, level))


if __name__ == '__main__':
    unittest.main()
