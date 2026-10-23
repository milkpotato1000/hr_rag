"""Independent artifact audit: original facts, byte preservation and reverse source tracing."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / '1. Naive RAG'
ROOT = STAGE / 'data/source-v2'
sys.path.insert(0, str(STAGE / 'scripts'))
import chunk_documents as pipeline
import document_common as common
import prepare_source_evaluation as evaluation

OUT = Path(__file__).resolve().parent
compact = lambda s: ''.join(s.split())
manifest, loaded = pipeline.load_documents(ROOT / 'extracted/manifest.json')
documents = {x['document_id']: (x, text) for x, text in loaded}
legacy = [json.loads(x) for x in (STAGE / 'data/synthetic/chunks.jsonl').read_text().splitlines()]
policy = []
for row in legacy:
    key = row['document_id'].replace('fictional-', 'hr-v2-')
    original = row['text'].removeprefix('[가상 HR 규정: 실제 회사 정책이 아님] ')
    assert compact(original) in compact(documents[key][1]), row['chunk_id']
    policy.append({'legacy_chunk_id_for_review_only': row['chunk_id'], 'new_document_id': key,
                   'policy_text': original, 'whitespace_insensitive_full_policy_match': True})
# Original source/cache bytes are independently checked against catalog and snapshot.
catalog = common.read_json(ROOT / 'drive-fixture-catalog.json')
snapshot = common.read_json(ROOT / 'snapshot/manifest.json')
for author, cache in zip(catalog['documents'], snapshot['documents']):
    assert (ROOT / author['path']).read_bytes() == (ROOT / 'snapshot' / cache['path']).read_bytes()
    assert common.file_hash(ROOT / author['path']) == cache['sha256'] == cache['downloaded_content_sha256']
common.validate_snapshot(snapshot)
chunk_rows = [json.loads(x) for x in (ROOT / 'fixed-400-80/chunks.jsonl').read_text().splitlines()]
maps = common.read_json(ROOT / 'fixed-400-80/source-map.json')['chunks']
assert len(chunk_rows) == len(maps) == 20
cross_page = []
for chunk, entry in zip(chunk_rows, maps):
    row, text = documents[entry['document_id']]
    a, b = entry['start'], entry['end']
    assert chunk['chunk_id'] == entry['chunk_id']
    assert chunk['text'] == text[a:b]
    assert hashlib.sha256(chunk['text'].encode()).hexdigest() == entry['text_sha256']
    assert entry['original_sha256'] == row['provenance']['downloaded_content_sha256']
    assert entry['provenance'] == row['provenance']
    assert len(chunk['text']) <= 400
    for span in entry['pages']:
        page = row['pages'][span['page_number'] - 1]
        extracted = (ROOT / 'extracted' / page['text_path']).read_text()
        assert extracted[span['page_start']:span['page_end']] == text[span['canonical_start']:span['canonical_end']]
    if len(entry['pages']) > 1:
        cross_page.append({'chunk_id': chunk['chunk_id'], 'document_id': entry['document_id'], 'start': a, 'end': b,
                           'pages': [x['page_number'] for x in entry['pages']]})
assert cross_page
source_eval = common.read_json(ROOT / 'evaluation/source-evaluation.json')
evaluation.validate_evaluation(source_eval, loaded)
# Find facts needing more than one complete chunk. This is an artifact illustration, not retrieval evaluation.
fragmented = []
for fact in source_eval['facts']:
    spans = fact['required_spans']
    single = any(all(m['document_id'] == s['document_id'] and m['start'] <= s['start'] and m['end'] >= s['end'] for s in spans) for m in maps)
    if not single:
        fragmented.append({'fact_id': fact['fact_id'], 'meaning': fact['meaning'],
                           'spans': [{'document_id': s['document_id'], 'start': s['start'], 'end': s['end']} for s in spans]})
# P001-P005 records, legacy data/locks/core and UI preserved relative to pre-P006 dev.
baseline = '8d150f44251919f9326cb22778d0b8bcae72dae7'
paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline], cwd=REPO, text=True).splitlines()
protected = [p for p in paths if p.startswith(('docs/verification/p001/', 'docs/verification/p002/', 'docs/verification/p003/',
    'docs/verification/p004/', 'docs/verification/p005/', '1. Naive RAG/data/synthetic/', '1. Naive RAG/web/'))
    or p in ['1. Naive RAG/runtime-lock.json','1. Naive RAG/generation-lock.json','1. Naive RAG/requirements.lock',
             '1. Naive RAG/scripts/rag.py','1. Naive RAG/scripts/serve.py']
    or p in [f'docs/planning/plans/P00{i}.md' for i in range(1,6)]]
for path in protected:
    assert (REPO / path).read_bytes() == subprocess.check_output(['git', 'show', baseline + ':' + path], cwd=REPO), path
legacy_index = common.read_json(STAGE / '.runtime/index-v1/index-manifest.json')
assert legacy_index['corpus_sha256'] == common.file_hash(STAGE / 'data/synthetic/chunks.jsonl')
report = {'status': 'PASS', 'policy_comparisons': policy, 'source_documents': len(loaded), 'pages': sum(len(x['pages']) for x, _ in loaded),
    'chunk_count': len(chunk_rows), 'cross_page_chunks': cross_page, 'facts_without_one_covering_chunk': fragmented,
    'preservation_baseline': baseline, 'byte_preserved_paths': protected, 'legacy_index_manifest': legacy_index,
    'notes': ['Whitespace-insensitive policy matching is an audit, not a semantic answer quality metric.',
              'Original footer/page-number text retained; normalization does not silently remove content.',
              'All source spans use Unicode code points, half-open intervals in canonical text.']}
common.write_json(OUT / '04-source-audit.json', report)
print('PASS:', len(protected), 'existing files preserved;',len(cross_page),'cross-page chunks;',len(fragmented),'multi-chunk facts')
