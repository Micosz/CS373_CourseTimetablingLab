"""Write input_reports.json: engine/input_validation.py reports for the shipped datasets and broken copies.

    python dotnet/tests/Timetabling.Engine.Tests/Fixtures/make_input_reports.py

A case names a dataset under data/ and a list of edits. Each edit is {"path": [...], "value": ...} to set a
value or {"path": [...], "delete": true} to remove a key; path items are object keys or list indexes.
"""
import copy
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'engine'))
from input_validation import validate  # noqa: E402

DATASETS = ['data/fall-cs.json.gz', 'data/variants/fall-cs-labs2.json.gz', 'data/variants/fall-cs-labs3.json.gz']
MAIN = DATASETS[0]


def apply(data, edits):
    data = copy.deepcopy(data)
    for edit in edits:
        *parents, last = edit['path']
        node = data
        for key in parents:
            node = node[key]
        if edit.get('delete'):
            del node[last]
        else:
            node[last] = edit['value']
    return data


def cases(main):
    def first(collection, test):
        return next(i for i, item in enumerate(main[collection]) if test(item))

    lab_session = first('recurring_sessions', lambda s: len(s['lab_weeks']) >= 2)
    return [
        ('missing_top_level_fields', MAIN, [{'path': ['objectives'], 'delete': True}, {'path': ['calendar'], 'delete': True}]),
        ('schema_and_rooms', MAIN, [
            {'path': ['schema_version'], 'value': '2.0'},
            {'path': ['rooms', 0, 'capacity'], 'value': -1},
            {'path': ['rooms', 1, 'kind'], 'value': 'auditorium'},
            {'path': ['rooms', 2, 'availability', 0, 'end_minute'], 'value': 2000},
        ]),
        ('classes_and_sessions', MAIN, [
            {'path': ['classes', 0, 'instructor_ids'], 'value': []},
            {'path': ['classes', 1, 'student_count'], 'value': 0},
            {'path': ['classes', 2, 'lab_room_ids'], 'value': []},
            {'path': ['classes', 3, 'time_options', 0, 'meetings', 0, 'start_minute'], 'value': 481},
            {'path': ['recurring_sessions', lab_session, 'lab_weeks'],
             'value': list(reversed(main['recurring_sessions'][lab_session]['lab_weeks']))},
            {'path': ['external_classes', 0, 'meetings'], 'value': []},
            {'path': ['objectives', 'ordered_metrics'], 'value': ['room_changes', 'unnecessary_lab_minutes', 'unassigned_weekly_sessions']},
        ]),
        ('duplicate_ids', MAIN, [
            {'path': ['classes', 1, 'id'], 'value': main['classes'][0]['id']},
            {'path': ['calendar', 'week_ids'], 'value': [1, 2, 4]},
        ]),
        ('strict_student_rule', MAIN, [{'path': ['constraints', 'external_student_overlap_is_hard'], 'value': True}]),
    ]


def read(path):
    with gzip.open(ROOT / path, 'rt', encoding='utf-8') as f:
        return json.load(f)


def main():
    out = []
    for path in DATASETS:
        out.append({'name': Path(path).name, 'dataset': path, 'edits': [], 'expected': validate(read(path))})
    for name, path, edits in cases(read(MAIN)):
        out.append({'name': name, 'dataset': path, 'edits': edits, 'expected': validate(apply(read(path), edits))})
    for case in out:
        report = case['expected']
        print(f"{case['name']:28s} {report['status']:22s} errors={len(report['errors'])} warnings={len(report['warnings'])}")
    target = Path(__file__).with_name('input_reports.json')
    target.write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
    print('Saved', target)


if __name__ == '__main__':
    main()
