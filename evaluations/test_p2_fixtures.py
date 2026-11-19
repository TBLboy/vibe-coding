import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from prepare_p2 import prepare, ROOT

class FixtureTests(unittest.TestCase):
    def test_all_materialized_cases_have_green_baselines(self):
        cases = json.loads((ROOT / 'cases.json').read_text())
        materialized = [c for c in cases if 'fixture' in c]
        self.assertGreaterEqual(len(materialized), 6)
        with tempfile.TemporaryDirectory() as temp:
            for case in materialized:
                with self.subTest(case=case['id']):
                    target = Path(temp) / case['id']
                    meta = prepare(case['id'], target)
                    self.assertEqual(len(meta['baseline']), 40)
                    run = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-v'], cwd=target, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    status = subprocess.check_output(['git','status','--porcelain'],cwd=target,text=True).strip()
                    self.assertEqual(status, 'M notes.txt' if case.get('dirty_note') else '')
    def test_verification_fixture_contains_real_bypass(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'case'; prepare('p2-verification-ingress', target)
            # Fixture self-test, not an Agent evaluation: confirm the planted defect is observable.
            probe = "from handler import Store,handle; s=Store(); handle(s,'verify'); assert s.state=='verify' and s.writes==1"
            subprocess.run([sys.executable,'-B','-c',probe],cwd=target,check=True)
    def test_prepare_rejects_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError): prepare('p2-landing-wiring', Path(temp))

if __name__ == '__main__': unittest.main()
