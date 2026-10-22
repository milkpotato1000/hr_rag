#!/usr/bin/env python3
"""Real fixed-set generation. Pass only question text to the product CLI."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / '1. Naive RAG'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    output = args.output_dir.resolve()
    output.mkdir()
    rubric = Path(__file__).with_name('rubric.json')
    manifest = {'started_at': datetime.now().astimezone().isoformat(),
                'rubric_sha256_before_run': hashlib.sha256(rubric.read_bytes()).hexdigest(),
                'provider': 'actual local Ollama Qwen3:4b; not a fixture',
                'settings': {'retriever': 'dense', 'top_k': 5, 'max_context_chars': 8000, 'timeout_seconds': 120}}
    (output / 'run.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    queries = [json.loads(line) for line in (STAGE / 'data/synthetic/queries.jsonl').read_text().splitlines()]
    with (output / 'commands.txt').open('w') as log:
        for row in queries:
            command = [str(STAGE / '.venv/bin/python'), 'scripts/ask.py', '--question', row['question']]
            result = subprocess.run(command, cwd=STAGE, capture_output=True, text=True, timeout=300)
            log.write(json.dumps({'query_id': row['query_id'], 'command': command, 'exit': result.returncode,
                                  'stderr': result.stderr}, ensure_ascii=False) + '\n')
            log.flush()
            parsed = json.loads(result.stdout)
            (output / (row['query_id'] + '.json')).write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + '\n')
            print(row['query_id'], parsed['status'], parsed['reason'], flush=True)
    manifest['finished_at'] = datetime.now().astimezone().isoformat()
    (output / 'run.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
