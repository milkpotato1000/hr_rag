"""Verified immutable BM25 builds; query-time settings do not change the index."""
from pathlib import Path
import shutil
import time
import struct,math
from . import embedding
from .llm.config import fields, number, read_json as input_json, ValidationError
from .llm import validate_config
from .storage import require,RagError,fingerprint,write_json,read_json,staging,seal,verify,safe_path,digest
from .documents import load_snapshot
from .chunks import make_chunks,ALGORITHM,validate_heading_profile
from .bm25 import BM25Index

PARAMETERS={'tokenizer':'unicode-word-v1','k1':1.2,'b':.75,'text':'canonical_slice_only'}


def config(path):
    path=Path(path)
    try:
        c=input_json(path)
        require(isinstance(c,dict),'invalid_config','config')
        require('reranker' not in c,'unsupported_reranker','config')
        fields(c,{'schema_version','retrieval','llm_config',('chunk_artifact' if c.get('schema_version')==3 else 'chunking')}|({'embedding_config'} if c.get('schema_version') in (2,3) else set()),set(),'config')
        require(type(c['schema_version']) is int and c['schema_version'] in (1,2,3),'invalid_schema','config')
        if c['schema_version']==3:
            from . import chunk_artifact
            require(isinstance(c['chunk_artifact'],str) and c['chunk_artifact'],'chunk_artifact_required','config')
            cp=Path(c['chunk_artifact']);cp=cp if cp.is_absolute() else path.absolute().parent/cp
            c=dict(c,chunk_artifact=str(cp));chunk_artifact.load(cp)
        else:
            fields(c['chunking'],{'method','size_chars','overlap_chars'},{'heading_profile'},'chunking')
            validate_heading_profile(c['chunking'])
        fields(c['retrieval'],{'method','top_k','context_budget_chars'}|({'candidate_k','rrf_k'} if c['schema_version'] in (2,3) else set()),set(),'retrieval')
        if c['schema_version']!=3:require(c['chunking']['method'] in ('fixed','recursive','structure'),'unsupported_chunking','config')
        require(c['retrieval']['method'] in (('bm25',) if c['schema_version']==1 else ('bm25','dense','hybrid')),'unsupported_retrieval','config')
        if c['schema_version'] in (2,3):
            number(c['retrieval']['candidate_k'],c['retrieval']['top_k'],1000,'candidate_k',True);number(c['retrieval']['rrf_k'],1,1000,'rrf_k',True)
            if c['retrieval']['method']=='bm25':require(c['embedding_config'] is None,'unexpected_embedding_config','config')
            else:
                require(isinstance(c['embedding_config'],str) and c['embedding_config'],'embedding_config_required','config')
                ep=Path(c['embedding_config']);ep=ep if ep.is_absolute() else path.parent/ep
                c=dict(c,embedding_config=str(ep.absolute()))
                embedding.read_profile(ep)
        if c['schema_version']!=3:
            number(c['chunking']['size_chars'],100,4000,'size',True)
            number(c['chunking']['overlap_chars'],0,min(400,c['chunking']['size_chars']-1),'overlap',True)
        number(c['retrieval']['top_k'],1,100,'top_k',True);number(c['retrieval']['context_budget_chars'],1,64000,'budget',True)
        require(isinstance(c['llm_config'],str) and c['llm_config'].strip(),'invalid_llm_config','config')
        p=Path(c['llm_config']);p=p if p.is_absolute() else path.parent/p
        llm=validate_config(input_json(p))
        return c,llm
    except ValidationError:raise RagError('invalid_config','config') from None


def effective(c,llm):
    result={'schema_version':c['schema_version'],'retrieval':c['retrieval'],'llm':llm}
    if c['schema_version']==3:
        from . import chunk_artifact
        r,_,_,_=chunk_artifact.load(c['chunk_artifact'])
        result['chunk_artifact']={'fingerprint':r['chunk_fingerprint'],'config':r['config']}
    else:result['chunking']=c['chunking']
    if c['schema_version'] in (2,3):result['embedding']=embedding.identity(embedding.read_profile(c['embedding_config'])) if c['embedding_config'] else None
    return result


