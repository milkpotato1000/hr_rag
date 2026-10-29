"""Versioned BM25/Qdrant indexes; both use canonical slice text only."""
import os,time,json
from pathlib import Path
from document_common import read_json,write_json,file_hash,fingerprint,atomic_directory
from experiment_common import ARTIFACTS,RUNTIME,EXP,need,load_run,source,work_lock,strict,code_hash
from model_runtime import Provider,Ledger
from bm25_core import BM25Index
from dense_core import create_index,DenseIndex


def read_chunks(run):
    path=Path(run);m=load_run(path);row,text,_=source()
    need(m['canonical_sha256']==row['canonical_sha256'] and m['text_version']=='canonical-slice-only-v1','stale','Wrong source/text version')
    rows=[strict(line) for line in (path/'chunks.jsonl').read_text().splitlines()];maps=read_json(path/'source-map.json')['chunks'];byid={r['chunk_id']:r for r in rows}
    need(len(byid)==len(rows)==len(maps),'stale','Chunk count/IDs differ')
    for s in maps:need(byid[s['chunk_id']]['text']==text[s['start']:s['end']],'stale','Not an exact source slice')
    return m,byid,maps

def identity(run,retriever):
    m,chunks,maps=read_chunks(run);need(retriever in ('bm25','dense'),'invalid_config','Unknown retriever')
    lock=read_json(EXP.parents[1]/'runtime-lock.json')
    meta=dict(chunk_run_id=m['run_id'],chunks_sha256=m['outputs']['chunks.jsonl'],canonical_sha256=m['canonical_sha256'],config=m['config'],retriever=retriever,text_version=m['text_version'],model_digest=lock['model']['digest'] if retriever=='dense' else None,parameters={'k1':1.2,'b':.75,'tokenizer':'unicode-word-v1'} if retriever=='bm25' else {'dimension':1024,'distance':'Cosine','qdrant':'1.19.1'})
    return meta,fingerprint(meta),m,chunks,maps,lock

def build_index(run,retriever,provider=None):
    with work_lock():
        meta,fp,m,chunks,maps,lock=identity(run,retriever);dest=RUNTIME/'indexes'/fp;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():
            saved=read_json(dest/'metadata.json');need(saved['identity']==meta,'stale','Index metadata mismatch');return dict(**saved,replayed=True,index_bytes=sum(p.stat().st_size for p in dest.rglob('*') if p.is_file()))
        start=time.monotonic();usage=None
        with atomic_directory(dest) as tmp:
            if retriever=='dense':
                vectors,usage=(provider or Provider()).embed([chunks[cid]['text'] for cid in sorted(chunks)])
                create_index(chunks,m['outputs']['chunks.jsonl'],vectors,lock,tmp/'dense')
            else:BM25Index(chunks)
            out=dict(identity=meta,fingerprint=fp,status='complete',build_ms=(time.monotonic()-start)*1000,embedding=usage)
            write_json(tmp/'metadata.json',out)
        out['index_bytes']=sum(p.stat().st_size for p in dest.rglob('*') if p.is_file());return out

class Searcher:
    def __init__(self,run,retriever):
        self.run=Path(run);self.retriever=retriever
        self.meta,self.fp,self.manifest,self.chunks,self.maps,self.lock=identity(run,retriever)
        path=RUNTIME/'indexes'/self.fp;need((path/'metadata.json').is_file(),'index_not_ready','Build this index first')
        need(read_json(path/'metadata.json')['identity']==self.meta,'stale','Index identity mismatch')
        self.index=DenseIndex(path/'dense',self.chunks,self.manifest['outputs']['chunks.jsonl'],self.lock) if retriever=='dense' else BM25Index(self.chunks)
    def search(self,question,k=20,vector=None,ledger=None):
        need(isinstance(question,str) and question.strip() and len(question)<=2000 and type(k)==int and 1<=k<=20,'invalid_input','Question/top-k outside bounds')
        if ledger:ledger.ranking()
        t=time.monotonic()
        hits=self.index.search(vector,k) if self.retriever=='dense' else self.index.search(question,k)[1]
        return dict(question_hash=fingerprint(question),chunk_run_id=self.manifest['run_id'],index_fingerprint=self.fp,config_id=self.manifest['config']['id'],retriever=self.retriever,results=hits,elapsed_ms=(time.monotonic()-t)*1000)
    def close(self):
        if self.retriever=='dense':self.index.client.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
