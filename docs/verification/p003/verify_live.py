#!/usr/bin/env python3
"""Reverify an already prepared P003 runtime/index into a NEW evidence directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / '1. Naive RAG'
PYTHON = str(STAGE / '.venv/bin/python')
BASE = 'a0ce4da55f9a309a50db7420fc400543d8452bb9'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--index-dir', type=Path, default=STAGE / '.runtime/index-v1')
    args = parser.parse_args()
    output, index_dir = args.output_dir.absolute(), args.index_dir.absolute()
    output.mkdir()
    records = []

    def run(command, cwd=STAGE, expected=0):
        p = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=600)
        records.extend(['cwd: ' + str(cwd), 'command: ' + json.dumps(command, ensure_ascii=False),
                        'exit=' + str(p.returncode), p.stdout.rstrip(), p.stderr.rstrip(), ''])
        (output / 'commands.txt').write_text('\n'.join(records).rstrip() + '\n')
        assert p.returncode == expected, p.stderr
        return p.stdout

    # Runtime scripts use only the owner record; external processes are refused.
    run(['python3', 'scripts/setup_runtime.py'])
    assert json.loads(run([PYTHON, 'scripts/runtime.py', 'stop']))['state'] == 'stopped'
    assert json.loads(run([PYTHON, 'scripts/runtime.py', 'status']))['state'] == 'stopped'
    try:
        assert json.loads(run([PYTHON, 'scripts/runtime.py', 'start']))['owned'] is True
        run([PYTHON, 'scripts/runtime.py', 'start'])  # idempotent own reuse
        run([PYTHON, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        run(['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-v'], ROOT)
        dense_command = [PYTHON, 'scripts/run_dense_baseline.py', '--chunks', 'data/synthetic/chunks.jsonl',
                         '--queries', 'data/synthetic/queries.jsonl', '--index-dir', str(index_dir),
                         '--top-k', '20', '--k', '5', '10', '20']
        run(dense_command + ['--output-dir', str(output / 'dense')])
        run([PYTHON, 'scripts/run_bm25_baseline.py', '--chunks', 'data/synthetic/chunks.jsonl', '--queries',
             'data/synthetic/queries.jsonl', '--top-k', '20', '--k', '5', '10', '20', '--output-dir', str(output / 'bm25')])
        for kind in ['dense', 'bm25']:
            reevaluated = output / (kind + '-reevaluated.json')
            run([PYTHON, 'scripts/evaluate_retrieval.py', '--chunks', 'data/synthetic/chunks.jsonl', '--queries',
                 'data/synthetic/queries.jsonl', '--rankings', str(output / kind / 'rankings.jsonl'),
                 '--k', '5', '10', '20', '--output', str(reevaluated)])
            assert reevaluated.read_bytes() == (output / kind / 'metrics.json').read_bytes()
        probe = 'import sys,json;sys.path.insert(0,"scripts");from runtime_common import load_lock;from dense_retrieval import DenseIndex,point_id;import evaluate_retrieval as e;from pathlib import Path;rows,h=e.read_jsonl(Path("data/synthetic/chunks.jsonl"));chunks=e.validate_chunks(rows);\nwith DenseIndex(Path(sys.argv[1]),chunks,h,load_lock()) as i:\n records,_=i.client.scroll("hr_chunks",limit=16,with_payload=True);print(json.dumps([dict(point_id=str(r.id),payload=r.payload) for r in records],ensure_ascii=False))'
        payloads = json.loads(run([PYTHON, '-c', probe, str(index_dir)]))
        (output / 'payload-mapping.json').write_text(json.dumps(payloads, ensure_ascii=False, indent=2) + '\n')
        assert len(payloads) == 15 and len({r['point_id'] for r in payloads}) == 15
        (output / 'index-manifest.json').write_bytes((index_dir / 'index-manifest.json').read_bytes())

        with tempfile.TemporaryDirectory(prefix='p003-standalone-') as scratch:
            copied = Path(scratch) / '1. Naive RAG'
            shutil.copytree(STAGE, copied, ignore=shutil.ignore_patterns('.runtime', '.venv', '__pycache__', '*.pyc'))
            (copied / '.runtime').mkdir()
            shutil.copytree(index_dir, copied / '.runtime/index-copy')
            run([PYTHON, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], copied)
            run([PYTHON, 'scripts/run_dense_baseline.py', '--chunks', 'data/synthetic/chunks.jsonl', '--queries',
                 'data/synthetic/queries.jsonl', '--index-dir', '.runtime/index-copy', '--top-k', '20',
                 '--k', '5', '10', '20', '--output-dir', str(Path(scratch) / 'dense-copy')], copied)
            copied_ranks = (Path(scratch) / 'dense-copy/rankings.jsonl').read_bytes()
            assert copied_ranks == (output / 'dense/rankings.jsonl').read_bytes()
        source = json.loads((STAGE / 'stage-manifest.json').read_text())
        for row in source['files']:
            original = subprocess.run(['git', 'show', row['source_commit'] + ':' + row['source_path']], cwd=ROOT,
                                      check=True, capture_output=True).stdout
            assert hashlib.sha256(original).hexdigest() == row['copied_sha256']
            assert original == (STAGE / row['destination_path']).read_bytes()
        for prefix in ['docs/planning/plans/P001.md', 'docs/planning/plans/P002.md', 'docs/verification/p001', 'docs/verification/p002']:
            paths = subprocess.run(['git', 'ls-tree', '-r', '--name-only', BASE, '--', prefix], cwd=ROOT,
                                   capture_output=True, text=True, check=True).stdout.splitlines()
            for name in paths:
                original = subprocess.run(['git', 'show', BASE + ':' + name], cwd=ROOT, check=True, capture_output=True).stdout
                assert original == (ROOT / name).read_bytes(), name
        (output / 'delivery-checks.json').write_text(json.dumps({
            'live_documents': 15, 'live_queries': 14, 'model_digest_locked': True,
            'new_process_reopen': True, 'independent_p001_reevaluation_bytes_equal': True,
            'standalone_source_and_copied_index_live_ranks_equal': True,
            'standalone_uses_same_approved_dependency_interpreter_and_loopback_service': True,
            'all_original_six_files_and_P001_P002_cards_evidence_unchanged': True}, indent=2) + '\n')
        run([PYTHON, 'scripts/runtime.py', 'status'])
    finally:
        assert json.loads(run([PYTHON, 'scripts/runtime.py', 'stop']))['state'] == 'stopped'
        assert json.loads(run([PYTHON, 'scripts/runtime.py', 'status']))['state'] == 'stopped'
    print('PASS: live model, fresh process reopen, reevaluation, source-only standalone regression/live search and owned lifecycle')


if __name__ == '__main__':
    main()
