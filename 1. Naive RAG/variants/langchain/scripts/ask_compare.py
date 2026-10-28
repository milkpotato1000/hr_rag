#!/usr/bin/env python3
"""Ask the local Naive RAG pipeline; exactly one result JSON on stdout."""
import argparse
import json
import sys
from pathlib import Path
from rag import INDEX, CHUNKS
from comparison import ask


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    p = Parser(description=__doc__)
    p.add_argument('--question', required=True)
    p.add_argument('--implementation', default='direct')
    p.add_argument('--retriever', default='dense')
    p.add_argument('--top-k', type=int, default=5)
    p.add_argument('--index-dir', type=Path, default=INDEX)
    p.add_argument('--chunks', dest='chunks_path', type=Path, default=CHUNKS,
                   help='explicit corpus; defaults to the preserved 15 hand-authored chunks')
    p.add_argument('--max-context-chars', type=int, default=8000)
    p.add_argument('--timeout-seconds', type=float, default=120)
    try:
        args = p.parse_args(argv)
        result = ask(**vars(args))
    except ValueError as exc:
        result = {'status': 'error', 'answer': '입력 인자를 확인하세요.', 'citations': [],
                  'reason': 'input', 'trace': {'error': {'kind': 'input', 'message': str(exc)}}}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    if result['status'] == 'error':
        print('error: ' + result['trace']['error']['message'], file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
