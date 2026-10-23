#!/usr/bin/env python3
"""Isolated pypdf process; stdout is one JSON result, diagnostics only on stderr."""
import json
from pathlib import Path
import sys
from pypdf import PdfReader
from document_common import MAX_BYTES, MAX_PAGES, MAX_CHARS, DocumentError, load_ingestion_lock


def extract(path):
    lock = load_ingestion_lock()
    if path.stat().st_size > MAX_BYTES:
        raise DocumentError('file_limit', 'PDF exceeds 20 MiB')
    reader = PdfReader(path, strict=True)
    if reader.is_encrypted:
        raise DocumentError('encrypted_pdf', 'encrypted PDFs are unsupported, including empty-password encryption')
    if not 0 < len(reader.pages) <= MAX_PAGES:
        raise DocumentError('page_limit', 'PDF must have 1..100 pages')
    pages, total = [], 0
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text(extraction_mode='plain') or ''
        total += len(text)
        if total > MAX_CHARS:
            raise DocumentError('text_limit', 'PDF extracted text exceeds one million characters')
        # len(images) inspects image IDs including inline images; it does not decode image pixels.
        image_count = len(page.images)
        status = 'text' if text.strip() else ('ocr_candidate' if image_count else 'blank_candidate')
        pages.append({'page_number': number, 'text': text, 'image_count': image_count, 'classification': status})
    return {'status': 'ok', 'parser': {'name': 'pypdf', 'version': lock['pypdf']['version'], 'mode': 'plain'}, 'pages': pages}


if __name__ == '__main__':
    try:
        value = extract(Path(sys.argv[1]))
    except Exception as exc:
        value = {'status': 'error', 'kind': getattr(exc, 'kind', 'damaged_pdf'), 'message': str(exc)}
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))
    raise SystemExit(0 if value['status'] == 'ok' else 2)
