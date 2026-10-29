"""Pinned local provider and durable cumulative budget. Never downloads models."""
import json,math,socket,time
from pathlib import Path
from urllib import request,error
from document_common import read_json,fingerprint,file_hash
from experiment_common import EXP,RUNTIME,need,ExperimentError,save_state,spec,strict
ENDPOINT='http://127.0.0.1:11434'

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None

def validate_vector(vector,dimension=1024):
    need(isinstance(vector,list) and len(vector)==dimension and all(type(x) in (int,float) and math.isfinite(x) for x in vector),'invalid_vector','Expected finite 1024-dimensional vector')
    need(math.hypot(*vector)>0,'invalid_vector','Zero vector')

class Ledger:
    def __init__(self,path=None):
        self.path=Path(path) if path else RUNTIME/'budget-ledger.json'
        if not self.path.exists():
            probe=read_json(EXP/'probe-results.json')
            state=dict(schema_version=1,spec_sha256=file_hash(EXP/'spec.json'),llm_requests=3,corpus_requests=0,smoke_requests=0,embedding_requests=1,embedding_items=2,
                llm_seconds=sum(x['wall_seconds'] for x in probe['generation']),embedding_seconds=probe['embedding']['wall_seconds'],rankings=0,pending=None,unresolved=False,calls=[],
                readiness=dict(path='experiments/p007/probe-results.json',sha256=file_hash(EXP/'probe-results.json'),generation=3,embedding_requests=1,embedding_items=2))
            save_state(self.path,state)
        self.state=read_json(self.path)
        need(self.state['spec_sha256']==file_hash(EXP/'spec.json'),'budget_changed','Budget spec changed')
    def refresh(self):self.state=read_json(self.path);return self.state
    def before(self,kind,items,payload,purpose):
        s=self.refresh();limits=spec();need(not s['pending'] and not s['unresolved'],'provider_unresolved','Previous call may still be running; automatic restart is blocked')
        if kind=='llm':
            need(purpose in ('corpus','smoke'),'invalid_input','Unknown LLM budget category')
            need(s['llm_requests']<limits['llm']['max_requests_including_smokes'] and s['llm_seconds']<limits['llm']['total_model_wall_seconds'],'budget_exhausted','LLM request/time limit reached')
            need(s[purpose+'_requests']<(210 if purpose=='corpus' else 6),'budget_exhausted','LLM purpose quota reached')
            s['llm_requests']+=1;s[purpose+'_requests']+=1
            remaining=limits['llm']['total_model_wall_seconds']-s['llm_seconds'];timeout=min(90,remaining)
        else:
            need(s['embedding_items']+items<=32000 and s['embedding_seconds']<1800,'budget_exhausted','Embedding item/time limit reached')
            s['embedding_items']+=items;s['embedding_requests']+=1;timeout=min(60,1800-s['embedding_seconds'])
        record=dict(id=len(s['calls'])+1,kind=kind,purpose=purpose,items=items,payload_sha256=fingerprint(payload),started_at=time.time(),status='dispatched')
        s['pending']=record;save_state(self.path,s);return timeout,record
    def after(self,record,elapsed,response=None,exc=None,unresolved=False):
        s=self.refresh();record.update(wall_seconds=elapsed,status='failed' if exc else 'returned',error=str(exc) if exc else None)
        if response:record['usage']={k:response.get(k) for k in ['done','done_reason','prompt_eval_count','eval_count','total_duration','load_duration','prompt_eval_duration','eval_duration']}
        s['llm_seconds' if record['kind']=='llm' else 'embedding_seconds']+=elapsed
        s['calls'].append(record);s['pending']=None;s['unresolved']=unresolved;save_state(self.path,s)
    def ranking(self):
        s=self.refresh();need(s['rankings']<2328,'budget_exhausted','Ranking request cap reached');s['rankings']+=1;save_state(self.path,s)

