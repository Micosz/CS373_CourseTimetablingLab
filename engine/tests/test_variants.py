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
import make_lab_week_variants  # noqa: E402
import make_pattern_variants  # noqa: E402
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


def lab_weeks_by_part(data):
    """Lab weeks seen in each (course, subpart): the sections of one part must share them."""
    part_of = {c['id']: (c['course_id'], c['source_subpart_id']) for c in data['classes']}
    by_part = {}
    for s in data['recurring_sessions']:
        by_part.setdefault(part_of[s['class_id']], set()).add(tuple(s['lab_weeks']))
    return by_part


class MainDatasetLabRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(gzip.decompress(make_lab_variants.SOURCE.read_bytes()))
        cls.plan = cls.base['generator']['lab_plan']
        cls.by_part = lab_weeks_by_part(cls.base)

    def test_sections_of_one_part_share_lab_weeks(self):
        self.assertTrue(all(len(v) == 1 for v in self.by_part.values()))

    def test_only_the_practice_part_of_a_lab_course_needs_a_lab(self):
        n = self.base['generator']['config']['lab_weeks_per_lab_course']
        for (course, subpart), seen in self.by_part.items():
            weeks = next(iter(seen))
            order = self.plan['lab_courses'].get(course)
            if order and self.plan['practice_subparts'][course] == subpart:
                self.assertEqual(list(weeks), sorted(order[:n]))
            else:
                self.assertEqual(weeks, ())

    def test_a_single_part_meeting_several_times_a_week_is_a_lecture_course(self):
        parts = {}
        for c in self.base['classes']:
            parts.setdefault(c['course_id'], {})[c['source_subpart_id']] = len(c['session_ids'])
        for course, subparts in parts.items():
            if len(subparts) == 1 and next(iter(subparts.values())) > 1:
                self.assertNotIn(course, self.plan['practice_subparts'])

    def test_lab_hours_stay_close_to_the_target(self):
        hours = sum(s['duration_minutes'] * len(s['lab_weeks']) for s in self.base['recurring_sessions']) / 60
        self.assertAlmostEqual(hours, self.base['generator']['config']['lab_hours_target'], delta=20)


class LabWeekVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(gzip.decompress(make_lab_week_variants.SOURCE.read_bytes()))

    def test_parts_share_lab_weeks_and_levels_are_nested(self):
        previous = None
        for level in make_lab_week_variants.LEVELS:
            out = make_lab_week_variants.variant(self.base, level)
            by_part = lab_weeks_by_part(out)
            self.assertTrue(all(len(v) == 1 for v in by_part.values()))
            weeks = {p: set(next(iter(v))) for p, v in by_part.items()}
            self.assertEqual({len(w) for w in weeks.values()}, {0, level})
            if previous:
                self.assertTrue(all(previous[p] <= weeks[p] for p in weeks))
            previous = weeks
            self.assertEqual(out['classes'], self.base['classes'])
            self.assertEqual(out['rooms'], self.base['rooms'])
            self.assertEqual(validate(out)['errors'], [])

    def test_the_main_level_has_the_lab_weeks_of_the_main_dataset(self):
        n = self.base['generator']['config']['lab_weeks_per_lab_course']
        self.assertEqual(make_lab_week_variants.variant(self.base, n)['recurring_sessions'],
                         self.base['recurring_sessions'])

    def test_committed_variants_match_the_script(self):
        for level in make_lab_week_variants.LEVELS:
            path = make_lab_week_variants.OUT / f'fall-cs-labweeks-w{level:02d}.json.gz'
            self.assertEqual(json.loads(gzip.decompress(path.read_bytes())),
                             make_lab_week_variants.variant(self.base, level))


class PatternVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(gzip.decompress(make_pattern_variants.SOURCE.read_bytes()))

    def test_patterns_keep_the_lab_sessions_and_share_weeks_within_a_part(self):
        for name, step in (('consecutive', 1), ('alternate', 2)):
            out = make_pattern_variants.variant(self.base, name)
            self.assertTrue(all(len(v) == 1 for v in lab_weeks_by_part(out).values()))
            for before, after in zip(self.base['recurring_sessions'], out['recurring_sessions']):
                weeks = after['lab_weeks']
                self.assertEqual(len(before['lab_weeks']), len(weeks))
                self.assertTrue(all(b - a == step for a, b in zip(weeks, weeks[1:])))
            self.assertEqual(validate(out)['errors'], [])

    def test_committed_variants_match_the_script(self):
        for name in make_pattern_variants.PATTERNS:
            path = make_pattern_variants.OUT / f'fall-cs-pattern-{name}.json.gz'
            self.assertEqual(json.loads(gzip.decompress(path.read_bytes())),
                             make_pattern_variants.variant(self.base, name))


if __name__ == '__main__':
    unittest.main()

