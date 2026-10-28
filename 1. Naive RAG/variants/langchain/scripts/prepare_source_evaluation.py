#!/usr/bin/env python3
"""Author/validate evaluation-only source spans. Never imported by retrieval or generation."""
import argparse
import json
from pathlib import Path
from document_common import (read_json, write_json, fingerprint, file_hash, atomic_directory,
                             DocumentError, nonempty, cli_error)
from chunk_documents import load_documents, page_intersections


def locate(text, quote):
    """Ignore whitespace only to locate an authored quote; store the EXACT canonical slice."""
    nonempty(quote, 'fact quote')
    positions = [i for i, char in enumerate(text) if not char.isspace()]
    compact = ''.join(text[i] for i in positions)
    target = ''.join(quote.split())
    if not target:
        raise DocumentError('invalid_fact', 'quote contains no text')
    first = compact.find(target)
    if first < 0 or compact.find(target, first + 1) >= 0:
        raise DocumentError('invalid_fact', 'authored fact quote is missing or ambiguous: ' + quote)
    return positions[first], positions[first + len(target) - 1] + 1


def validate_evaluation(value, loaded):
    docs = {row['document_id']: (row, text) for row, text in loaded}
    seen, fact_ids = set(), set()
    for fact in value['facts']:
        fid = nonempty(fact.get('fact_id'), 'fact_id')
        if fid in fact_ids or not fact.get('required_spans'):
            raise DocumentError('invalid_fact', 'duplicate fact or empty spans')
        fact_ids.add(fid)
        nonempty(fact.get('meaning'), 'fact meaning')
        for span in fact['required_spans']:
            if span['span_id'] in seen:
                raise DocumentError('invalid_fact', 'duplicate span ID')
            seen.add(span['span_id'])
            if span['document_id'] not in docs:
                raise DocumentError('invalid_fact', 'unknown document')
            row, text = docs[span['document_id']]
            a, b = span['start'], span['end']
            if (type(a) is not int or type(b) is not int or not 0 <= a < b <= len(text)
                    or text[a:b] != span['quote'] or not span['quote'].strip()
                    or span['canonical_sha256'] != row['canonical_sha256']
                    or span['original_sha256'] != row['original_sha256']
                    or span['provenance'] != row['provenance']
                    or span['pages'] != page_intersections(row['pages'], a, b)):
                raise DocumentError('invalid_fact', 'span does not trace to the exact original/canonical slice')
    queries = set()
    for q in value['questions']:
        qid = nonempty(q.get('query_id'), 'query_id')
        nonempty(q.get('question'), 'question')
        nonempty(q.get('semantic_rubric'), 'semantic rubric')
        ids = q['required_fact_ids']
        if (qid in queries or not isinstance(ids, list) or len(ids) != len(set(ids))
                or any(fid not in fact_ids for fid in ids)
                or q['answerability'] not in ('answerable', 'unanswerable')
                or bool(ids) != (q['answerability'] == 'answerable')):
            raise DocumentError('invalid_fact', 'question/fact mapping is invalid')
        queries.add(qid)
    if not fact_ids or not queries:
        raise DocumentError('invalid_fact', 'empty facts or questions')


def prepare(documents, spec_path, output_dir):
    manifest, loaded = load_documents(documents)
    spec = read_json(spec_path)
    docs = {row['document_id']: (row, text) for row, text in loaded}
    facts = []
    for fact in spec['facts']:
        spans = []
        for authored in fact['required_spans']:
            row, text = docs[authored['document_id']]
            a, b = locate(text, authored['quote'])
            identity = {'fact_id': fact['fact_id'], 'document_id': row['document_id'],
                        'canonical_sha256': row['canonical_sha256'], 'start': a, 'end': b}
            spans.append({'span_id': 'span-' + fingerprint(identity), 'document_id': row['document_id'],
                          'start': a, 'end': b, 'quote': text[a:b], 'canonical_sha256': row['canonical_sha256'],
                          'original_sha256': row['original_sha256'], 'provenance': row['provenance'],
                          'pages': page_intersections(row['pages'], a, b)})
        facts.append({'fact_id': fact['fact_id'], 'meaning': fact['meaning'], 'required_spans': spans})
    result = {'schema_version': 1, 'evaluation_version': 'source-facts-v1', 'usage': 'evaluation_only_not_runtime',
        'reviewer': 'Codex authored source rubric; not human adjudication or model self-grading',
        'offset_unit': 'Unicode code point [start,end) in canonical text',
        'ingestion_run_id': manifest['run_id'], 'spec_sha256': file_hash(spec_path),
        'facts': facts, 'questions': spec['questions'],
        'fact_semantics': 'Every required span is necessary; multiple chunks may jointly cover a fact. No chunk-ID qrels copied.',
        'scope': 'Evidence preparation only. Chunk comparison metrics and answer evaluation protocol are P007/P008.'}
    validate_evaluation(result, loaded)
    with atomic_directory(output_dir) as stage:
        write_json(stage / 'source-evaluation.json', result)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--documents', type=Path, required=True)
    p.add_argument('--spec', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = prepare(args.documents, args.spec, args.output_dir)
        print(json.dumps({'facts': len(result['facts']), 'questions': len(result['questions'])}))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return cli_error(exc)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
