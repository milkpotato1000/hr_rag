"""P032 S2a: installed CLI/core only, no model/network/index calls.

Run with S1's installed Python -I, from a source-free cwd. This evidence
script never imports the S1 live runners or changes their clocks/ledgers.
"""
from pathlib import Path
import contextlib, io, json, hashlib, os, sys, socket, subprocess, shutil
import statistics, re, copy, importlib.abc

E = Path(__file__).resolve().parent
ROOT = E.parents[2]
S1 = E.parent / 'p032-s1'
OUT = E / 'run001'
PRIVATE = ROOT / '.rag-runs/p032-s2a/run001'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()

def read(path): return json.loads(Path(path).read_text())
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

blocked = []
def deny(name):
    def call(*args, **kwargs):
        blocked.append(name)
        raise AssertionError('S2a forbidden entrypoint: ' + name)
    return call

class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch','transformers','sentence_transformers','huggingface_hub'}:
            deny('model_import:' + fullname)()

sys.meta_path.insert(0, NoModels())
class NoSocket(socket.socket):
    def __init__(self, *args, **kwargs): deny('socket')()
socket.socket = NoSocket
socket.create_connection = deny('network')
subprocess.Popen = deny('subprocess'); os.system = deny('shell')
# No credentials are read, including environment-based keys.
old_getitem = os._Environ.__getitem__
def env_read(self, key):
    if re.search(r'(KEY|TOKEN|SECRET|CREDENTIAL)', str(key), re.I): deny('credential_env')()
    return old_getitem(self, key)
os._Environ.__getitem__ = env_read

import rag_package
from rag_package import chunk_artifact, chunk_policy, embedding, reranker, retrieval, rag, llm
from rag_package import model_preparation, model_catalog, llm_setup
from rag_package.llm import core, transport
from rag_package.documents import load_snapshot
from rag_package.storage import fingerprint, verify
from rag_package.__main__ import main

assert 'site-packages' in str(Path(rag_package.__file__))
assert not Path(rag_package.__file__).is_relative_to(ROOT)
for module, names in [(embedding, ['encode']), (reranker, ['score']),
                      (retrieval, ['build','select']), (rag, ['ask','compare']),
                      (llm, ['invoke']), (core, ['invoke','http_transport']),
                      (transport, ['http_transport']), (chunk_artifact, ['http_transport']),
                      (model_preparation, ['prepare']), (model_catalog, ['plan']),
                      (llm_setup, ['configure'])]:
    for name in names:
        if hasattr(module, name): setattr(module, name, deny(module.__name__ + '.' + name))

def cli(args, target):
    assert not any(x.startswith('--execute') for x in args)
    text = io.StringIO()
    with contextlib.redirect_stdout(text): code = main(args)
    result = {'argv': args, 'exit_code': code, 'stdout': text.getvalue()}
    write(target, result)
    return code, json.loads(text.getvalue())

def hashes(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}

def minimum_cover(cs, spans):
    """Independent exact set-cover over source positions for one AND alternative."""
    target = {(s['document_id'], x) for s in spans for x in range(s['start'], s['end'])}
    positions = {p: i for i, p in enumerate(sorted(target))}
    full = (1 << len(positions)) - 1
    masks = {}
    for n, c in enumerate(cs):
        mask = sum(1 << positions[(c['document_id'], x)] for x in range(c['start'], c['end']) if (c['document_id'], x) in positions)
        if mask: masks.setdefault(mask, n)
    # Discard dominated masks. A superset costs the same one chunk.
    masks = {m: n for m, n in masks.items() if not any(m != v and m | v == v for v in masks)}
    queue = {0: []}; seen = {0}
    while queue:
        nxt = {}
        for mask, indices in queue.items():
            if mask == full: return indices
            for other, n in masks.items():
                union = mask | other
                if union not in seen:
                    seen.add(union); nxt[union] = indices + [n]
        queue = nxt
    return None