class Provider:
    def __init__(self,ledger=None):
        self.ledger=ledger or Ledger();self.opener=request.build_opener(request.ProxyHandler({}),NoRedirect());self.checked=False
    def http(self,route,payload=None,timeout=10):
        raw=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode() if payload is not None else None
        req=request.Request(ENDPOINT+route,data=raw,headers={'Content-Type':'application/json'})
        with self.opener.open(req,timeout=timeout) as r:value=strict(r.read().decode())
        need(isinstance(value,dict) and not value.get('error'),'provider','Invalid local provider response');return value
    def verify(self):
        locked=read_json(EXP/'runtime-metadata.json');need(self.http('/api/version').get('version')=='0.40.8','runtime_mismatch','Ollama version differs')
        rows=self.http('/api/tags').get('models',[])
        for key in ['llm','embedding']:
            model=spec()[key];found=[r for r in rows if r.get('name')==model['name']]
            need(len(found)==1 and found[0]['digest']==model['digest_candidate'],'runtime_mismatch','Model digest differs: '+model['name'])
        show=self.http('/api/show',{'model':'qwen3:4b'})
        expected=locked['/api/show:qwen3:4b']
        need(show.get('template')==expected['template'] and show.get('system') in (None,''),'budget_unverified','Model template/system differs')
        for k in ['tokenizer.ggml.model','tokenizer.ggml.pre','tokenizer.ggml.add_bos_token']:
            need(show['model_info'][k]==expected['model_info'][k],'budget_unverified','Tokenizer metadata differs')
        self.checked=True
    def call(self,kind,payload,purpose='corpus'):
        if not self.checked:self.verify()
        timeout,record=self.ledger.before(kind,len(payload.get('input',[])) if kind=='embedding' else 1,payload,purpose)
        started=time.monotonic()
        try:
            value=self.http('/api/chat' if kind=='llm' else '/api/embed',payload,timeout)
        except Exception as exc:
            uncertain=isinstance(exc,(TimeoutError,socket.timeout,error.URLError)) and not isinstance(exc,error.HTTPError)
            self.ledger.after(record,time.monotonic()-started,exc=exc,unresolved=uncertain)
            raise ExperimentError('provider_unresolved' if uncertain else 'provider',str(exc)) from exc
        self.ledger.after(record,time.monotonic()-started,response=value);return value
    def embed(self,texts):
        need(texts and all(isinstance(t,str) and t.strip() for t in texts),'invalid_input','Embedding text must be nonempty')
        if not self.checked:self.verify()
        cache=RUNTIME/'embedding-cache';cache.mkdir(parents=True,exist_ok=True);vectors=[None]*len(texts);missing=[];hits=0
        for i,text in enumerate(texts):
            key=fingerprint(dict(model=spec()['embedding']['digest_candidate'],text=text,text_version='canonical-slice-only-v1'))
            path=cache/(key+'.json')
            if path.exists():
                row=read_json(path);need(row['key']==key and row['vector_hash']==fingerprint(row['vector']),'stale','Embedding cache changed');validate_vector(row['vector']);vectors[i]=row['vector'];hits+=1
            else:missing.append((i,text,key,path))
        for offset in range(0,len(missing),32):
            batch=missing[offset:offset+32];payload={'model':'bge-m3:567m','input':[x[1] for x in batch],'truncate':False}
            for attempt in range(2):
                try:
                    response=self.call('embedding',payload,purpose='embedding');v=response.get('embeddings')
                    need(response.get('model')=='bge-m3:567m' and isinstance(v,list) and len(v)==len(batch),'invalid_vector','Embedding response count/model')
                    for vector in v:validate_vector(vector)
                    break
                except (ValueError,OSError) as exc:
                    if getattr(exc,'kind',None) in ('provider_unresolved','budget_exhausted') or attempt:raise
                    delay=time.monotonic();time.sleep(2);state=self.ledger.refresh();state['embedding_seconds']+=time.monotonic()-delay;save_state(self.ledger.path,state)
            for (i,text,key,path),vector in zip(batch,v):
                vectors[i]=vector;save_state(path,dict(key=key,vector=vector,vector_hash=fingerprint(vector)))
        return vectors,dict(items=len(texts),cache_hits=hits,new_items=len(missing))
