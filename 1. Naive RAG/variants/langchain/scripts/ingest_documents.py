#!/usr/bin/env python3
"""Extract a manifest-selected fixture snapshot into canonical text and page maps."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from document_common import (STAGE, NORMALIZATION, SEPARATOR, MAX_CHARS, PDF_TIMEOUT, DocumentError,
    read_json, write_json, fingerprint, file_hash, normalize, verify_file, validate_snapshot,
    provenance, atomic_directory, load_ingestion_lock, cli_error, new_path)


def pdf_pages(path, timeout):
    try:
        result = subprocess.run([sys.executable, str(STAGE / 'scripts/pdf_extract_worker.py'), str(path)],
                                capture_output=True, text=True, encoding='utf-8', timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise DocumentError('pdf_timeout', 'PDF extraction child exceeded timeout') from exc
    try:
        value = json.loads(result.stdout)
    except ValueError as exc:
        raise DocumentError('pdf_worker', 'PDF worker failed without a valid result: ' + result.stderr[-500:]) from exc
    if result.returncode or value.get('status') != 'ok':
        raise DocumentError(value.get('kind', 'pdf_worker'), value.get('message', 'PDF worker failed'))
    if not value.get('pages') or [x['page_number'] for x in value['pages']] != list(range(1, len(value['pages']) + 1)):
        raise DocumentError('missing_page', 'PDF extraction has missing/reordered pages')
    return value


def ingest(manifest_path, output_dir, pdf_timeout_seconds=PDF_TIMEOUT):
    started = perf_counter()
    if (type(pdf_timeout_seconds) not in (int, float) or not math.isfinite(pdf_timeout_seconds)
            or pdf_timeout_seconds <= 0):
        raise DocumentError('invalid_input', 'PDF timeout must be positive and finite')
    new_path(output_dir)
    lock = load_ingestion_lock()
    manifest_path = Path(manifest_path)
    manifest = read_json(manifest_path)
    rows = validate_snapshot(manifest)
    documents, review = [], []
    with atomic_directory(output_dir) as stage:
        (stage / 'pages').mkdir()
        (stage / 'canonical').mkdir()
        for row in rows:
            original = verify_file(manifest_path.parent, row['path'], row['sha256'])
            if row['format'] == 'pdf':
                result = pdf_pages(original, pdf_timeout_seconds)
            else:
                try:
                    text = original.read_bytes().decode('utf-8')
                except UnicodeDecodeError as exc:
                    raise DocumentError('invalid_utf8', 'Markdown/TXT must be UTF-8') from exc
                result = {'parser': {'name': 'python-utf8', 'version': sys.version.split()[0]},
                          'pages': [{'page_number': 1, 'text': text, 'image_count': 0,
                                     'classification': 'text' if text.strip() else 'blank_candidate'}]}
            pieces, page_map, cursor = [], [], 0
            for page in result['pages']:
                text = normalize(page['text'])
                page_id = row['document_id'] + '-p' + str(page['page_number'])
                raw_path, normalized_path = 'pages/' + page_id + '.raw.txt', 'pages/' + page_id + '.txt'
                (stage / raw_path).write_text(page['text'], encoding='utf-8', newline='')
                (stage / normalized_path).write_text(text, encoding='utf-8', newline='')
                if pieces:
                    cursor += len(SEPARATOR)
                page_map.append({'page_number': page['page_number'], 'start': cursor, 'end': cursor + len(text),
                    'raw_text_path': raw_path, 'raw_text_sha256': file_hash(stage / raw_path),
                    'text_path': normalized_path, 'text_sha256': file_hash(stage / normalized_path),
                    'classification': page['classification'], 'image_count': page['image_count']})
                pieces.append(text)
                cursor += len(text)
                if cursor > MAX_CHARS:
                    raise DocumentError('text_limit', 'canonical text exceeds one million characters')
                if page['classification'] != 'text':
                    review.append({'document_id': row['document_id'], 'page_number': page['page_number'],
                                   'classification': page['classification']})
            canonical = SEPARATOR.join(pieces)
            target = 'canonical/' + row['document_id'] + '.txt'
            (stage / target).write_text(canonical, encoding='utf-8', newline='')
            documents.append({'document_id': row['document_id'], 'version': row['version'], 'title': row['title'],
                'synthetic': True, 'original_path': row['path'], 'original_sha256': row['sha256'],
                'format': row['format'], 'authored_by': row['authored_by'], 'provenance': provenance(manifest, row),
                'parser': result['parser'], 'canonical_path': target, 'canonical_sha256': file_hash(stage / target),
                'canonical_chars': len(canonical), 'pages': page_map})
            # Detect a source changing during the extraction operation.
            verify_file(manifest_path.parent, row['path'], row['sha256'])
        identity = {'schema_version': 1, 'snapshot_manifest_sha256': file_hash(manifest_path),
                    'normalization_version': NORMALIZATION, 'page_separator': SEPARATOR,
                    'ingestion_lock_sha256': file_hash(STAGE / 'ingestion-lock.json'), 'documents': documents}
        output = {**identity, 'run_id': fingerprint(identity), 'status': 'needs_review' if review else 'complete',
                  'review_pages': review, 'offset_unit': 'Unicode code point [start,end) in canonical text, not PDF bytes',
                  'limits': {**lock['limits'], 'pdf_timeout_seconds': pdf_timeout_seconds},
                  'limitations': ['No OCR. Blank/image classifications are heuristic; vector-drawn text may look blank.',
                      'PDF reading order/table/column recovery is not guaranteed.',
                      'Limits/timeouts are not a comprehensive memory/resource sandbox.'],
                  'elapsed_ms': (perf_counter() - started) * 1000}
        # Review-only outputs intentionally have NO successful completion manifest.
        write_json(stage / ('review.json' if review else 'manifest.json'), output)
    return output


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--pdf-timeout-seconds', type=float, default=PDF_TIMEOUT)
    args = p.parse_args(argv)
    try:
        result = ingest(args.manifest, args.output_dir, args.pdf_timeout_seconds)
        print(json.dumps({'status': result['status'], 'run_id': result['run_id'], 'review_pages': result['review_pages']}))
        return 3 if result['status'] == 'needs_review' else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return cli_error(exc)


if __name__ == '__main__':
    raise SystemExit(main())
