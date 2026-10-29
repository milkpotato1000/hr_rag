"""Selected P006 source validation and fixed window primitives."""
from pathlib import Path
from document_common import (NORMALIZATION,SEPARATOR,MAX_CHARS,DocumentError,read_json,fingerprint,verify_file,normalize,identifier,nonempty)

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
