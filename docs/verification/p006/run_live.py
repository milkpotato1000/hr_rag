"""Explicit new-corpus CLI smoke; labels are used only by this verification runner."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / '1. Naive RAG'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path, required=True)
OUT = parser.parse_args().output_dir
OUT.mkdir(exist_ok=False)
questions = [json.loads(x) for x in (STAGE / 'data/synthetic/queries.jsonl').read_text().splitlines()]
for qid in ('q06', 'q13'):
    question = next(x['question'] for x in questions if x['query_id'] == qid)
    cmd = [str(STAGE / '.venv/bin/python'), str(STAGE / 'scripts/ask.py'), '--question', question,
        '--chunks', str(STAGE / 'data/source-v2/fixed-400-80/chunks.jsonl'),
        '--index-dir', str(STAGE / '.runtime/index-source-v2-fixed-400-80'), '--top-k', '5']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    (OUT / (qid + '.json')).write_text(result.stdout)
    (OUT / (qid + '-stderr.txt')).write_text(result.stderr or 'No stderr.\n')
    print(qid, result.returncode, flush=True)
    if result.returncode: raise RuntimeError(result.stderr)
    value = json.loads(result.stdout)
    print(value['status'], value['answer'], flush=True)
