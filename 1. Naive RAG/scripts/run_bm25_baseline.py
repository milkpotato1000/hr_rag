#!/usr/bin/env python3
"""Fixed BM25 baseline, using the local P001 validation and evaluator."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import tempfile
from time import perf_counter
import unicodedata

import evaluate_retrieval as evaluation

RETRIEVER_VERSION = "1.0.0"
TOKENIZER_ID = "unicode-word-v1"
TOKEN_PATTERN = r"[^\W_]+"
K1 = 1.2
B = 0.75
ARTIFACTS = ("rankings.jsonl", "scores.jsonl", "metrics.json", "run.json")


def tokenize(value):
    return re.findall(TOKEN_PATTERN, unicodedata.normalize("NFKC", value).casefold())


def validate_options(top_k, ks):
    if type(top_k) is not int or top_k <= 0:
        raise evaluation.InputError("top-k must be a positive integer")
    if (not isinstance(ks, (list, tuple)) or not ks
            or any(type(k) is not int or k <= 0 for k in ks)
            or len(set(ks)) != len(ks)):
        raise evaluation.InputError("K must contain positive unique integers")
    if top_k < max(ks):
        raise evaluation.InputError("top-k must be at least max(K)")


class BM25Index:
    """Index corpus text only. No query labels or relevance enter this class."""

    def __init__(self, chunks):
        if not chunks:
            raise evaluation.InputError("corpus must not be empty")
        self.counts = {}
        self.document_frequency = Counter()
        for chunk_id, chunk in sorted(chunks.items()):
            counts = Counter(tokenize(chunk["title"] + "\n" + chunk["text"]))
            self.counts[chunk_id] = counts
            self.document_frequency.update(counts.keys())
        self.lengths = {chunk_id: sum(counts.values()) for chunk_id, counts in self.counts.items()}
        self.n = len(self.counts)
        self.avgdl = sum(self.lengths.values()) / self.n

    def search(self, question, top_k):
        if type(top_k) is not int or top_k <= 0:
            raise evaluation.InputError("top-k must be a positive integer")
        if not isinstance(question, str):
            raise evaluation.InputError("question must be a string")
        tokens = sorted(set(tokenize(question)))
        results = []
        if not tokens or self.avgdl == 0:
            return tokens, results
        for chunk_id, counts in self.counts.items():
            score = 0.0
            norm = K1 * (1 - B + B * self.lengths[chunk_id] / self.avgdl)
            for token in tokens:
                tf = counts.get(token, 0)
                if not tf:
                    continue
                df = self.document_frequency[token]
                idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
                score += idf * tf * (K1 + 1) / (tf + norm)
            if not math.isfinite(score):
                raise evaluation.InputError("non-finite BM25 score")
            if score > 0:
                results.append({"chunk_id": chunk_id, "score": score})
        results.sort(key=lambda row: (-row["score"], row["chunk_id"]))
        return tokens, results[:top_k]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
                            for row in rows), encoding="utf-8")


def publish_directory(staging, destination):
    """Reserve a new path exclusively, then publish already completed artifacts.

    mkdir rejects existing files, directories, and dangling symlinks, including
    ones appearing after preflight. On failure remove only files this call made.
    """
    destination.mkdir()
    created = []
    try:
        for name in ARTIFACTS:
            target = destination / name
            with (staging / name).open("rb") as source, target.open("xb") as output:
                created.append(target)
                shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
    except BaseException:
        for target in reversed(created):
            target.unlink()
        destination.rmdir()
        raise


def run_baseline(chunks_path, queries_path, output_dir, top_k=20, ks=(5, 10, 20)):
    validate_options(top_k, ks)
    chunks_path, queries_path, output_dir = Path(chunks_path), Path(queries_path), Path(output_dir)
    if os.path.lexists(output_dir):
        raise evaluation.InputError("output-dir already exists: " + str(output_dir))
    if not output_dir.parent.is_dir():
        raise evaluation.InputError("output parent directory must exist")
    chunk_rows, chunk_hash = evaluation.read_jsonl(chunks_path)
    query_rows, query_hash = evaluation.read_jsonl(queries_path)
    chunks = evaluation.validate_chunks(chunk_rows)
    queries = evaluation.validate_queries(query_rows, chunks)

    started = perf_counter()
    index = BM25Index(chunks)
    index_ms = (perf_counter() - started) * 1000
    ranking_rows, score_rows, query_ms = [], [], {}
    for query_id in sorted(queries):
        started = perf_counter()
        tokens, results = index.search(queries[query_id]["question"], top_k)
        query_ms[query_id] = (perf_counter() - started) * 1000
        ranking_rows.append({"query_id": query_id, "chunk_ids": [row["chunk_id"] for row in results]})
        score_rows.append({"query_id": query_id, "query_tokens": tokens, "results": results})

    # Build and evaluate everything in an owned sibling scratch directory first.
    with tempfile.TemporaryDirectory(prefix=".bm25-", dir=output_dir.parent) as scratch:
        staging = Path(scratch)
        write_jsonl(staging / "rankings.jsonl", ranking_rows)
        write_jsonl(staging / "scores.jsonl", score_rows)
        saved_rankings, ranking_hash = evaluation.read_jsonl(staging / "rankings.jsonl")
        rankings = evaluation.validate_rankings(saved_rankings, queries, chunks)
        hashes = {"chunks": chunk_hash, "queries": query_hash, "rankings": ranking_hash}
        report = evaluation.evaluate(chunks, queries, rankings, list(ks), hashes)
        write_json(staging / "metrics.json", report)
        run = {
            "retriever_version": RETRIEVER_VERSION,
            "tokenizer": {"id": TOKENIZER_ID, "steps": ["NFKC", "casefold", "re.findall"],
                          "pattern": TOKEN_PATTERN},
            "parameters": {"k1": K1, "b": B, "top_k": top_k, "k": list(ks)},
            "environment": {"python_version": platform.python_version(),
                            "unicode_version": unicodedata.unidata_version,
                            "platform": platform.platform()},
            "sha256": hashes,
            "statistics": {"N": index.n, "avgdl": index.avgdl},
            "observations": {"index_build_ms": index_ms, "query_search_ms": query_ms},
        }
        write_json(staging / "run.json", run)
        publish_directory(staging, output_dir)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10, 20])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        run_baseline(args.chunks, args.queries, args.output_dir, args.top_k, args.k)
    except (OSError, ValueError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
