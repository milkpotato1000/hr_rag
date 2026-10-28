#!/usr/bin/env python3
"""Reopen persistent Dense index, search, and evaluate with the P001 evaluator."""
import argparse
import json
from pathlib import Path
import platform
import sys
import tempfile
from time import perf_counter

import evaluate_retrieval as evaluation
from run_bm25_baseline import validate_options, write_json, write_jsonl, publish_directory
from runtime_common import LocalAPI, ENDPOINT, load_lock


def run(chunks_path, queries_path, index_dir, output_dir, top_k=20, ks=(5, 10, 20), endpoint=ENDPOINT):
    from dense_retrieval import DenseIndex, check_new_path
    validate_options(top_k, ks)
    output_dir = check_new_path(output_dir)
    chunk_rows, chunk_hash = evaluation.read_jsonl(chunks_path)
    query_rows, query_hash = evaluation.read_jsonl(queries_path)
    chunks = evaluation.validate_chunks(chunk_rows)
    queries = evaluation.validate_queries(query_rows, chunks)
    lock, api = load_lock(), LocalAPI(endpoint)
    api.check(lock)
    start = perf_counter()
    index = DenseIndex(index_dir, chunks, chunk_hash, lock)
    index_ms = (perf_counter() - start) * 1000
    rankings, scores, embed_times, search_times = [], [], {}, {}
    with index:
        for qid in sorted(queries):
            start = perf_counter()
            vector = api.embed([queries[qid]['question']], lock['model']['dimension'])[0]
            embed_times[qid] = (perf_counter() - start) * 1000
            start = perf_counter()
            results = index.search(vector, top_k)
            search_times[qid] = (perf_counter() - start) * 1000
            rankings.append({'query_id': qid, 'chunk_ids': [row['chunk_id'] for row in results]})
            scores.append({'query_id': qid, 'results': results})
        manifest = index.manifest
    api.check(lock)
    with tempfile.TemporaryDirectory(prefix='.dense-run-', dir=output_dir.parent) as scratch:
        staging = Path(scratch)
        write_jsonl(staging / 'rankings.jsonl', rankings)
        write_jsonl(staging / 'scores.jsonl', scores)
        ranked_rows, rank_hash = evaluation.read_jsonl(staging / 'rankings.jsonl')
        ranking_map = evaluation.validate_rankings(ranked_rows, queries, chunks)
        hashes = {'chunks': chunk_hash, 'queries': query_hash, 'rankings': rank_hash}
        report = evaluation.evaluate(chunks, queries, ranking_map, list(ks), hashes)
        write_json(staging / 'metrics.json', report)
        write_json(staging / 'run.json', {
            'retriever_version': 'dense-cosine-v1', 'endpoint': endpoint, 'model': lock['model'],
            'ollama': lock['ollama'], 'index_manifest': manifest, 'sha256': hashes,
            'parameters': {'top_k': top_k, 'k': list(ks), 'distance': 'Cosine', 'truncate': False},
            'environment': {'python_version': platform.python_version(), 'platform': platform.platform(),
                            'qdrant_client_version': lock['qdrant_client_version']},
            'observations': {'index_open_verify_ms': index_ms, 'query_embedding_ms': embed_times,
                             'vector_search_ms': search_times}})
        publish_directory(staging, output_dir)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['chunks', 'queries', 'index-dir', 'output-dir']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--top-k', type=int, default=20)
    p.add_argument('--k', type=int, nargs='+', default=[5, 10, 20])
    p.add_argument('--endpoint', default=ENDPOINT)
    args = p.parse_args(argv)
    try:
        run(args.chunks, args.queries, args.index_dir, args.output_dir, args.top_k, args.k, args.endpoint)
    except (OSError, ValueError, KeyError, ImportError, RuntimeError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
