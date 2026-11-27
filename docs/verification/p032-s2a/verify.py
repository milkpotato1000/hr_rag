"""Independent interval/counter/identity verification; no inference."""
from pathlib import Path
import runpy, json, itertools, collections, hashlib
E=Path(__file__).resolve().parent
p=runpy.run_path(str(E/'prepare.py'))  # Installs deny guards, does not prepare again.
read,write,sha=p['read'],p['write'],p['sha'];R=E/'run001'
from rag_package import chunk_artifact,chunk_policy
from rag_package.documents import load_snapshot
sm,docs=load_snapshot(R/'snapshot');bydoc={d['document_id']:d for d in docs}
source_points={(d['document_id'],n) for d in docs for n in range(len(d['text']))}
stats=read(R/'rule-statistics.json');facts=read(R/'fact-boundaries.json')['rows'];checked=0
for method in ('fixed','recursive','structure'):
    record,_,chunks,mapping=chunk_artifact.load(R/'chunks'/method)
    points=[{(c['document_id'],n) for n in range(c['start'],c['end'])} for c in chunks]
    assert set().union(*points)==source_points
    assert sum(map(len,points))-len(source_points)==stats[method]['duplicate_chars']
    assert len(chunks)==stats[method]['chunk_count']
    for row in (r for r in facts if r['method']==method):
        minima=[]
        for option in row['alternatives']:
            target={(s['document_id'],n) for s in option['spans'] for n in range(s['start'],s['end'])}
            candidates=[i for i,ps in enumerate(points) if ps&target]
            # Independent exhaustive combinations, not the preparation bit-mask BFS.
            found=None
            for count in range(1,len(candidates)+1):
                if any(target.issubset(set().union(*(points[i] for i in group))) for group in itertools.combinations(candidates,count)):
                    found=count;break
            assert found==option['minimum_chunks']
            assert target.issubset(set().union(*(points[i] for i in option['chunk_indices'])))
            minima.append(found)
        assert min(x for x in minima if x is not None)==row['minimum_chunks'];checked+=1
units=read(R/'units.json')['units'];windows=read(R/'llm-window-diagnostics.json')
for kind,info in windows.items():
    config=read(R/'configs'/('llm-'+kind+'-example.json'))
    profile=config['profiles'][config['roles']['chunking']]
    assert profile['identity']['validation_status']=='example_requires_configuration'
    def identity(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    assert sum(r['units'] for r in info['records'])==len(units)
    assert [id for r in info['records'] for id in r['unit_ids']]==[u['id'] for u in units]
    for row in info['records']:
        assert row['request_bytes']==len(json.dumps(row['request']['body'],ensure_ascii=False,allow_nan=False).encode())
        assert row['units']<=20 and row['source_chars']<=1200 and row['token_count'] is None
        request=row['request']
        assert request['request_fingerprint']==identity({'provider':request['provider'],'url':request['url'],'body':request['body'],'identity':profile['identity']})
        assert request['actual_messages_hash']==identity(request['body']['messages'])
    assert info['windows']==34 and not info['window_limit_exceeded'] and not info['prompt_limit_exceeded']
assert read(R/'fixed-reuse.json')['S1_fixed_chunks_equal']
pres=read(R/'preservation-before.json')
assert p['hashes'](p['S1'])==pres['S1_files']
assert all(sha(p['ROOT']/n)==h for n,h in pres['protected_files'].items())
assert not p['blocked']
# Guard canaries raise before any socket/model/credential/worker operation.
tests=[('socket',lambda:p['socket'].socket()),('worker',lambda:p['subprocess'].Popen(['never'])),
       ('key',lambda:p['os'].environ.get('RAG_API_KEY')),('model_import',lambda:__import__('torch')),
       ('embedding',lambda:p['embedding'].encode(None)),('generation',lambda:p['llm'].invoke(None)),
       ('index',lambda:p['retrieval'].build(None)),('reranker',lambda:p['reranker'].score(None))]
for name,call in tests:
    try:call()
    except AssertionError as e:assert 'S2a forbidden' in str(e)
    else:raise AssertionError(name+' guard failed')
result={'status':'PASS','fact_method_rows_independently_checked':checked,'request_bodies_checked':68,
        'rule_replays':3,'source_unicode_positions':len(source_points),'S1_files_unchanged':len(pres['S1_files']),
        'protected_files_unchanged':len(pres['protected_files']),'guard_canaries_blocked_before_operation':len(tests),
        'actual_model_network_key_index_query_calls':0,'all_preview_tokens':None}
write(E/'verification.json',result);print(json.dumps(result))
