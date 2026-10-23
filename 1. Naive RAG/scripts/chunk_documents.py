#!/usr/bin/env python3
"""Fixed CHARACTER windows over canonical documents; 400/80 is a starting point, not an optimum."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
from time import perf_counter
from urllib.parse import quote
from document_common import (NORMALIZATION, SEPARATOR, MAX_CHARS, DocumentError, read_json, write_json,
    fingerprint, file_hash, safe_file, verify_file, normalize, atomic_directory, identifier, nonempty, cli_error)

ALGORITHM = 'fixed-char-v1'


def windows(text, size, overlap):
    if type(size) is not int or size <= 0 or type(overlap) is not int or not 0 <= overlap < size:
        raise DocumentError('invalid_settings', 'require integer size > 0 and 0 <= overlap < size; bool is invalid')
    if not isinstance(text, str) or not text.strip():
        raise DocumentError('empty_text', 'canonical text must contain non-whitespace characters')
    start = 0
    while True:
        end = min(start + size, len(text))
        yield start, end
        if end == len(text):
            return
        start += size - overlap


def load_documents(path):
    path = Path(path)
    manifest = read_json(path)
    if (manifest.get('status') != 'complete' or manifest.get('normalization_version') != NORMALIZATION
            or manifest.get('page_separator') != SEPARATOR or manifest.get('review_pages') != []):
        raise DocumentError('incomplete_documents', 'complete, reviewed canonical documents are required')
    identity_keys = ('schema_version', 'snapshot_manifest_sha256', 'normalization_version', 'page_separator',
                     'ingestion_lock_sha256', 'documents')
    if fingerprint({k: manifest[k] for k in identity_keys}) != manifest.get('run_id'):
        raise DocumentError('manifest_mismatch', 'ingestion manifest identity mismatch')
    rows = manifest.get('documents')
    if not isinstance(rows, list) or not rows:
        raise DocumentError('empty_documents', 'documents must be nonempty')
    loaded, seen = [], set()
    for row in rows:
        did = identifier(row['document_id'])
        if did in seen:
            raise DocumentError('duplicate_document', 'duplicate document_id')
        seen.add(did)
        for field in ('version', 'title'):
            nonempty(row.get(field), field)
        if row.get('synthetic') is not True:
            raise DocumentError('invalid_input', 'synthetic fixture required')
        canonical = verify_file(path.parent, row['canonical_path'], row['canonical_sha256']).read_text(encoding='utf-8')
        if not canonical.strip() or len(canonical) != row['canonical_chars'] or len(canonical) > MAX_CHARS:
            raise DocumentError('empty_text', 'invalid canonical length/content')
        pages = row['pages']
        if not pages:
            raise DocumentError('missing_page', 'page map is empty')
        cursor, parts = 0, []
        for number, page in enumerate(pages, 1):
            if page['page_number'] != number or page['classification'] != 'text':
                raise DocumentError('missing_page', 'page number missing/reordered or page not reviewed')
            raw = verify_file(path.parent, page['raw_text_path'], page['raw_text_sha256']).read_bytes().decode('utf-8')
            text = verify_file(path.parent, page['text_path'], page['text_sha256']).read_bytes().decode('utf-8')
            if parts:
                cursor += len(SEPARATOR)
            if (type(page['start']) is not int or type(page['end']) is not int
                    or (page['start'], page['end']) != (cursor, cursor + len(text))
                    or text != normalize(raw) or canonical[page['start']:page['end']] != text):
                raise DocumentError('invalid_offset', 'page offsets/extracted text disagree with canonical text')
            cursor += len(text)
            parts.append(text)
        if SEPARATOR.join(parts) != canonical or cursor != len(canonical):
            raise DocumentError('missing_page', 'page map does not reconstruct complete canonical text')
        prov = row['provenance']
        if (prov['downloaded_content_sha256'] != row['original_sha256'] or prov['source_mode'] != 'fixture'
                or prov['source_provider'] != 'google_drive' or prov['source_url'] is not None
                or not prov['file_id'].startswith('fixture:') or not prov['snapshot_id'].startswith('fixture:')):
            raise DocumentError('invalid_provenance', 'original source and cache hash disagree')
        loaded.append((row, canonical))
    return manifest, loaded


def page_intersections(pages, start, end):
    result = []
    for page in pages:
        a, b = max(start, page['start']), min(end, page['end'])
        if a < b:
            result.append({'page_number': page['page_number'], 'canonical_start': a, 'canonical_end': b,
                'page_start': a - page['start'], 'page_end': b - page['start'],
                'page_text_sha256': page['text_sha256'], 'raw_text_sha256': page['raw_text_sha256']})
    return result


def union_length(intervals):
    total, right = 0, 0
    for start, end in sorted(intervals):
        total += max(0, end - max(start, right))
        right = max(right, end)
    return total


def chunk(documents_path, output_dir, method='fixed', size_chars=400, overlap_chars=80):
    started = perf_counter()
    if method != 'fixed':
        raise DocumentError('unsupported_method', 'only fixed character chunking is implemented')
    list(windows('x', size_chars, overlap_chars))  # validate settings even before reading documents
    manifest, loaded = load_documents(documents_path)
    settings = {'method': method, 'size_chars': size_chars, 'overlap_chars': overlap_chars}
    chunks, maps, skipped, per_doc = [], [], [], []
    for row, canonical in loaded:
        intervals = []
        for start, end in windows(canonical, size_chars, overlap_chars):
            text = canonical[start:end]
            if not text.strip():
                skipped.append({'document_id': row['document_id'], 'start': start, 'end': end,
                                'reason': 'whitespace_only'})
                continue
            identity = {'document_id': row['document_id'], 'document_version': row['version'],
                'original_sha256': row['original_sha256'], 'canonical_sha256': row['canonical_sha256'],
                'normalization_version': NORMALIZATION, 'algorithm_version': ALGORITHM,
                'settings': settings, 'start': start, 'end': end}
            cid = 'fixed-' + fingerprint(identity)
            spans = page_intersections(row['pages'], start, end)
            if not spans:
                raise DocumentError('invalid_offset', 'nonempty chunk has no source page')
            page_ids = ','.join(str(x['page_number']) for x in spans)
            source = (f"synthetic://hr/source-v2/{quote(row['document_id'], safe='')}/{row['original_sha256']}"
                      f'?pages={page_ids}&chars={start}-{end}')
            chunks.append({'chunk_id': cid, 'document_id': row['document_id'], 'version': row['version'],
                           'title': row['title'], 'text': text, 'source': source, 'synthetic': True})
            maps.append({'chunk_id': cid, **identity, 'provenance': row['provenance'], 'source': source,
                         'pages': spans, 'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()})
            intervals.append((start, end))
        per_doc.append({'document_id': row['document_id'], 'canonical_chars': len(canonical),
                        'chunk_count': len(intervals), 'emitted_chars': sum(b - a for a, b in intervals),
                        'covered_unique_chars': union_length(intervals)})
    if not chunks:
        raise DocumentError('empty_chunks', 'no nonempty chunks were produced')
    lengths = [len(x['text']) for x in chunks]
    total = sum(lengths)
    unique = sum(x['covered_unique_chars'] for x in per_doc)
    source_map = {'schema_version': 1, 'offset_unit': 'Unicode code point [start,end)',
                  'page_separator': SEPARATOR, 'separator_note': 'Page separators belong to canonical text, not either PDF page.',
                  'chunks': maps, 'skipped_windows': skipped}
    with atomic_directory(output_dir) as stage:
        with (stage / 'chunks.jsonl').open('w', encoding='utf-8', newline='\n') as stream:
            for item in chunks:
                stream.write(json.dumps(item, ensure_ascii=False, separators=(',', ':')) + '\n')
        write_json(stage / 'source-map.json', source_map)
        identity = {'schema_version': 1, 'algorithm_version': ALGORITHM, 'settings': settings,
            'ingestion_run_id': manifest['run_id'], 'normalization_version': NORMALIZATION,
            'ingestion_lock_sha256': manifest['ingestion_lock_sha256'],
            'originals': [{'document_id': x['document_id'], 'original_sha256': x['original_sha256'],
                           'canonical_sha256': x['canonical_sha256'], 'parser': x['parser']} for x, _ in loaded],
            'chunks_sha256': file_hash(stage / 'chunks.jsonl'), 'source_map_sha256': file_hash(stage / 'source-map.json')}
        output = {**identity, 'run_id': fingerprint(identity), 'status': 'complete',
            'documents_manifest_sha256': file_hash(documents_path),
            'identity_note': 'Run identity excludes observational timings and the ingestion manifest hash containing them.',
            'statistics': {'chunk_count': len(chunks), 'length_chars': {'min': min(lengths), 'max': max(lengths),
                'mean': statistics.mean(lengths), 'median': statistics.median(lengths), 'values': lengths},
                'emitted_chars': total, 'covered_unique_chars': unique, 'overlap_chars': total - unique,
                'overlap_ratio': (total - unique) / total,
                'overlap_definition': '(sum emitted chunk lengths - union of emitted intervals per document) / sum emitted lengths',
                'skipped_whitespace_windows': len(skipped), 'per_document': per_doc},
            'elapsed_ms': (perf_counter() - started) * 1000}
        write_json(stage / 'manifest.json', output)
    return output


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--documents', type=Path, required=True, help='ingestion manifest.json')
    p.add_argument('--method', default='fixed')
    p.add_argument('--size-chars', type=int, default=400)
    p.add_argument('--overlap-chars', type=int, default=80)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = chunk(args.documents, args.output_dir, args.method, args.size_chars, args.overlap_chars)
        print(json.dumps({'run_id': result['run_id'], 'statistics': result['statistics']}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return cli_error(exc)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
