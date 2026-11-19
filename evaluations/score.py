#!/usr/bin/env python3
"""Score independent, evidence-backed evaluation annotations; never a model self-score."""
import argparse
import json
from pathlib import Path

CASES = Path(__file__).with_name('cases.json')


def score(cases, results):
    ids = {c['id'] for c in cases}
    if len(ids) != len(cases) or not isinstance(results, dict) or set(results) - ids:
        raise ValueError('Duplicate cases or unknown result IDs')
    report = {}
    for case in cases:
        cid = case['id']; n = len(case['criteria'])
        if not n or any(i < 0 or i >= n for i in case['critical']):
            raise ValueError(f'Invalid case: {cid}')
        if cid not in results:
            report[cid] = {'status': 'not_run'}; continue
        row = results[cid]
        if not isinstance(row.get('evaluator'), str) or not row['evaluator'].strip() or not isinstance(row.get('trace'), str) or not row['trace'].strip():
            raise ValueError(f'{cid}: independent evaluator and trace required')
        grades = row.get('criteria', [])
        if len(grades) != n:
            raise ValueError(f'{cid}: grade every criterion')
        for grade in grades:
            if type(grade.get('pass')) is not bool or not isinstance(grade.get('evidence'), str) or not grade['evidence'].strip():
                raise ValueError(f'{cid}: boolean pass and evidence required')
        count = sum(g['pass'] for g in grades)
        report[cid] = {'status': 'passed' if count == n else 'failed', 'passed': count, 'total': n, 'critical_failed': any(not grades[i]['pass'] for i in case['critical'])}
    return {'cases': report, 'release_gate': all(r['status'] == 'passed' for r in report.values())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('results', type=Path); args = parser.parse_args()
    result = score(json.loads(CASES.read_text()), json.loads(args.results.read_text()))
    print(json.dumps(result, ensure_ascii=False, indent=2)); raise SystemExit(0 if result['release_gate'] else 1)
