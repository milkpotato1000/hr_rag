"""Freeze verified stored retrieval branches; no search, embedding, or model work."""
from pathlib import Path
import math
import shutil
from .storage import require, fingerprint, digest, read_json, write_json, verify, seal, staging
from .documents import load_snapshot, safe_id
from .chunks import make_chunks, ALGORITHM
from .retrieval import load_build, rrf
from .reranker import integer


def copy_artifact(src, dst, kind):
    m = verify(src, kind); dst = Path(dst); dst.mkdir(parents=True)
    for name in [*m['identity']['files'], 'manifest.json']:
        target = dst/name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(src)/name, target)
    require(verify(dst, kind)['fingerprint']==m['fingerprint'], 'copy_changed', 'candidates')


def ranking(result, chunks):
    settings = result['effective_settings']['retrieval']; trace = result.get('retrieval_trace')
    require(isinstance(trace, dict) and set(trace) == {'bm25','dense','embedding_work'}, 'retrieval_trace_required', 'candidates')
    require(type(settings.get('candidate_k')) is int, 'candidate_depth_required', 'candidates')
    known = {c['chunk_id'] for c in chunks}; depth = settings['candidate_k']; method = settings['method']
    for name in ('bm25','dense'):
        rows = trace[name]
        require(isinstance(rows,list) and len(rows)<=depth, 'invalid_branch_trace', 'candidates')
        require(len({r['chunk_id'] for r in rows}) == len(rows), 'invalid_branch_trace','candidates')
        for n,r in enumerate(rows,1):
            require(set(r)=={'chunk_id','score','rank'} and r['chunk_id'] in known and type(r['rank']) is int and r['rank']==n and type(r['score']) in (int,float) and math.isfinite(r['score']), 'invalid_branch_trace','candidates')
            if name=='bm25':require(r['score']>0, 'invalid_branch_trace','candidates')
        require(rows==sorted(rows,key=lambda r:(-r['score'],r['chunk_id'])), 'invalid_branch_order','candidates')
        if (name=='dense' and method=='bm25') or (name=='bm25' and method=='dense'):require(not rows,'unexpected_branch','candidates')
        if name=='dense' and method in ('dense','hybrid'):require(len(rows)==min(depth,len(known)), 'incomplete_branch','candidates')
    rows = rrf(trace['bm25'],trace['dense'],settings['rrf_k']) if method=='hybrid' else trace['dense' if method=='dense' else 'bm25']
    require(rows[:settings['top_k']]==result['candidates'], 'stored_ranking_mismatch','candidates')
    return rows


def freeze(build, result, question_id, n, out):
    integer(n,1,100); require(safe_id(question_id),'invalid_question_id','candidates')
    rm=verify(result,'answer'); r=read_json(Path(result)/'result.json')
    bm,_,chunks=load_build(build,r['effective_settings'])
    for key in ('source_fingerprint','chunk_fingerprint','index_fingerprint'):
        require(r[key]==bm['identity'][key], 'result_build_mismatch','candidates')
    require(r['query_hash']==fingerprint(r['question']) and r['config_hash']==fingerprint(r['effective_settings']), 'result_identity_mismatch','candidates')
    require(rm['identity']['query_hash']==r['query_hash'] and rm['identity']['source_fingerprint']==r['source_fingerprint'], 'result_identity_mismatch','candidates')
    rows=ranking(r,chunks); depth=r['effective_settings']['retrieval']['candidate_k']
    require(depth>=n, 'insufficient_candidate_depth','candidates')
    byid={c['chunk_id']:c for c in chunks}
    data={'schema_version':1,'question_id':question_id,'question':r['question'],'query_hash':r['query_hash'],
          **{k:r[k] for k in ('source_fingerprint','chunk_fingerprint','index_fingerprint','execution_kind')},
          'settings':r['effective_settings'],'parent_result_fingerprint':rm['fingerprint'],'requested_n':n,'actual_n':min(n,len(rows)),
          'candidate_depth':depth,'shortage_reason':'available_retrieval_candidates_below_n' if len(rows)<n else None,
          'original_retrieval_ms':r['latency_ms']['retrieval'],
          'rows':[dict(byid[row['chunk_id']], original_rank=i+1,retrieval_score=row['score'],text_hash=digest(byid[row['chunk_id']]['text'].encode())) for i,row in enumerate(rows[:n])]}
    data['candidate_fingerprint']=fingerprint(data)
    with staging(out) as tmp:
        copy_artifact(Path(build)/'snapshot',tmp/'snapshot','snapshot')
        write_json(tmp/'corpus.json',chunks); write_json(tmp/'coverage.json',read_json(Path(build)/'coverage.json'))
        write_json(tmp/'chunk-identity.json',bm['identity']['chunk_identity'])
        write_json(tmp/'index-identity.json',read_json(Path(build)/'index.json')['identity'])
        write_json(tmp/'parent-result.json',r);write_json(tmp/'parent-manifest.json',rm)
        # Preserve exact parent bytes to verify the stored digest, independent of JSON serialization.
        shutil.copyfile(Path(result)/'result.json',tmp/'parent-result.json')
        write_json(tmp/'candidates.json',data)
        seal(tmp,{'schema_version':1,'kind':'candidates','candidate_fingerprint':data['candidate_fingerprint']})
        load(tmp)
    return data