def build(snapshot_dir,config_path,out,*,execute_retrieval=False,embedding_backend=None,reuse=None):
    started=time.monotonic();c,llm=config(config_path);sm,docs=load_snapshot(snapshot_dir)
    if c['schema_version']==3:
        from . import chunk_artifact
        r,_,chunks,maps=chunk_artifact.load(c['chunk_artifact']);require(r['source_fingerprint']==sm['fingerprint'],'stale_chunk_source','build')
        ci=frozen_identity(r);chunk_fp=r['chunk_fingerprint']
    else:
        chunks,maps=make_chunks(docs,sm['fingerprint'],c['chunking'])
        ci={'source_fingerprint':sm['fingerprint'],'algorithm':ALGORITHM,'config':c['chunking'],'chunks_hash':fingerprint(chunks),'coverage_hash':fingerprint(maps)}
        chunk_fp=fingerprint(ci)
    ii={'chunk_fingerprint':chunk_fp,'parameters':PARAMETERS};vector_bytes=None;stats={'jobs':0,'documents':0,'queries':0};method=c['retrieval']['method']
    if method!='bm25':
        ep=embedding.read_profile(c['embedding_config']);require(len(chunks)<=ep['max_chunks'],'embedding_chunk_limit','build')
        model_identity=embedding.identity(ep)
        if reuse is not None:
            old,_,old_chunks=load_build(reuse,c);require(old['identity']['chunk_fingerprint']==chunk_fp,'stale_reuse_source','build');old_index=read_json(Path(reuse)/'index.json');vector_bytes=(Path(reuse)/'vectors.f32').read_bytes();ii=old_index['identity'];stats=dict(stats,reused=True)
        else:
            vectors,stats=embedding.encode(ep,[x['text'] for x in chunks],[x['chunk_id'] for x in chunks],'document',execute=execute_retrieval,backend=embedding_backend)
            vector_bytes=b''.join(struct.pack('<'+str(len(v))+'f',*v) for v in vectors)
            ii.update(embedding=model_identity,sdk_versions=stats['sdk_versions'],vectors_hash=digest(vector_bytes),chunk_order_hash=fingerprint([x['chunk_id'] for x in chunks]),execution_kind=stats['execution_kind'])
    index_fp=fingerprint(ii)
    if chunks:BM25Index({x['chunk_id']:x for x in chunks})
    with staging(out) as tmp:
        if c['schema_version']==3:
            from .candidates import copy_artifact
            copy_artifact(c['chunk_artifact'],tmp/'frozen-chunks','chunks')
        (tmp/'snapshot').mkdir()
        for name in list(sm['identity']['files'])+['manifest.json']:
            dest=safe_path(tmp/'snapshot',name);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(safe_path(snapshot_dir,name),dest)
        copied,_=load_snapshot(tmp/'snapshot')
        require(copied['fingerprint']==sm['fingerprint'],'source_changed_during_copy','build')
        write_json(tmp/'chunks.json',chunks);write_json(tmp/'coverage.json',maps)
        if vector_bytes is not None:(tmp/'vectors.f32').write_bytes(vector_bytes)
        write_json(tmp/'embedding-work.json',stats)
        write_json(tmp/'index.json',{'identity':ii,'fingerprint':index_fp,'document_ids':[d['document_id'] for d in docs],'chunk_ids':[x['chunk_id'] for x in chunks]})
        return seal(tmp,{'schema_version':1,'kind':'build','status':'ready','source_fingerprint':sm['fingerprint'],
                         'chunk_identity':ci,'chunk_fingerprint':chunk_fp,'index_fingerprint':index_fp,'retrieval_method':method},round((time.monotonic()-started)*1000,3))


def load_build(root,c):
    root=Path(root);m=verify(root,'build');i=m['identity']
    require(i.get('status')=='ready','build_not_ready','build')
    require((i['retrieval_method']==c['retrieval']['method'] or {i['retrieval_method'],c['retrieval']['method']}<= {'dense','hybrid'}),'stale_build_config','build')
    sm,docs=load_snapshot(root/'snapshot');require(sm['fingerprint']==i['source_fingerprint'],'stale_snapshot','build')
    chunks=read_json(root/'chunks.json');maps=read_json(root/'coverage.json');index=read_json(root/'index.json')
    validate_chunks(root,sm,c,chunks,maps,i['chunk_identity'],i['chunk_fingerprint'])
    ii={'chunk_fingerprint':i['chunk_fingerprint'],'parameters':PARAMETERS}
    if c['retrieval']['method']!='bm25':
        model_identity=c.get('embedding') or embedding.identity(embedding.read_profile(c['embedding_config']))
        ii.update(embedding=model_identity,sdk_versions=index['identity'].get('sdk_versions'),vectors_hash=digest((root/'vectors.f32').read_bytes()),chunk_order_hash=fingerprint([x['chunk_id'] for x in chunks]),execution_kind=index['identity'].get('execution_kind'))
        load_vectors(root,len(chunks),model_identity['catalog']['dimension'])
    require(index=={'identity':ii,'fingerprint':fingerprint(ii),'document_ids':[d['document_id'] for d in docs],'chunk_ids':[x['chunk_id'] for x in chunks]} and i['index_fingerprint']==fingerprint(ii),'stale_index','build')
    return m,docs,chunks


