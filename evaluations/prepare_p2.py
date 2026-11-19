#!/usr/bin/env python3
"""Materialize an immutable scenario baseline in a new disposable directory."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def prepare(case_id, destination):
    cases = {c['id']: c for c in json.loads((ROOT / 'cases.json').read_text())}
    case = cases.get(case_id, {})
    if not case.get('fixture'):
        raise ValueError('case has no materialized fixture')
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('destination must not exist')
    if destination.is_relative_to(ROOT.parent):
        raise ValueError('destination must be outside the framework checkout')
    shutil.copytree(ROOT / 'fixtures' / case['fixture'], destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # Windows flashes a console window for every child process unless suppressed.
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    def git(*args):
        return subprocess.check_output(['git', '-C', str(destination), *args], text=True, creationflags=flags).strip()
    git('init', '-q'); git('add', '.'); git('-c', 'user.name=Vibe Eval', '-c', 'user.email=eval@example.invalid', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Evaluation baseline')
    sha = git('rev-parse', 'HEAD')
    if case.get('dirty_note'):
        with (destination / 'notes.txt').open('a') as stream:
            stream.write('User draft: preserve this uncommitted line.\n')
    return {'case': case_id, 'repo': str(destination), 'baseline': sha, 'prompt': case['prompt'], 'setup': case['setup']}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('case'); parser.add_argument('destination', type=Path); args = parser.parse_args()
    print(json.dumps(prepare(args.case, args.destination), ensure_ascii=False, indent=2))
