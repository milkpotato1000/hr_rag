"""Verified immutable BM25 builds; query-time settings do not change the index."""
from pathlib import Path
import shutil
import time
from .llm.config import fields, number, read_json as input_json, ValidationError
from .llm import validate_config
from .storage import require,RagError,fingerprint,write_json,read_json,staging,seal,verify,safe_path
from .documents import load_snapshot
from .chunks import make_chunks,ALGORITHM
from .bm25 import BM25Index

PARAMETERS={'tokenizer':'unicode-word-v1','k1':1.2,'b':.75,'text':'canonical_slice_only'}


def config(path):
    path=Path(path)
    try:
        c=input_json(path)
        require(isinstance(c,dict),'invalid_config','config')
        require('reranker' not in c,'unsupported_reranker','config')
        fields(c,{'schema_version','chunking','retrieval','llm_config'},set(),'config')
        require(type(c['schema_version']) is int and c['schema_version']==1,'invalid_schema','config')
        fields(c['chunking'],{'method','size_chars','overlap_chars'},set(),'chunking')
        fields(c['retrieval'],{'method','top_k','context_budget_chars'},set(),'retrieval')
        require(c['chunking']['method'] in ('fixed','recursive','structure'),'unsupported_chunking','config')
        require(c['retrieval']['method']=='bm25','unsupported_retrieval','config')
        number(c['chunking']['size_chars'],100,4000,'size',True)
        number(c['chunking']['overlap_chars'],0,min(400,c['chunking']['size_chars']-1),'overlap',True)
        number(c['retrieval']['top_k'],1,100,'top_k',True);number(c['retrieval']['context_budget_chars'],1,64000,'budget',True)
        require(isinstance(c['llm_config'],str) and c['llm_config'].strip(),'invalid_llm_config','config')
        p=Path(c['llm_config']);p=p if p.is_absolute() else path.parent/p
        llm=validate_config(input_json(p))
        return c,llm
    except ValidationError:raise RagError('invalid_config','config') from None


def effective(c,llm):
    return {'schema_version':1,'chunking':c['chunking'],'retrieval':c['retrieval'],'llm':llm}


def build(snapshot_dir,config_path,out):
    started=time.monotonic();c,llm=config(config_path);sm,docs=load_snapshot(snapshot_dir)
    chunks,maps=make_chunks(docs,sm['fingerprint'],c['chunking'])
    ci={'source_fingerprint':sm['fingerprint'],'algorithm':ALGORITHM,'config':c['chunking'],'chunks_hash':fingerprint(chunks),'coverage_hash':fingerprint(maps)}
    chunk_fp=fingerprint(ci);ii={'chunk_fingerprint':chunk_fp,'parameters':PARAMETERS};index_fp=fingerprint(ii)
    if chunks:BM25Index({x['chunk_id']:x for x in chunks})
    with staging(out) as tmp:
        (tmp/'snapshot').mkdir()
        for name in list(sm['identity']['files'])+['manifest.json']:
            dest=safe_path(tmp/'snapshot',name);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(safe_path(snapshot_dir,name),dest)
        copied,_=load_snapshot(tmp/'snapshot')
        require(copied['fingerprint']==sm['fingerprint'],'source_changed_during_copy','build')
        write_json(tmp/'chunks.json',chunks);write_json(tmp/'coverage.json',maps)
        write_json(tmp/'index.json',{'identity':ii,'fingerprint':index_fp,'document_ids':[d['document_id'] for d in docs],'chunk_ids':[x['chunk_id'] for x in chunks]})
        return seal(tmp,{'schema_version':1,'kind':'build','status':'ready','source_fingerprint':sm['fingerprint'],
                         'chunk_identity':ci,'chunk_fingerprint':chunk_fp,'index_fingerprint':index_fp,'retrieval_method':'bm25'},round((time.monotonic()-started)*1000,3))


def load_build(root,c):
    root=Path(root);m=verify(root,'build');i=m['identity']
    require(i.get('status')=='ready','build_not_ready','build')
    require(i['chunk_identity']['config']==c['chunking'] and i['retrieval_method']==c['retrieval']['method'],'stale_build_config','build')
    sm,docs=load_snapshot(root/'snapshot');require(sm['fingerprint']==i['source_fingerprint'],'stale_snapshot','build')
    chunks=read_json(root/'chunks.json');maps=read_json(root/'coverage.json');index=read_json(root/'index.json')
    expected,mapping=make_chunks(docs,sm['fingerprint'],c['chunking'])
    require(chunks==expected and maps==mapping,'stale_chunks','build')
    ci={'source_fingerprint':sm['fingerprint'],'algorithm':ALGORITHM,'config':c['chunking'],'chunks_hash':fingerprint(chunks),'coverage_hash':fingerprint(maps)}
    require(ci==i['chunk_identity'] and fingerprint(ci)==i['chunk_fingerprint'],'stale_chunk_identity','build')
    ii={'chunk_fingerprint':i['chunk_fingerprint'],'parameters':PARAMETERS}
    require(index=={'identity':ii,'fingerprint':fingerprint(ii),'document_ids':[d['document_id'] for d in docs],'chunk_ids':[x['chunk_id'] for x in chunks]} and i['index_fingerprint']==fingerprint(ii),'stale_index','build')
    return m,docs,chunks


def select(chunks,question,settings):
    require(isinstance(question,str) and question.strip() and len(question)<=2000,'invalid_question','retrieval')
    rows=BM25Index({x['chunk_id']:x for x in chunks}).search(question,settings['top_k'])[1] if chunks else []
    byid={x['chunk_id']:x for x in chunks};selected=[];excluded=[];used=0
    for row in rows:
        chunk=byid[row['chunk_id']]
        if used+len(chunk['text'])>settings['context_budget_chars']:excluded.append(dict(row,reason='budget'))
        else:selected.append(chunk);used+=len(chunk['text'])
    return rows,selected,excluded