def select(chunks,question,settings,*,run=None,embedding_profile=None,execute_retrieval=False,embedding_backend=None,trace=None):
    require(isinstance(question,str) and question.strip() and len(question)<=2000,'invalid_question','retrieval')
    method=settings.get('method','bm25');k=settings.get('candidate_k',settings['top_k']);bm=[];dense=[];stats={'jobs':0,'documents':0,'queries':0}
    if method in ('bm25','hybrid'):bm=BM25Index({x['chunk_id']:x for x in chunks}).search(question,k)[1] if chunks else []
    bm=[dict(row,rank=n+1) for n,row in enumerate(bm)]
    if method in ('dense','hybrid'):
        require(execute_retrieval,'retrieval_execution_required','embedding')
        index=read_json(Path(run)/'index.json')['identity']
        if embedding_backend is None:
            require(index['execution_kind']=='local_hf' and index['sdk_versions']==embedding.versions(),'stale_embedding_sdk','retrieval')
        else:require(index['execution_kind']=='test_fixture','embedding_backend_mismatch','retrieval')
        vectors=load_vectors(run,len(chunks),embedding.CATALOG[embedding_profile['model_id']]['dimension'])
        q,stats=embedding.encode(embedding_profile,[question],['query'],'query',execute=execute_retrieval,backend=embedding_backend)
        require(stats['sdk_versions']==index['sdk_versions'],'stale_embedding_sdk','retrieval')
        dense=cosine(chunks,vectors,q[0],k)
    rows=(rrf(bm,dense,settings['rrf_k']) if method=='hybrid' else dense if method=='dense' else bm)[:settings['top_k']]
    if trace is not None:trace.update(bm25=bm,dense=dense,embedding_work=stats)
    byid={x['chunk_id']:x for x in chunks};selected=[];excluded=[];used=0
    for row in rows:
        chunk=byid[row['chunk_id']]
        if used+len(chunk['text'])>settings['context_budget_chars']:excluded.append(dict(row,reason='budget'))
        else:selected.append(chunk);used+=len(chunk['text'])
    return rows,selected,excluded


def load_vectors(root,count,dim):
    path=Path(root)/'vectors.f32';require(path.stat().st_size==count*dim*4,'invalid_vector_size','build')
    raw=path.read_bytes();rows=[list(struct.unpack_from('<'+str(dim)+'f',raw,n*dim*4)) for n in range(count)]
    for row in rows:require(all(math.isfinite(x) for x in row) and abs(sum(x*x for x in row)-1)<1e-4,'invalid_stored_vector','build')
    return rows


def cosine(chunks,vectors,query,k):
    require(len(chunks)==len(vectors) and len({x['chunk_id'] for x in chunks})==len(chunks),'vector_count','retrieval')
    rows=[{'chunk_id':c['chunk_id'],'score':sum(a*b for a,b in zip(v,query))} for c,v in zip(chunks,vectors)]
    return [dict(r,rank=n+1) for n,r in enumerate(sorted(rows,key=lambda r:(-r['score'],r['chunk_id']))[:k])]


def rrf(bm,dense,k):
    scores={}
    for name,rows in (('bm25',bm),('dense',dense)):
        require(len({r['chunk_id'] for r in rows})==len(rows),'duplicate_retrieval_id','retrieval')
        for rank,row in enumerate(rows,1):
            value=scores.setdefault(row['chunk_id'],{'chunk_id':row['chunk_id'],'score':0.0,'components':{}});part=1/(k+rank)
            value['score']+=part;value['components'][name]={'rank':rank,'score':row['score'],'contribution':part}
    return [dict(r,rank=n+1) for n,r in enumerate(sorted(scores.values(),key=lambda r:(-r['score'],r['chunk_id'])))]


def dry_run(path):
    c,lc=config(path);p=embedding.read_profile(c['embedding_config']) if c.get('embedding_config') else None
    return {'status':'preview','retrieval':c['retrieval'],'embedding':embedding.identity(p) if p else None,'configured':embedding.configured(p) if p else True,'execution_required':p is not None,'expected_work':{'build':'document embeddings' if p else 'BM25 only','ask':'query embedding even with stored document vectors' if p else 'BM25 only','generation_requests':0}}


def frozen_identity(r):
    return {'source_fingerprint':r['source_fingerprint'],'algorithm':'frozen-chunks-v1','config':r['config'],'chunks_hash':r['chunks_hash'],'coverage_hash':r['coverage_hash'],'frozen_fingerprint':r['chunk_fingerprint']}


def validate_chunks(root,sm,c,chunks,maps,ci,chunk_fp):
    if c['schema_version']==3:
        from . import chunk_artifact
        r,_,expected,mapping=chunk_artifact.load(Path(root)/'frozen-chunks')
        requested=c['chunk_artifact']
        if isinstance(requested,str):
            external,_,_,_=chunk_artifact.load(requested);requested={'fingerprint':external['chunk_fingerprint'],'config':external['config']}
        require(requested=={'fingerprint':r['chunk_fingerprint'],'config':r['config']} and r['source_fingerprint']==sm['fingerprint'] and ci==frozen_identity(r) and chunk_fp==r['chunk_fingerprint'],'stale_chunk_identity','build')
    else:
        _,docs=load_snapshot(Path(root)/'snapshot')
        expected,mapping=make_chunks(docs,sm['fingerprint'],c['chunking'])
        expected_ci={'source_fingerprint':sm['fingerprint'],'algorithm':ALGORITHM,'config':c['chunking'],'chunks_hash':fingerprint(chunks),'coverage_hash':fingerprint(maps)}
        require(ci==expected_ci and fingerprint(ci)==chunk_fp,'stale_chunk_identity','build')
    require(chunks==expected and maps==mapping,'stale_chunks','build')
