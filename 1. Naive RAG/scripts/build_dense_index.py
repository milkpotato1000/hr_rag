#!/usr/bin/env python3
"""Embed fixed synthetic chunks and create a NEW local persistent index."""
import argparse
import json
import sys
from time import perf_counter

import evaluate_retrieval as evaluation
from runtime_common import LocalAPI, ENDPOINT, load_lock


def build(chunks_path, index_dir, endpoint=ENDPOINT):
    from dense_retrieval import create_index, check_new_path
    check_new_path(index_dir)
    rows, digest = evaluation.read_jsonl(chunks_path)
    chunks = evaluation.validate_chunks(rows)
    lock, api = load_lock(), LocalAPI(endpoint)
    api.check(lock)
    texts = [chunks[cid]['title'] + '\n' + chunks[cid]['text'] for cid in sorted(chunks)]
    start = perf_counter()
    vectors = api.embed(texts, lock['model']['dimension'])
    embed_ms = (perf_counter() - start) * 1000
    start = perf_counter()
    manifest = create_index(chunks, digest, vectors, lock, index_dir, before_publish=lambda: api.check(lock))
    return {'index_manifest': manifest, 'observations': {'document_embedding_ms': embed_ms,
            'index_build_verify_ms': (perf_counter() - start) * 1000}}


def main(argv=None):
    from pathlib import Path
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--chunks', type=Path, required=True)
    p.add_argument('--index-dir', type=Path, required=True)
    p.add_argument('--endpoint', default=ENDPOINT)
    args = p.parse_args(argv)
    try:
        print(json.dumps(build(args.chunks, args.index_dir, args.endpoint), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, ImportError, RuntimeError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
