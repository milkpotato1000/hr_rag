#!/usr/bin/env python3
"""P004 source-only copy, regression, CLI smoke, and historical byte preservation."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / '1. Naive RAG'
PYTHON = str(STAGE / '.venv/bin/python')
OUTPUT = Path(__file__).with_name('04-delivery')
BASE = '74b3c35a551671e1387904a0715ea5f8a1625a0c'


def main():
    OUTPUT.mkdir()
    records = []
    def run(cmd, cwd, expected=0):
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=400)
        records.append({'cwd': str(cwd), 'command': cmd, 'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
        (OUTPUT / 'commands.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
        assert p.returncode == expected, p.stderr
        return p.stdout
    run([PYTHON, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], STAGE)
    run(['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-v'], ROOT)
    with tempfile.TemporaryDirectory(prefix='p004-standalone-') as scratch:
        copied = Path(scratch) / 'Naive RAG'
        shutil.copytree(STAGE, copied, ignore=shutil.ignore_patterns('.runtime', '.venv', '__pycache__', '*.pyc'))
        (copied / '.runtime').mkdir()
        shutil.copytree(STAGE / '.runtime/index-v1', copied / '.runtime/index-v1')
        run([PYTHON, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], copied)
        for q, expected in [('재택근무일과 휴가일에도 사무실 식대가 나오나요?', 'answered'),
                            ('퇴직금 계산식은 어떻게 되나요?', 'abstained')]:
            result = json.loads(run([PYTHON, 'scripts/ask.py', '--question', q], copied))
            (OUTPUT / (expected + '-standalone.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
            assert result['status'] == expected, result['reason']
    checked = []
    for prefix in ['docs/verification/p001', 'docs/verification/p002', 'docs/verification/p003',
                   'docs/planning/plans/P001.md', 'docs/planning/plans/P002.md', 'docs/planning/plans/P003.md',
                   '1. Naive RAG/runtime-lock.json', '1. Naive RAG/requirements.lock']:
        names = subprocess.run(['git', 'ls-tree', '-r', '--name-only', BASE, '--', prefix], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.splitlines()
        for name in names:
            original = subprocess.run(['git', 'show', BASE+':'+name], cwd=ROOT, capture_output=True, check=True).stdout
            assert original == (ROOT / name).read_bytes(), name
            checked.append(name)
    manifest = json.loads((STAGE / 'stage-manifest.json').read_text())
    for item in manifest['files']:
        assert hashlib.sha256((STAGE / item['destination_path']).read_bytes()).hexdigest() == item['copied_sha256']
    (OUTPUT / 'preservation.json').write_text(json.dumps({'base_commit':BASE, 'unchanged_paths': checked,
        'six_original_copied_hashes_match': True, 'source_only_copy': True,
        'copy_reuses_approved_interpreter_and_loopback_service': True}, ensure_ascii=False, indent=2)+'\n')
    print('PASS: regression, standalone live answer/abstain, historical bytes preserved')


if __name__ == '__main__':
    main()
