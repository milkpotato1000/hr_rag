"""Versioned source pipeline utilities; no model, qrels, or network dependency."""
import ctypes
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import unicodedata
from contextlib import contextmanager
from time import perf_counter

from evaluate_retrieval import unique_object, reject_constant

STAGE = Path(__file__).resolve().parents[1]
NORMALIZATION = 'nfc-lf-v1'
SEPARATOR = '\n\n'
MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 100
MAX_CHARS = 1_000_000
PDF_TIMEOUT = 30


class DocumentError(ValueError):
    def __init__(self, kind, message):
        self.kind = kind
        super().__init__(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def raw_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def fingerprint(value):
    return hashlib.sha256(raw_json(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise DocumentError('invalid_input', name + ' must be nonempty text')
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', value):
        raise DocumentError('invalid_input', 'invalid document_id')
    return value


def safe_file(root, relative):
    nonempty(relative, 'relative path')
    p = PurePosixPath(relative)
    root = Path(root).resolve()
    if p.is_absolute() or '..' in p.parts or '\\' in relative:
        raise DocumentError('path_escape', 'path must remain inside input root')
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise DocumentError('path_escape', 'input file missing or escapes input root: ' + relative)
    return resolved


def verify_file(root, relative, digest):
    path = safe_file(root, relative)
    if path.stat().st_size > MAX_BYTES:
        raise DocumentError('file_limit', 'input exceeds 20 MiB limit')
    if file_hash(path) != digest:
        raise DocumentError('hash_mismatch', 'input bytes differ from manifest: ' + relative)
    return path


def normalize(text):
    # Preserve whitespace, headings and all text; only newline representation and NFC change.
    return unicodedata.normalize('NFC', text.replace('\r\n', '\n').replace('\r', '\n'))


def new_path(path):
    path = Path(path).absolute()
    if os.path.lexists(path) or not path.parent.is_dir():
        raise DocumentError('output_exists', 'output must be a new directory with an existing parent')
    return path


def rename_exclusive(source, destination):
    """Atomic directory publication, including race-safe refusal to replace an empty directory."""
    lib = ctypes.CDLL(None, use_errno=True)
    a, b = os.fsencode(source), os.fsencode(destination)
    if sys.platform == 'darwin':
        fn = lib.renamex_np
        fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = fn(a, b, 0x4)  # RENAME_EXCL
    elif sys.platform.startswith('linux') and hasattr(lib, 'renameat2'):
        fn = lib.renameat2
        fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = fn(-100, a, -100, b, 1)  # AT_FDCWD, RENAME_NOREPLACE
    else:
        raise DocumentError('unsupported_platform', 'atomic no-replace publication requires macOS or Linux renameat2')
    if result:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


@contextmanager
def atomic_directory(destination):
    destination = new_path(destination)
    with tempfile.TemporaryDirectory(prefix='.document-stage-', dir=destination.parent) as temporary:
        staging = Path(temporary) / 'result'
        staging.mkdir()
        yield staging
        rename_exclusive(staging, destination)


def load_ingestion_lock():
    lock = read_json(STAGE / 'ingestion-lock.json')
    if (importlib.metadata.version('pypdf') != lock['pypdf']['version']
            or file_hash(STAGE / 'ingestion-requirements.lock') != lock['requirements_sha256']
            or lock['normalization_version'] != NORMALIZATION or lock['page_separator'] != SEPARATOR
            or lock['limits'] != {'file_bytes': MAX_BYTES, 'pdf_pages': MAX_PAGES,
                                  'canonical_chars': MAX_CHARS, 'pdf_timeout_seconds': PDF_TIMEOUT}):
        raise DocumentError('dependency_mismatch', 'ingestion runtime or configuration differs from lock')
    return lock


def valid_rows(rows):
    if not isinstance(rows, list) or not rows:
        raise DocumentError('invalid_input', 'documents must be a nonempty list')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise DocumentError('invalid_input', 'document must be an object')
        did = identifier(row.get('document_id'))
        if did in seen:
            raise DocumentError('duplicate_document', 'duplicate document_id: ' + did)
        seen.add(did)
        for field in ('version', 'title', 'authored_by'):
            nonempty(row.get(field), field)
        if row.get('synthetic') is not True or row.get('format') not in ('pdf', 'md', 'txt'):
            raise DocumentError('unsupported_input', 'only explicit synthetic pdf/md/txt inputs are supported')
    return rows


def validate_snapshot(manifest):
    if (manifest.get('source_provider') != 'google_drive' or manifest.get('source_mode') != 'fixture'
            or manifest.get('timestamps_synthetic') is not True):
        raise DocumentError('unsupported_source', 'only explicitly synthetic Drive fixture snapshots are supported')
    for key in ('snapshot_id', 'folder_id'):
        if not nonempty(manifest.get(key), key).startswith('fixture:'):
            raise DocumentError('invalid_provenance', key + ' must be a fixture ID')
    rows = valid_rows(manifest.get('documents'))
    seen = set()
    for row in rows:
        fid = nonempty(row.get('file_id'), 'file_id')
        if not fid.startswith('fixture:') or fid in seen or row.get('source_url') is not None:
            raise DocumentError('invalid_provenance', 'unique fixture file_id and null source_url required')
        seen.add(fid)
        for key in ('name', 'mime_type', 'source_modified_time'):
            nonempty(row.get(key), key)
        if row.get('source_version') is not None:
            nonempty(row['source_version'], 'source_version')
        if row.get('downloaded_content_sha256') != row.get('sha256') or row.get('local_path') != row.get('path'):
            raise DocumentError('invalid_provenance', 'cache path/hash aliases disagree')
    basis = {k: v for k, v in manifest.items() if k != 'snapshot_id'}
    if manifest['snapshot_id'] != 'fixture:' + fingerprint(basis):
        raise DocumentError('invalid_provenance', 'snapshot ID differs from metadata/content fingerprint')
    return rows


def provenance(manifest, row):
    return {**{k: manifest[k] for k in ('source_provider', 'source_mode', 'snapshot_id', 'folder_id', 'timestamps_synthetic')},
            **{k: row[k] for k in ('file_id', 'name', 'mime_type', 'source_modified_time', 'source_version',
                                    'source_url', 'local_path', 'downloaded_content_sha256')}}


def cli_error(exc):
    print(json.dumps({'status': 'error', 'kind': getattr(exc, 'kind', 'execution'),
                      'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
    return 2
