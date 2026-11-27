"""One active core job; durable idempotency, no automatic retry or restart replay."""
import copy,threading,uuid
from pathlib import Path
from .ui_registry import uid,check_id,exact,atomic_json,contained,bounded
from .storage import RagError,require,fingerprint,write_json,read_json,digest,verify
from .llm.config import number,ValidationError
from .llm.core import configuration_required
from .documents import snapshot,load_snapshot,safe_id
from .retrieval import build
from . import embedding
from .rag import ask,compare
from .connectors.google_drive import pull_memory
from .connectors.drive_config import validate_memory,preview_memory

TERMINAL={'completed','needs_review','failed','interrupted'}

def settings(chunking,retrieval):
    exact(chunking,('method','size_chars','overlap_chars'));exact(retrieval,('method','top_k','context_budget_chars'),('candidate_k','rrf_k'))
    require(chunking['method'] in ('fixed','recursive','structure'),'unsupported_chunking','input');require(retrieval['method'] in ('bm25','dense','hybrid'),'unsupported_retrieval','input')
    try:
        number(chunking['size_chars'],100,4000,'size',True);number(chunking['overlap_chars'],0,min(400,chunking['size_chars']-1),'overlap',True)
        if 'candidate_k' in retrieval or 'rrf_k' in retrieval or retrieval['method']!='bm25':
            number(retrieval.get('candidate_k'),retrieval['top_k'],1000,'candidate_k',True);number(retrieval.get('rrf_k'),1,1000,'rrf_k',True)
        number(retrieval['top_k'],1,100,'top_k',True);number(retrieval['context_budget_chars'],1,64000,'budget',True)
    except (ValidationError,TypeError):raise RagError('invalid_settings','input') from None

def question(text):require(isinstance(text,str) and text.strip() and len(text)<=2000,'invalid_question','input')

