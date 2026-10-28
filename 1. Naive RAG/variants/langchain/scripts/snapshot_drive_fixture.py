#!/usr/bin/env python3
"""Simulate a Drive download snapshot from an explicit local fixture catalog. No network."""
import argparse
from pathlib import Path
import shutil
from document_common import (read_json, write_json, valid_rows, verify_file, atomic_directory,
                             fingerprint, validate_snapshot, cli_error, nonempty, DocumentError)

MIMES = {'pdf': 'application/pdf', 'md': 'text/markdown', 'txt': 'text/plain'}


def snapshot(catalog_path, output_dir):
    catalog_path = Path(catalog_path)
    catalog = read_json(catalog_path)
    if (catalog.get('source_provider') != 'google_drive' or catalog.get('source_mode') != 'fixture'
            or catalog.get('timestamps_synthetic') is not True
            or not nonempty(catalog.get('folder_id'), 'folder_id').startswith('fixture:')):
        raise DocumentError('unsupported_source', 'an explicitly synthetic Drive fixture catalog is required')
    rows = valid_rows(catalog.get('documents'))
    manifest = {k: catalog[k] for k in ('source_provider', 'source_mode', 'timestamps_synthetic', 'folder_id')}
    manifest.update(schema_version=1, adapter_version='drive-fixture-v1',
                    collected_time=None, collection_note='Local fixture copy; no real Drive access or download occurred.', documents=[])
    inputs = []
    for row in rows:
        path = verify_file(catalog_path.parent, row['path'], row['sha256'])
        cache_path = 'cache/' + row['sha256'] + '.' + row['format']
        item = {**row, 'path': cache_path, 'local_path': cache_path, 'mime_type': MIMES[row['format']],
                'downloaded_content_sha256': row['sha256']}
        manifest['documents'].append(item)
        inputs.append(path)
    manifest['snapshot_id'] = 'fixture:' + fingerprint(manifest)
    validate_snapshot(manifest)
    with atomic_directory(output_dir) as stage:
        (stage / 'cache').mkdir()
        for row, source in zip(manifest['documents'], inputs):
            shutil.copyfile(source, stage / row['path'])
            verify_file(stage, row['path'], row['sha256'])
        write_json(stage / 'manifest.json', manifest)
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = snapshot(args.catalog, args.output_dir)
        print(result['snapshot_id'])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return cli_error(exc)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
