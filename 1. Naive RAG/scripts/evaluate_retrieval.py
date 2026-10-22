#!/usr/bin/env python3
"""Evaluate fixed retrieval rankings with Python 3.9+ and no dependencies."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile

EVALUATOR_VERSION = "1.0.0"
METRICS = ("recall", "precision", "mrr", "ndcg")


class InputError(ValueError):
    """An invalid dataset, ranking, or CLI option."""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate JSON key: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise InputError("non-JSON numeric constant: " + value)


def read_jsonl(path):
    raw = path.read_bytes()
    if not raw.strip():
        raise InputError(str(path) + ": empty file")
    rows = []
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        try:
            row = json.loads(line, object_pairs_hook=unique_object,
                             parse_constant=reject_constant)
            if not isinstance(row, dict):
                raise InputError("record must be an object")
        except ValueError as exc:
            raise InputError("{}:{}: {}".format(path, line_number, exc)) from exc
        rows.append(row)
    return rows, hashlib.sha256(raw).hexdigest()


def string_field(row, key, context):
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InputError(context + ": " + key + " must be a nonempty string")
    return value


def validate_chunks(rows):
    chunks = {}
    for row in rows:
        context = "chunk " + repr(row.get("chunk_id"))
        for key in ("chunk_id", "document_id", "version", "title", "text", "source"):
            string_field(row, key, context)
        if row.get("synthetic") is not True:
            raise InputError(context + ": synthetic must be true")
        if not row["source"].startswith("synthetic://"):
            raise InputError(context + ": source must start with synthetic://")
        chunk_id = row["chunk_id"]
        if chunk_id in chunks:
            raise InputError("duplicate chunk_id: " + chunk_id)
        chunks[chunk_id] = row
    return chunks


def validate_queries(rows, chunks):
    queries = {}
    for row in rows:
        context = "query " + repr(row.get("query_id"))
        query_id = string_field(row, "query_id", context)
        string_field(row, "question", context)
        if query_id in queries:
            raise InputError("duplicate query_id: " + query_id)
        answerability = row.get("answerability")
        if answerability not in ("answerable", "unanswerable"):
            raise InputError(context + ": invalid answerability")
        relevance = row.get("relevance")
        if not isinstance(relevance, dict):
            raise InputError(context + ": relevance must be an object")
        for chunk_id, grade in relevance.items():
            if chunk_id not in chunks:
                raise InputError(context + ": unknown relevance chunk_id: " + chunk_id)
            if type(grade) is not int or not 0 <= grade <= 3:
                raise InputError(context + ": relevance grade must be an integer from 0 to 3")
        if answerability == "answerable" and not any(relevance.values()):
            raise InputError(context + ": answerable query needs a positive relevance grade")
        if answerability == "unanswerable" and relevance:
            raise InputError(context + ": unanswerable relevance must be empty")
        queries[query_id] = row
    return queries


def validate_rankings(rows, queries, chunks):
    rankings = {}
    for row in rows:
        query_id = string_field(row, "query_id", "ranking")
        if query_id not in queries:
            raise InputError("unknown ranking query_id: " + query_id)
        if query_id in rankings:
            raise InputError("duplicate ranking query_id: " + query_id)
        ids = row.get("chunk_ids")
        if not isinstance(ids, list):
            raise InputError("ranking chunk_ids must be a list: " + query_id)
        seen = set()
        for chunk_id in ids:
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise InputError("ranking chunk_id must be a nonempty string: " + query_id)
            if chunk_id not in chunks:
                raise InputError("unknown ranking chunk_id: " + chunk_id)
            if chunk_id in seen:
                raise InputError("duplicate ranking chunk_id: " + chunk_id)
            seen.add(chunk_id)
        rankings[query_id] = ids
    missing = sorted(set(queries) - set(rankings))
    if missing:
        raise InputError("missing ranking queries: " + ", ".join(missing))
    return rankings


def metrics_at_k(relevance, ranking, k):
    relevant_count = sum(grade > 0 for grade in relevance.values())
    top_grades = [relevance.get(chunk_id, 0) for chunk_id in ranking[:k]]
    hits = sum(grade > 0 for grade in top_grades)
    reciprocal = next((1.0 / rank for rank, grade in enumerate(top_grades, 1)
                       if grade > 0), 0.0)
    dcg = sum((2 ** grade - 1) / math.log2(rank + 1)
              for rank, grade in enumerate(top_grades, 1))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum((2 ** grade - 1) / math.log2(rank + 1)
               for rank, grade in enumerate(ideal, 1))
    return {"recall": hits / relevant_count, "precision": hits / k,
            "mrr": reciprocal, "ndcg": dcg / idcg}


def evaluate(chunks, queries, rankings, ks, hashes):
    answerable_count = sum(q["answerability"] == "answerable" for q in queries.values())
    unanswerable_count = len(queries) - answerable_count
    per_query = []
    for query_id, query in queries.items():
        per_query.append({
            "query_id": query_id,
            "answerability": query["answerability"],
            "retrieved_count": len(rankings[query_id]),
            "metrics": {
                str(k): metrics_at_k(query["relevance"], rankings[query_id], k)
                if query["answerability"] == "answerable"
                else {name: None for name in METRICS}
                for k in ks
            },
        })
    macro = {
        str(k): {
            name: sum(row["metrics"][str(k)][name] for row in per_query
                      if row["answerability"] == "answerable") / answerable_count
            if answerable_count else None
            for name in METRICS
        }
        for k in ks
    }
    with_results = sum(bool(rankings[qid]) for qid, q in queries.items()
                       if q["answerability"] == "unanswerable")
    return {
        "metadata": {"evaluator_version": EVALUATOR_VERSION, "sha256": hashes,
                     "k": ks, "chunk_count": len(chunks), "query_count": len(queries),
                     "answerable_count": answerable_count,
                     "unanswerable_count": unanswerable_count},
        "per_query": per_query,
        "macro": macro,
        "unanswerable": {
            "query_count": unanswerable_count,
            "with_results_count": with_results,
            "empty_results_count": unanswerable_count - with_results,
            "with_results_ratio": with_results / unanswerable_count if unanswerable_count else None,
            "empty_results_ratio": (unanswerable_count - with_results) / unanswerable_count
            if unanswerable_count else None,
        },
    }


def write_atomic(path, result):
    """Only replace the destination after all validation and serialization succeed."""
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".retrieval-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--rankings", type=Path, required=True)
    parser.add_argument("--k", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if any(k <= 0 for k in args.k) or len(set(args.k)) != len(args.k):
            raise InputError("K must contain positive unique integers")
        for path in (args.chunks, args.queries, args.rankings):
            if (args.output.resolve() == path.resolve()
                    or (args.output.exists() and path.exists() and args.output.samefile(path))):
                raise InputError("output must not alias an input file")
        chunk_rows, chunk_hash = read_jsonl(args.chunks)
        query_rows, query_hash = read_jsonl(args.queries)
        ranking_rows, ranking_hash = read_jsonl(args.rankings)
        chunks = validate_chunks(chunk_rows)
        queries = validate_queries(query_rows, chunks)
        rankings = validate_rankings(ranking_rows, queries, chunks)
        report = evaluate(chunks, queries, rankings, args.k,
                          {"chunks": chunk_hash, "queries": query_hash, "rankings": ranking_hash})
        write_atomic(args.output, report)
    except (OSError, ValueError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