class Jobs:
    def __init__(self,registry,allow_model=False,allow_drive=False,*,transport=None,key_resolver=None,drive_transport=None,auth_backend=None,env_resolver=None,allow_retrieval=False,embedding_backend=None,allow_reranking=False,reranker_backend=None,allow_chunking=False):
        self.allow_chunking=allow_chunking
        self.allow_reranking=allow_reranking;self.reranker_backend=reranker_backend
        self.registry=registry;self.allow_model=allow_model;self.allow_drive=allow_drive;self.allow_retrieval=allow_retrieval;self.embedding_backend=embedding_backend
        self.transport=transport;self.key_resolver=key_resolver;self.drive_transport=drive_transport;self.auth_backend=auth_backend;self.env_resolver=env_resolver
        self.fixture=any(x is not None for x in (transport,key_resolver,drive_transport,auth_backend,env_resolver,embedding_backend,reranker_backend));self.lock=threading.RLock();self.active=None;self.records={};self.thread=None
        for p in (registry.root/'jobs').glob('*.json'):
            contained(registry.workspace,p);r=read_json(p);check_id(r['id']);self.records[r['request_id']]=r
            if r['status'] not in TERMINAL:
                r.update(status='interrupted',stage='restart',dispatch_attempted='unknown',error={'code':'process_interrupted','stage':'restart'});self.persist(r)
    def persist(self,r):atomic_json(self.registry.root/'jobs'/(r['id']+'.json'),r)
    def get(self,key):
        check_id(key)
        with self.lock:
            r=next((r for r in self.records.values() if r['id']==key),None);require(r is not None,'unknown_job','jobs');return copy.deepcopy(r)
    def summaries(self):return [copy.deepcopy(r) for r in list(self.records.values())[-50:]][::-1]
    def _llm(self,key,execute):
        c=self.registry.llm(key);p=c['profiles'][c['roles']['generation']]
        require(p['response_mode']=='json_object','json_object_required','config')
        if execute:
            require(self.allow_model,'model_execution_disabled','permission');require(not configuration_required(p),'configuration_required','config')
        return c
    def _embedding(self,v,retrieval):
        enabled=v.get('execute_retrieval',False);require(type(enabled) is bool,'invalid_execute_retrieval','input')
        if retrieval['method']=='bm25':
            require(not v.get('embedding_config_id'),'unexpected_embedding_config','input');return None
        require(self.allow_retrieval and enabled,'retrieval_execution_required','permission')
        p=self.registry.embedding(v.get('embedding_config_id'));require(embedding.configured(p),'embedding_configuration_required','input');return p
    def prepare(self,v):
        kind=v['kind'];r=self.registry;plan={};summary=copy.deepcopy(v)
        if kind in ('chunk','chunk_derive','chunk_build','chunk_compare'):
            from .ui_chunking import prepare
            return prepare(self,v),summary
        if kind in ('candidates','rerank','rerank_compare','rerank_answer'):
            from .ui_reranking import prepare
            return prepare(self,v),summary
        if kind=='snapshot':
            exact(v,('request_id','kind','input_ids'));plan['inputs']=r.freeze_inputs(v['input_ids']);plan['fingerprints']=[x['sha256'] for x in plan['inputs']]
        elif kind in ('drive_preview','drive_pull'):
            exact(v,('request_id','kind','drive_config_id','url'));c=r.drive(v['drive_config_id'],v['url'])
            if kind=='drive_pull':require(self.allow_drive,'drive_download_disabled','permission')
            parsed=validate_memory(c);plan['drive']=c;summary.pop('url');summary['link_identity_hash']=fingerprint({'file_id':parsed['file_id'],'resource_key':parsed['resource_key']});plan['fingerprints']=[fingerprint(c)]
        elif kind=='build':
            exact(v,('request_id','kind','snapshot_id','chunking','retrieval','llm_config_id'),('embedding_config_id','execute_retrieval'));settings(v['chunking'],v['retrieval'])
            p,e,m=r.artifact(v['snapshot_id']);require(e['kind']=='snapshot','wrong_artifact_kind','input');load_snapshot(p)
            plan.update(source=str(p),source_fingerprint=m['fingerprint'],llm=self._llm(v['llm_config_id'],False),chunking=v['chunking'],retrieval=v['retrieval'],embedding=self._embedding(v,v['retrieval']))
        elif kind=='ask':
            exact(v,('request_id','kind','build_id','llm_config_id','question','top_k','context_budget_chars','execute'),('embedding_config_id','execute_retrieval','retrieval'));question(v['question']);require(type(v['execute']) is bool,'invalid_execute','input')
            p,e,m=r.artifact(v['build_id']);require(e['kind']=='build','wrong_artifact_kind','input')
            retrieval=v.get('retrieval',{'method':'bm25','top_k':v['top_k'],'context_budget_chars':v['context_budget_chars']});chunking=m['identity']['chunk_identity']['config'];frozen=m['identity']['chunk_identity']['algorithm']=='frozen-chunks-v1'
            settings({'method':'fixed','size_chars':100,'overlap_chars':0} if frozen else chunking,retrieval)
            plan.update(source=str(p),source_fingerprint=m['fingerprint'],llm=self._llm(v['llm_config_id'],v['execute']),chunking=chunking,retrieval=retrieval,snapshot_id=e['snapshot_id'],embedding=self._embedding(v,retrieval))
            if frozen:plan['chunk_artifact']=str(p/'frozen-chunks')
        elif kind=='compare':
            exact(v,('request_id','kind','snapshot_id','variants','questions','execute'),('execute_retrieval',));require(type(v['execute']) is bool,'invalid_execute','input')
            variants=v['variants'];qs=v['questions'];require(isinstance(variants,list) and 2<=len(variants)<=4 and isinstance(qs,list) and 1<=len(qs)<=20,'comparison_limit','input')
            ids=set()
            for q in qs:
                exact(q,('id','question'));require(safe_id(q['id']) and q['id'] not in ids,'invalid_question_id','input');ids.add(q['id']);question(q['question'])
            ps=[]
            for x in variants:
                exact(x,('label','chunking','retrieval','llm_config_id'),('embedding_config_id',));require(isinstance(x['label'],str) and 1<=len(x['label'])<=100,'invalid_label','input');settings(x['chunking'],x['retrieval'])
                ps.append({'llm':self._llm(x['llm_config_id'],v['execute']),'chunking':x['chunking'],'retrieval':x['retrieval'],'embedding':self._embedding(dict(x,execute_retrieval=v.get('execute_retrieval',False)),x['retrieval'])})
            p,e,m=r.artifact(v['snapshot_id']);require(e['kind']=='snapshot','wrong_artifact_kind','input');load_snapshot(p);plan.update(source=str(p),source_fingerprint=m['fingerprint'],variants=ps)
        else:raise RagError('unsupported_job','input')
        return plan,summary
    def submit(self,value):
        require(isinstance(value,dict) and 'request_id' in value and 'kind' in value,'invalid_job','input');v=copy.deepcopy(value)
        try:
            rid=str(uuid.UUID(v['request_id']));require(rid==v['request_id'],'invalid_request_id','input')
        except (ValueError,TypeError,AttributeError):raise RagError('invalid_request_id','input') from None
        if v['kind'] in ('ask','compare'):v.setdefault('execute',False)
        h=fingerprint(v)
        with self.lock:
            if rid in self.records:
                prior=self.records[rid];require(prior['payload_hash']==h,'idempotency_conflict','jobs');return copy.deepcopy(prior),False
            require(self.active is None,'busy','jobs');plan,summary=self.prepare(v)
            key=uid();r={'id':key,'request_id':rid,'payload_hash':h,'input_fingerprint':fingerprint(plan),'kind':v['kind'],'status':'queued','stage':'accepted','request':summary,'artifact_ids':[],'error':None,'dispatch_attempted':False,'execution_kind':'test_fixture' if self.fixture else 'live' if v.get('execute') or v['kind']=='drive_pull' else 'preview'}
            self.persist(r);self.records[rid]=r;self.active=key
            self.thread=threading.Thread(target=self.run,args=(r,v,plan),daemon=True);self.thread.start();return copy.deepcopy(r),True
    def _config(self,work,plan,name='settings'):
        p=work/name;p.mkdir();write_json(p/'llm.json',plan['llm']);c={'schema_version':1,'chunking':plan['chunking'],'retrieval':plan['retrieval'],'llm_config':'llm.json'}
        if 'candidate_k' in plan['retrieval']:
            c.update(schema_version=2,embedding_config='embedding.json' if plan.get('embedding') else None)
            if plan.get('embedding'):write_json(p/'embedding.json',plan['embedding'])
        if plan.get('chunk_artifact'):
            c.pop('chunking');c.update(schema_version=3,chunk_artifact=plan['chunk_artifact'],embedding_config='embedding.json' if plan.get('embedding') else None)
        write_json(p/'rag.json',c);return p/'rag.json'
    def run(self,r,v,plan):
        registry=self.registry;work=registry.root/'artifacts'/r['id'];kind=v['kind'];ids=[]
        try:
            r.update(status='running',stage=kind,dispatch_attempted='unknown' if v.get('execute') or kind=='drive_pull' else False);self.persist(r);work.mkdir()
            if 'source' in plan:
                m=verify(plan['source'],'build' if kind=='ask' else 'snapshot');require(m['fingerprint']==plan['source_fingerprint'],'stale_artifact','jobs')
            if kind in ('chunk','chunk_derive','chunk_build','chunk_compare'):
                from .ui_chunking import execute
                ids,state,result=execute(self,v,plan,work);r['dispatch_attempted']=result.get('dispatch_attempted',False);r['error']=result.get('error')
            elif kind in ('candidates','rerank','rerank_compare','rerank_answer'):
                from .ui_reranking import execute
                ids,state,result=execute(self,v,plan,work)
                r['dispatch_attempted']=result.get('dispatch_attempted',False);r['error']=result.get('error')
            elif kind=='snapshot':
                docs=[];src=work/'input';src.mkdir()
                for d in plan['inputs']:
                    path=contained(registry.workspace,d['path']);raw=bounded(path,20*1024*1024);require(digest(raw)==d['sha256'],'stale_source','snapshot')
                    target=src/(d['document_id']+'.'+d['format']);target.write_bytes(raw)
                    docs.append({k:d[k] for k in ('document_id','title','format','synthetic')}|{'path':str(target)})
                write_json(src/'sources.json',{'schema_version':1,'documents':docs});m=snapshot(src/'sources.json',work/'result');ids=[registry.add_artifact(work/'result','snapshot')];state='completed' if m['identity']['status']=='ready' else 'needs_review';r['dispatch_attempted']=False
            elif kind=='drive_preview':
                r['result']=preview_memory(plan['drive']);state='completed';r['dispatch_attempted']=False
            elif kind=='drive_pull':
                result=pull_memory(plan['drive'],work/'result',execute=True,transport=self.drive_transport,auth_backend=self.auth_backend,env_resolver=self.env_resolver)
                r['dispatch_attempted']=result['requests']>0;ids=[registry.add_artifact(work/'result/snapshot','snapshot')];state='completed' if result['status']=='ready' else 'needs_review'
            elif kind=='build':
                path=self._config(work,plan);m=build(plan['source'],path,work/'result',execute_retrieval=v.get('execute_retrieval',False),embedding_backend=self.embedding_backend);ids=[registry.add_artifact(work/'result','build',snapshot_id=v['snapshot_id'])];state='completed';r['dispatch_attempted']=False
            elif kind=='ask':
                path=self._config(work,plan);result=ask(plan['source'],path,v['question'],work/'result',execute=v['execute'],transport=self.transport,key_resolver=self.key_resolver,execute_retrieval=v.get('execute_retrieval',False),embedding_backend=self.embedding_backend)
                r['dispatch_attempted']=result['dispatch_attempted'];ids=[registry.add_artifact(work/'result','answer',snapshot_id=plan['snapshot_id'],build_id=v['build_id'])];state='failed' if result['status']=='failed' else 'completed';r['error']=result['error']
            else:
                paths=[self._config(work,p,'settings-'+str(n)) for n,p in enumerate(plan['variants'])];write_json(work/'questions.json',v['questions'])
                result=compare(plan['source'],paths,work/'questions.json',work/'result',execute=v['execute'],transport=self.transport,key_resolver=self.key_resolver,execute_retrieval=v.get('execute_retrieval',False),embedding_backend=self.embedding_backend)
                r['dispatch_attempted']=any(x['dispatch_attempted'] for x in result['rows']);children={}
                for n in range(len(paths)):
                    b=work/'result'/('config-'+str(n+1))/'build'
                    if b.exists():children['config-'+str(n+1)]=registry.add_artifact(b,'build',snapshot_id=v['snapshot_id'])
                rows={}
                for row in result['rows']:
                    if 'result_path' in row:
                        p=work/'result'/row['result_path'];rows[row['config_id']+'/'+row['question_id']]=registry.add_artifact(p.parent,'answer',snapshot_id=v['snapshot_id'],build_id=children[row['config_id']])
                ids=[registry.add_artifact(work/'result','comparison',snapshot_id=v['snapshot_id'],build_ids=children,answer_ids=rows,labels=[x['label'] for x in v['variants']])];state='completed'
            with self.lock:
                r.update(status=state,stage='finished',artifact_ids=ids);self.persist(r);self.active=None
        except Exception as e:
            with self.lock:
                r.update(status='failed',stage=getattr(e,'stage','publish'),error={'code':e.code if isinstance(e,(RagError,ValidationError)) else 'job_failed','stage':getattr(e,'stage','publish')},artifact_ids=ids,dispatch_attempted=getattr(e,'dispatch_attempted',r['dispatch_attempted']))
                try:self.persist(r)
                except OSError:r['error']={'code':'job_state_write_failed','stage':'publish'}
                self.active=None
        finally:
            with self.lock:
                if self.active==r['id']:self.active=None
