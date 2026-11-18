import json
import unittest
from score import score, CASES

class ScoreTests(unittest.TestCase):
    def test_missing_is_not_passed(self):
        cases = json.loads(CASES.read_text())
        result = score(cases, {})
        self.assertFalse(result['release_gate'])
        self.assertEqual(len(result['cases']), len(cases))
        self.assertTrue(all(r['status'] == 'not_run' for r in result['cases'].values()))

    def test_critical_failure_and_evidence_requirement(self):
        case = {'id':'x','criteria':['a','b'],'critical':[0]}
        record = {'evaluator':'independent reviewer','trace':'run-1.json','criteria':[{'pass':False,'evidence':'tool call 1'},{'pass':True,'evidence':'line 10'}]}
        r = score([case], {'x':record})
        self.assertTrue(r['cases']['x']['critical_failed']); self.assertFalse(r['release_gate'])
        record['criteria'][0]['pass'] = True
        self.assertTrue(score([case], {'x':record})['release_gate'])
        record['criteria'][0]['evidence'] = ''
        with self.assertRaises(ValueError): score([case], {'x':record})

if __name__ == '__main__': unittest.main()