def load(root):
    root=Path(root);m=verify(root,'candidates');data=read_json(root/'candidates.json')
    require(isinstance(data,dict) and data.get('candidate_fingerprint')==fingerprint({k:v for k,v in data.items() if k!='candidate_fingerprint'})==m['identity']['candidate_fingerprint'], 'stale_candidates','candidates')
    integer(data['requested_n'],1,100);require(safe_id(data['question_id']),'invalid_question_id','candidates')
    sm,docs=load_snapshot(root/'snapshot');chunks=read_json(root/'corpus.json');ci=read_json(root/'chunk-identity.json')
    expected,mapping=make_chunks(docs,sm['fingerprint'],data['settings']['chunking'])
    require(chunks==expected and mapping==read_json(root/'coverage.json'), 'stale_corpus','candidates')
    require(ci=={'source_fingerprint':sm['fingerprint'],'algorithm':ALGORITHM,'config':data['settings']['chunking'],'chunks_hash':fingerprint(chunks),'coverage_hash':fingerprint(mapping)} and fingerprint(ci)==data['chunk_fingerprint'], 'stale_chunk_identity','candidates')
    ii=read_json(root/'index-identity.json');require(fingerprint(ii)==data['index_fingerprint'] and ii['chunk_fingerprint']==data['chunk_fingerprint'],'stale_index_identity','candidates')
    require(sm['fingerprint']==data['source_fingerprint'] and data['query_hash']==fingerprint(data['question']), 'stale_candidate_source','candidates')
    parent=read_json(root/'parent-result.json');pm=read_json(root/'parent-manifest.json')
    require(fingerprint(pm['identity'])==pm['fingerprint']==data['parent_result_fingerprint'] and digest((root/'parent-result.json').read_bytes())==pm['identity']['files']['result.json'], 'stale_parent','candidates')
    require(all(parent[k]==data[k] for k in ('query_hash','question','source_fingerprint','chunk_fingerprint','index_fingerprint','execution_kind')) and parent['effective_settings']==data['settings'], 'stale_parent','candidates')
    rows=ranking(parent,chunks);byid={c['chunk_id']:c for c in chunks};n=data['requested_n']
    expected=[dict(byid[r['chunk_id']], original_rank=i+1,retrieval_score=r['score'],text_hash=digest(byid[r['chunk_id']]['text'].encode())) for i,r in enumerate(rows[:n])]
    require(data['candidate_depth']==parent['effective_settings']['retrieval']['candidate_k'] and data['candidate_depth']>=n and data['actual_n']==len(expected) and data['rows']==expected,'stale_candidate_order','candidates')
    require(data['shortage_reason']==('available_retrieval_candidates_below_n' if len(rows)<n else None),'stale_candidate_shortage','candidates')
    return data,docs,chunks
