"""Contract and regression tests; fixtures are code tests, not experiment datasets."""
import copy
import gzip
import json
import random
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from lab_core import Problem
from runner import prepare, run_one, check_configuration
from solution_validator import audit_solution
from algorithms import ordered_crossover
from compare_modes import summarize


def fixture():
    rooms=[{'id':rid,'capacity':30,'kind':kind,'schedulable':True,
            'availability':[{'day':0,'start_minute':480,'end_minute':1080}]} for rid,kind in
           [('R1','lecture'),('R2','lecture'),('L','computer_lab')]]
    classes=[]; sessions=[]
    for i in range(4):
        cid=f'C{i}';sid=f'S{i}'
        classes.append({'id':cid,'course_id':cid,'student_count':20,'instructor_ids':[f'T{i}'],
                        'student_group_ids':[f'G{i}'],'lecture_room_ids':['R1','R2'],'lab_room_ids':['L'],
                        'time_options':[{'id':f'O{i}','meetings':[{'session_id':sid,'day':0,'start_minute':540+60*i,'duration_minutes':60}]}]})
        sessions.append({'id':sid,'class_id':cid,'duration_minutes':60,'active_weeks':[1,2],'lab_weeks':[2]})
    return {'dataset_id':'test','rooms':rooms,'classes':classes,'recurring_sessions':sessions,'external_classes':[],
            'constraints':{'external_student_overlap_is_hard':False,'non_overlap_groups':[],'same_time_of_day_groups':[]}}


def schedule(data):
    return {'dataset_id':data['dataset_id'],'class_time_options':{c['id']:c['time_options'][0]['id'] for c in data['classes']},
            'weekly_room_assignments':[{'session_id':s['id'],'week':w,'room_id':'L' if w in s['lab_weeks'] else 'R1'} for s in data['recurring_sessions'] for w in s['active_weeks']]}


class IndependentValidatorTests(unittest.TestCase):
    def setUp(self):self.data=fixture();self.solution=schedule(self.data)
    def codes(self):return {v['code'] for v in audit_solution(self.data,self.solution)['violations']}
    def test_valid_and_missing_week(self):
        report=audit_solution(self.data,self.solution)
        self.assertTrue(report['valid']);self.assertEqual(report['metrics']['room_changes'],4)
        self.solution['weekly_room_assignments'].pop()
        report=audit_solution(self.data,self.solution)
        self.assertTrue(report['valid']);self.assertEqual(report['metrics']['unassigned_weekly_sessions'],1)
        self.assertEqual(report['metrics']['room_changes'],3)
    def test_room_type_capacity_availability_duplicate(self):
        self.solution['weekly_room_assignments'][1]['room_id']='R1'
        self.data['rooms'][0]['capacity']=1
        self.data['rooms'][0]['availability']=[]
        self.solution['weekly_room_assignments'].append(dict(self.solution['weekly_room_assignments'][0]))
        self.assertTrue({'LAB_REQUIRED','ROOM_DOMAIN','CAPACITY','ROOM_UNAVAILABLE','DUPLICATE_SESSION_WEEK'}<=self.codes())
    def test_room_teacher_student_overlap(self):
        self.data['classes'][1]['time_options'][0]['meetings'][0]['start_minute']=540
        self.data['classes'][1]['instructor_ids']=['T0'];self.data['classes'][1]['student_group_ids']=['G0']
        self.assertTrue({'ROOM_OVERLAP','INSTRUCTOR_OVERLAP','STUDENT_GROUP_OVERLAP'}<=self.codes())
    def test_reused_source_id_does_not_merge_distinct_groups(self):
        self.data['classes'][2]['time_options'][0]['meetings'][0]['start_minute']=540
        self.solution['weekly_room_assignments']=[r for r in self.solution['weekly_room_assignments'] if r['week']==1]
        for row in self.solution['weekly_room_assignments']:
            if row['session_id']=='S2':row['room_id']='R2'
        self.data['constraints']['non_overlap_groups']=[{'source_constraint_id':'90','class_ids':['C0','C1']},{'source_constraint_id':'90','class_ids':['C2','C3']}]
        self.assertTrue(audit_solution(self.data,self.solution)['valid'])
        self.data['classes'][1]['time_options'][0]['meetings'][0]['start_minute']=540
        self.assertIn('DISTRIBUTION_OVERLAP',self.codes())
    def test_external_constraints_and_half_open_intervals(self):
        self.data['external_classes']=[{'id':'E','active_weeks':[1],'room_ids':['R1'],'instructor_ids':[],
                                       'student_group_ids':[], 'meetings':[{'day':0,'start_minute':480,'duration_minutes':60}]}]
        self.assertTrue(audit_solution(self.data,self.solution)['valid'])
        self.data['external_classes'][0]['meetings'][0]['start_minute']=485
        self.assertIn('ROOM_OVERLAP',self.codes())
    def test_same_time_containment_ignores_day(self):
        self.data['constraints']['same_time_of_day_groups']=[{'source_constraint_id':'same-1','class_ids':['C0','C1']}]
        self.assertIn('SAME_TIME',self.codes())


