"""Final regression and isolated stage copy -> snapshot -> extraction -> chunks -> real model smoke."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / '1. Naive RAG'
PYTHON = str(STAGE / '.venv/bin/python')
OUT = Path(__file__).resolve().parent / '05-delivery'
OUT.mkdir(exist_ok=False)
commands = []


def run(name, command, cwd, timeout=180):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    (OUT / (name + '-stdout.txt')).write_text(result.stdout or '(no stdout)\n')
    (OUT / (name + '-stderr.txt')).write_text(result.stderr or '(no stderr)\n')
    commands.append({'name': name, 'command': command, 'cwd': str(cwd), 'returncode': result.returncode})
    (OUT / 'commands.json').write_text(json.dumps(commands, ensure_ascii=False, indent=2) + '\n')
    print(name, result.returncode, flush=True)
    if result.returncode:
        raise RuntimeError(name + ' failed: ' + result.stderr[-1000:])
    return result.stdout


run('stage-tests', [PYTHON, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], STAGE)
run('root-tests', ['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-v'], REPO)
with tempfile.TemporaryDirectory(prefix='p006-standalone-') as temp:
    copy = Path(temp) / 'Naive RAG'
    shutil.copytree(STAGE, copy, ignore=shutil.ignore_patterns('.runtime', '.venv', '__pycache__', '*.pyc', '.DS_Store'))
    (copy / '.runtime').mkdir()
    run('copy-tests', [PYTHON, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], copy)
    run('copy-snapshot', [PYTHON, 'scripts/snapshot_drive_fixture.py', '--catalog', 'data/source-v2/drive-fixture-catalog.json',
                          '--output-dir', '.runtime/snapshot'], copy)
    run('copy-ingest', [PYTHON, 'scripts/ingest_documents.py', '--manifest', '.runtime/snapshot/manifest.json',
                        '--output-dir', '.runtime/documents'], copy)
    run('copy-chunk', [PYTHON, 'scripts/chunk_documents.py', '--documents', '.runtime/documents/manifest.json',
                       '--method', 'fixed', '--size-chars', '400', '--overlap-chars', '80', '--output-dir', '.runtime/chunks'], copy)
    run('copy-evaluation', [PYTHON, 'scripts/prepare_source_evaluation.py', '--documents', '.runtime/documents/manifest.json',
                            '--spec', 'data/source-v2/evaluation-spec.json', '--output-dir', '.runtime/evaluation'], copy)
    # Canonical content and IDs must be identical after reproducing from copied source bytes.
    expected = json.loads((STAGE / 'data/source-v2/fixed-400-80/manifest.json').read_text())
    actual = json.loads((copy / '.runtime/chunks/manifest.json').read_text())
    assert actual['run_id'] == expected['run_id']
    assert actual['chunks_sha256'] == expected['chunks_sha256']
    assert (copy / '.runtime/chunks/chunks.jsonl').read_bytes() == (STAGE / 'data/source-v2/fixed-400-80/chunks.jsonl').read_bytes()
    assert (copy / '.runtime/chunks/source-map.json').read_bytes() == (STAGE / 'data/source-v2/fixed-400-80/source-map.json').read_bytes()
    assert (copy / '.runtime/evaluation/source-evaluation.json').read_bytes() == (STAGE / 'data/source-v2/evaluation/source-evaluation.json').read_bytes()
    run('copy-index', [PYTHON, 'scripts/build_dense_index.py', '--chunks', '.runtime/chunks/chunks.jsonl',
                       '--index-dir', '.runtime/index'], copy)
    smoke = []
    for name, question in [('q04', '입사 1년 미만 직원의 연차는 언제 생기나요?'), ('q13', '퇴직금 계산식은 어떻게 되나요?')]:
        raw = run('copy-' + name, [PYTHON, 'scripts/ask.py', '--chunks', '.runtime/chunks/chunks.jsonl',
                      '--index-dir', '.runtime/index', '--question', question], copy, 240)
        value = json.loads(raw)
        if name == 'q04':
            assert value['status'] == 'answered', value
            assert value['citations'] and all(c['document_id'] == 'hr-v2-annual' for c in value['citations'])
        else:
            assert value['status'] == 'abstained' and value['reason'] == 'model_abstained', value
        smoke.append({'question': question, 'status': value['status'], 'reason': value['reason'], 'answer': value['answer']})
    report = {'status': 'PASS', 'same_canonical_chunk_and_source_map_bytes': True, 'same_run_id': actual['run_id'],
              'same_evaluation_bytes': True, 'smoke': smoke,
              'runtime_note': 'Source-only copy used the already installed locked interpreter and the owned loopback Ollama models. No model or venv copied; new index built from copied sources.'}
    (OUT / 'copy-summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
# Existing UI remains the legacy corpus; check transport and API defaults without changing UI.
with urllib.request.urlopen('http://127.0.0.1:8000/api/status', timeout=10) as r:
    (OUT / 'ui-status.json').write_text(json.dumps(json.load(r), ensure_ascii=False, indent=2) + '\n')
print('DELIVERY PASS', flush=True)