def prepare():
    assert not OUT.exists() and not PRIVATE.exists(), 'Never overwrite prior preparation'
    OUT.mkdir(); PRIVATE.mkdir(parents=True)
    baseline = hashes(S1)
    preserved = read(S1 / 'preservation.json')['files']
    assert all(sha(ROOT / p) == h for p, h in preserved.items())
    write(OUT / 'preservation-before.json', {'S1_files': baseline, 'protected_files': preserved})
    installation = read(S1 / 'continuation001/install/installation.json')
    assert sha(installation['wheel']) == installation['wheel_sha256']
    sample = Path(rag_package.__file__).parent / 'resources/sample'
    shutil.copytree(S1 / 'input/snapshot-installed', OUT / 'snapshot')
    sm, docs = load_snapshot(OUT / 'snapshot')
    assert hashes(OUT / 'snapshot') == hashes(S1 / 'input/snapshot-installed')
    bydoc = {d['document_id']: d for d in docs}
    configs = OUT / 'configs'; configs.mkdir()
    e5 = embedding.read_profile(S1 / 'run001/profiles/e5.json')
    # Pure file hashing/config validation, never a model instance or tokenizer.
    embedding.check_files(e5)
    write(PRIVATE / 'e5.json', e5)
    public_e5 = dict(e5, local_path='EXAMPLE_USE_EXISTING_S1_PRIVATE_PREPARED_DIRECTORY')
    write(configs / 'e5-public-reference.json', public_e5)
    local = read(sample / 'llm-chunking.json')
    api = read(sample / 'llm-api.json')
    api['schema_version'] = 2; api['roles']['chunking'] = 'answer'
    write(configs / 'llm-local-example.json', local)
    write(configs / 'llm-api-example.json', api)
    common = {'schema_version': 1, 'size_chars': 256, 'overlap_chars': 64}
    for method in ('fixed','recursive','structure'):
        write(configs / (method + '.json'), dict(common, method=method))
    semantic = dict(common, method='semantic', unit_max_chars=120, minimum_chars=120,
                    distance_threshold=0.35, embedding_config=str(PRIVATE / 'e5.json'))
    write(PRIVATE / 'semantic.json', semantic)
    write(configs / 'semantic-reference.json', dict(semantic, embedding_config='e5-public-reference.json'))
    for kind in ('local','api'):
        write(configs / ('llm-' + kind + '.json'), dict(common, method='llm', unit_max_chars=120,
            window_max_chars=1200, window_max_units=20, max_windows=64, max_prompt_bytes=16384,
            total_timeout_seconds=1800, llm_config='llm-' + kind + '-example.json'))

    rule_stats = {}; artifacts = {}; fact_rows = []; examples = {}
    # No questions/facts have entered chunking calls. All source facts below are post-hoc.
    for method in ('fixed','recursive','structure'):
        dest = OUT / 'chunks' / method
        code, _ = cli(['chunk','--snapshot',str(OUT/'snapshot'),'--config',str(configs/(method+'.json')),'--out',str(dest)], OUT/'cli'/('chunk-'+method+'.json'))
        assert code == 0
        record, ds, cs, maps = chunk_artifact.load(dest)
        code, replay = cli(['chunk-replay','--run',str(dest)], OUT/'cli'/('replay-'+method+'.json'))
        assert code == 0 and replay['model_calls'] == 0
        artifacts[method] = (record, cs, maps)
        lengths = sorted(len(c['text']) for c in cs)
        unique = set(); page_cross = 0; heading_cross = 0; forced = []
        for n, c in enumerate(cs):
            assert c['text'] == bydoc[c['document_id']]['text'][c['start']:c['end']]
            unique.update((c['document_id'], p) for p in range(c['start'], c['end']))
            page_cross += len(c['pages']) > 1
            heading_cross += any(c['start'] < h['start'] < c['end'] for h in chunk_policy.headings(bydoc[c['document_id']]['text']))
        for span in maps['coverage']:
            a, b = span['base_start'], span['base_end']; text = bydoc[span['document_id']]['text']
            if method == 'fixed':
                if b < len(text): forced.append([a,b,'fixed_size_boundary'])
            elif b-a == 192 and b < len(text) and not text[b-1].isspace():
                forced.append([a,b,'no_whitespace_boundary_at_maximum'])
        absent = [(d['document_id'], n) for d in docs for n in range(len(d['text'])) if (d['document_id'], n) not in unique]
        assert all(bydoc[id]['text'][n].isspace() for id,n in absent)
        rule_stats[method] = dict(record['statistics'], median=statistics.median(lengths),
            p95=lengths[(95*len(lengths)+99)//100-1], length_histogram={str(n): lengths.count(n) for n in sorted(set(lengths))},
            emitted_source_coverage_chars=len(unique), source_chars=sum(len(d['text']) for d in docs),
            excluded_whitespace_chars=len(absent), nonwhitespace_missing_chars=0,
            page_crossing_chunks=page_cross, heading_crossing_chunks=heading_cross,
            rule_boundary_splits=forced, rule_boundary_split_count=len(forced),
            forced_units_note='statistics.forced_units is diagnostic unitization, not rule chunk boundary count',
            chunk_fingerprint=record['chunk_fingerprint'], chunks_hash=record['chunks_hash'])
        examples[method] = {'toc_birthday': [dict(index=n, **c) for n,c in enumerate(cs) if c['start'] < 336 and c['end'] > 272]}

    # Freeze independent source-position review after constructing all three boundaries.
    facts = read(S1 / 'input/facts.json'); questions = read(S1 / 'input/questions.json')
    assert facts['source_fingerprint'] == sm['fingerprint']
    for q in facts['questions']:
        for fact in q['required_facts']:
            for method, (_, cs, _) in artifacts.items():
                options = []
                for number, alternative in enumerate(fact['alternatives']):
                    for s in alternative['spans']:
                        assert bydoc[s['document_id']]['text'][s['start']:s['end']] == s['quote']
                    chosen = minimum_cover(cs, alternative['spans'])
                    options.append({'alternative': number, 'minimum_chunks': len(chosen) if chosen is not None else None,
                                    'chunk_indices': chosen, 'spans': alternative['spans']})
                best = min((o for o in options if o['minimum_chunks'] is not None), key=lambda o:o['minimum_chunks'], default=None)
                fact_rows.append({'question_id':q['question_id'],'fact_id':fact['fact_id'],'method':method,
                                  'minimum_chunks':best['minimum_chunks'] if best else None,'chosen':best,'alternatives':options})
    write(OUT/'fact-boundaries.json', {'notice':'Source boundary inspection only; no ranking, retrieval recall, or answer evaluation', 'rows':fact_rows})
    write(OUT/'boundary-examples.json', examples)
    write(OUT/'rule-statistics.json', rule_stats)

    units = chunk_policy.units(docs, sm['fingerprint'], 120)
    batches = chunk_policy.windows(units, 1200, 20)
    unit_doc = {'units':units,'count':len(units),'lengths':[u['end']-u['start'] for u in units],
                'embedding_max_chunks':e5['max_chunks'],'fits_profile':len(units)<=e5['max_chunks'],
                'expected_boundary_embedding_jobs':1,'token_count':None,
                'unit_order_hash':fingerprint([u['id'] for u in units])}
    assert all(u['end']-u['start'] <= 120 for u in units)
    for d in docs:
        ordered = [u for u in units if u['document_id']==d['document_id']]
        assert ordered[0]['start']==0 and ordered[-1]['end']==len(d['text'])
        assert all(a['end']==b['start'] for a,b in zip(ordered,ordered[1:]))
    write(OUT/'units.json',unit_doc)
    previews = {}
    for name, cfg in [('semantic',PRIVATE/'semantic.json'),('llm-local',configs/'llm-local.json'),('llm-api',configs/'llm-api.json')]:
        dest = OUT/'previews'/name
        code,result = cli(['chunk','--snapshot',str(OUT/'snapshot'),'--config',str(cfg),'--out',str(dest)],OUT/'cli'/('preview-'+name+'.json'))
        previews[name] = {'exit_code':code,'result':result,'artifact_exists':dest.exists()}
        if code == 0:
            verify(dest,'chunk-preview'); saved=read(dest/'preview.json')
            assert saved['units']==units and saved['work']['boundary_model_jobs']==0 and saved['work']['dispatches']==0
        else: assert not dest.exists()
    # Diagnostic enumeration does not bypass a failed preflight or create ready chunks.
    # Preserve the original limit; inspect request bodies as data only.
    requests = {}
    for kind,model in [('local',local),('api',api)]:
        records=[]
        for n,batch in enumerate(batches):
            messages=chunk_policy.messages(batch,192); request=llm.preview(model,'chunking',messages)
            size=len(json.dumps(request['body'],ensure_ascii=False,allow_nan=False).encode())
            records.append({'window':n,'unit_ids':[u['id'] for u in batch], 'units':len(batch),
                'start':batch[0]['start'],'end':batch[-1]['end'],'source_chars':sum(len(u['text']) for u in batch),
                'request_bytes':size,'token_count':None,'request':request})
        requests[kind]={'windows':len(records),'max_windows':64,'window_limit_exceeded':len(records)>64,
            'max_request_bytes':max(r['request_bytes'] for r in records),'max_prompt_bytes':16384,
            'prompt_limit_exceeded':any(r['request_bytes']>16384 for r in records),
            'diagnostic_only':previews['llm-'+kind]['exit_code']!=0,'records':records}
    write(OUT/'llm-window-diagnostics.json',requests)
    write(OUT/'preview-outcomes.json',previews)

    old = read(S1/'input/build-bm25/chunks.json'); new = artifacts['fixed'][1]
    assert old == new
    old_manifest=read(S1/'input/build-bm25/manifest.json')
    reuse={'S1_fixed_chunks_equal':True,'count':len(new),'S1_chunks_file_sha256':sha(S1/'input/build-bm25/chunks.json'),
           'new_chunks_file_sha256':sha(OUT/'chunks/fixed/chunks.json'),
           'interval_text_ID_pages_heading_equal':True,
           'S1_chunk_fingerprint':old_manifest['identity']['chunk_fingerprint'],
           'new_frozen_chunk_fingerprint':artifacts['fixed'][0]['chunk_fingerprint'],
           'reason':'Rule chunk identity is unchanged; frozen artifact additionally includes config/unit/work/base metadata. It is a different artifact/version identity.',
           'qrels_reused_or_modified':False,'index_or_query_called':False,
           'reuse_limit':'Source slices and original fixed baseline results can be referenced by hash. No automatic transplantation of index/query/qrels into v3 identities was performed.'}
    write(OUT/'fixed-reuse.json',reuse)
    workload={'status':'estimate_only_not_execution_authorization','settings':{'retrieval':'E5 Hybrid RRF','candidate_N':20,'top_K':5,'context_budget_chars':2000,'questions':10},
        'methods':{m:{'boundary_embedding_jobs':0,'chunk_index_jobs':1,'chunk_index_items':len(cs),'query_jobs':10} for m,(_,cs,_) in artifacts.items()},
        'semantic':{'boundary_embedding_jobs':1,'boundary_embedding_items':len(units),'chunk_index_jobs':1,'chunk_count':None,'chunk_count_upper_bound':len(units),'query_jobs':10},
        'conservative_new_embedding_jobs':45,'if_exact_old_fixed_baseline_is_reference_only_new_jobs':34,
        'reuse_condition':'34 excludes fixed index+10queries as a historical control, not a new v3 run. New schema identity or API reuse still needs subsequent review. No query cache or automatic cross-build reuse assumed.',
        'llm_boundary_requests_if_authorized':len(batches),'llm_status':'example only; actual model and execution contract pending',
        'reranker_jobs':0,'generation_jobs':0,'actual_jobs_this_stage':0}
    write(OUT/'workload.json',workload)
    assert baseline==hashes(S1)
    assert all(sha(ROOT/p)==h for p,h in preserved.items())
    assert not blocked
    summary={'status':'preparation_complete','adopted_plan':'fbcb82a000f31bb9e0d26da38e831caedbfbe698',
        'installed_package':str(Path(rag_package.__file__).parent),'python':sys.executable,'cwd':str(Path.cwd()),'isolated':sys.flags.isolated,
        'wheel_sha256':installation['wheel_sha256'],'source_fingerprint':sm['fingerprint'],
        'snapshot_hashes':hashes(OUT/'snapshot'),'page_heading_mapping_hash':fingerprint([{'pages':d['pages'],'headings':chunk_policy.headings(d['text'])} for d in docs]),
        'facts_hash':sha(S1/'input/facts.json'),'questions_hash':sha(S1/'input/questions.json'),
        'e5_identity':embedding.identity(e5),'sample_profiles':{'local_source':sha(sample/'llm-chunking.json'),'api_source':sha(sample/'llm-api.json'),'api_adaptation':'schema2 and chunking role added; placeholder identity unchanged'},
        'rules':{m:v['chunk_count'] for m,v in rule_stats.items()},'semantic_units':len(units),'llm_windows':len(batches),
        'previews':{k:{'exit_code':v['exit_code'],'status':v['result']['status'],'error':v['result'].get('error')} for k,v in previews.items()},
        'guarded_forbidden_calls':blocked,'model_network_key_index_query_reranker_generation_calls':0,
        'S1_files_preserved':len(baseline),'protected_files_preserved':len(preserved),'S1_budget_and_clock':'unchanged',
        'P032_complete':False,'holds':'P013/P014/P029 C4/grant unchanged'}
    write(OUT/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ('status','rules','semantic_units','llm_windows','previews','S1_files_preserved','protected_files_preserved')},ensure_ascii=False))

if __name__ == '__main__': prepare()