def one_class_fixture():
    """Known answer: one 60-minute session, weeks 1-4, Lab only in week 2.

    weekly: R1, L, R1, R1 -> 0 unnecessary Lab minutes, 2 room changes.
    fixed:  L, L, L, L    -> 3 x 60 = 180 unnecessary Lab minutes, 0 changes.
    """
    data=fixture()
    data['classes']=data['classes'][:1];data['recurring_sessions']=data['recurring_sessions'][:1]
    data['recurring_sessions'][0].update({'active_weeks':[1,2,3,4],'lab_weeks':[2]})
    return data


class FixedRoomModeTests(unittest.TestCase):
    def test_known_answer_fixed_room_holds_lab_longer(self):
        data=one_class_fixture();problem=Problem(data);genome=problem.initial_genome()
        weekly=problem.decode(genome,room_mode='weekly');fixed=problem.decode(genome,room_mode='fixed')
        self.assertEqual(weekly.objectives,(0,0,2));self.assertEqual(fixed.objectives,(0,180,0))
        self.assertEqual([r['room_id'] for r in fixed.solution['weekly_room_assignments']],['L']*4)
        for mode,candidate in [('weekly',weekly),('fixed',fixed)]:
            report=audit_solution(data,candidate.solution,mode)
            self.assertTrue(report['valid'],report['violations'])
            self.assertEqual((report['metrics']['unassigned_weekly_sessions'],report['metrics']['unnecessary_lab_minutes'],
                              report['metrics']['room_changes']),candidate.objectives)
        self.assertGreater(fixed.objectives[1],weekly.objectives[1])
    def test_fixed_mode_leaves_weeks_unassigned_instead_of_moving_room(self):
        data=one_class_fixture()
        data['external_classes']=[{'id':'E','active_weeks':[3],'room_ids':['L'],'instructor_ids':[],'student_group_ids':[],
                                   'meetings':[{'day':0,'start_minute':540,'duration_minutes':60}]}]
        problem=Problem(data);fixed=problem.decode(problem.initial_genome(),room_mode='fixed')
        self.assertEqual(fixed.objectives,(1,120,0))
        self.assertTrue(audit_solution(data,fixed.solution,'fixed')['valid'])
    def test_validator_rejects_room_changes_and_non_lab_in_fixed_mode(self):
        data=fixture();weekly=schedule(data)
        self.assertTrue(audit_solution(data,weekly,'weekly')['valid'])
        codes={v['code'] for v in audit_solution(data,weekly,'fixed')['violations']}
        self.assertIn('FIXED_ROOM_CHANGED',codes)
        lecture_only={**weekly,'weekly_room_assignments':[r for r in weekly['weekly_room_assignments'] if r['week']==1]}
        codes={v['code'] for v in audit_solution(data,lecture_only,'fixed')['violations']}
        self.assertEqual(codes,{'FIXED_ROOM_NOT_LAB'})
    def test_paired_summary_reports_fixed_minus_weekly(self):
        m=lambda u,lab,c:{'unassigned_weekly_sessions':u,'unnecessary_lab_minutes':lab,'unnecessary_lab_hours':lab/60,'room_changes':c}
        batch={'results':[{'algorithm':'greedy','seed':1,'room_mode':'weekly','valid':True,'metrics':m(0,0,2)},
                          {'algorithm':'greedy','seed':1,'room_mode':'fixed','valid':True,'metrics':m(1,180,0)},
                          {'algorithm':'greedy','seed':2,'room_mode':'fixed','valid':False,'metrics':None}]}
        text=summarize(batch)
        self.assertIn('| greedy | fixed | 1 / 2 | 1.0 (1.0) | 3.0 (3.0) | 0.0 (0.0) |',text)
        self.assertIn('| greedy | 1 | 1.0 | 3.0 | -2.0 | 1 / 1 |',text)
    def test_validator_rejects_mode_mismatch_and_unknown_mode(self):
        data=one_class_fixture();problem=Problem(data)
        fixed=problem.decode(problem.initial_genome(),room_mode='fixed').solution
        self.assertIn('ROOM_MODE',{v['code'] for v in audit_solution(data,fixed,'weekly')['violations']})
        self.assertFalse(audit_solution(data,schedule(data),'monthly')['valid'])
        with self.assertRaises(ValueError):problem.decode(problem.initial_genome(),room_mode='monthly')
        with self.assertRaises(ValueError):check_configuration({'room_mode':'monthly'})


class RealDatasetEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=gzip.decompress((ROOT/'data/fall-cs.json.gz').read_bytes()).decode()
        cls.problem,cls.meta=prepare(cls.text)
        cls.config={'budget':8,'seconds':60,'parameters':{'ga':{'population_size':4}}}
    def test_all_methods_independent_audit_budget_and_trace(self):
        for method in ['greedy','hc','sa','ga']:
            with self.subTest(method=method):
                r=run_one(self.problem,self.config,method,42,self.meta)
                self.assertTrue(r['valid'],r['validation']['violations'][:2])
                self.assertEqual(r['validation']['violation_count'],0)
                self.assertEqual(r['evaluations'],1 if method=='greedy' else 8)
                objectives=[tuple(p['objectives']) for p in r['trace']]
                self.assertTrue(all(b<=a for a,b in zip(objectives,objectives[1:])))
                self.assertEqual(r['dataset_sha256'],self.meta['dataset_sha256'])
    def test_fixed_mode_all_methods_pass_audit_and_hold_more_lab(self):
        weekly=run_one(self.problem,self.config,'greedy',42,self.meta)
        self.assertEqual(weekly['room_mode'],'weekly')
        for method in ['greedy','hc','sa','ga']:
            with self.subTest(method=method):
                r=run_one(self.problem,{**self.config,'room_mode':'fixed'},method,42,self.meta)
                self.assertTrue(r['valid'],r['validation']['violations'][:2])
                self.assertEqual(r['room_mode'],'fixed');self.assertEqual(r['metrics']['room_changes'],0)
                rooms={}
                for row in r['solution']['weekly_room_assignments']:
                    rooms.setdefault(row['session_id'],set()).add(row['room_id'])
                self.assertTrue(all(len(v)==1 for v in rooms.values()))
                self.assertGreater(r['metrics']['unnecessary_lab_minutes'],weekly['metrics']['unnecessary_lab_minutes'])
    def test_seeded_reproduction(self):
        for method in ['hc','sa','ga']:
            a=run_one(self.problem,self.config,method,17,self.meta)
            b=run_one(self.problem,self.config,method,17,self.meta)
            self.assertEqual(a['solution'],b['solution']);self.assertEqual(a['metrics'],b['metrics'])
    def test_custom_budget_error_and_invalid_output(self):
        source='def solve(problem, context, parameters):\n    while True: context.evaluate(problem.random_genome(context.rng))'
        good=run_one(self.problem,self.config,'custom',42,self.meta,source)
        self.assertTrue(good['valid']);self.assertEqual(good['evaluations'],8)
        bad=run_one(self.problem,self.config,'custom',42,self.meta,'def solve(problem, context, parameters):\n    return {}')
        self.assertFalse(bad['valid']);self.assertEqual(bad['status'],'invalid_solution')
        error=run_one(self.problem,self.config,'custom',42,self.meta,'raise RuntimeError("expected test")')
        self.assertEqual(error['status'],'error');self.assertFalse(error['valid'])
    def test_scalar_preserves_lexicographic_order(self):
        p=self.problem
        self.assertGreater(p.minute_weight,p.max_changes)
        self.assertGreater(p.unassigned_weight,p.max_lab_minutes*p.minute_weight+p.max_changes)
    def test_configuration_rejects_unfair_or_invalid_budgets(self):
        for config in [{'budget':0},{'seconds':0},{'parameters':{'ga':{'population_size':4,'elites':4}}}]:
            with self.assertRaises(ValueError):check_configuration(config)
    def test_crossover_always_preserves_permutation(self):
        a=tuple(range(20));b=tuple(reversed(a))
        for seed in range(100):self.assertEqual(set(ordered_crossover(a,b,random.Random(seed))),set(a))


if __name__=='__main__':unittest.main()
