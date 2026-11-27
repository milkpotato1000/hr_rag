"""Explicit per-stage P032 S1 runner. No automatic retries or next-model fallback.
Execute using the pinned installed Python from a source-free cwd, PYTHONPATH unset.
"""
from pathlib import Path
import sys,json,os,time,shutil,math
from rag_package import model_catalog,model_preparation,embedding,reranker,retrieval,rag,candidates,reranking
from rag_package.storage import read_json,write_json,digest,fingerprint,require,RagError
from rag_package.model_process import pressure
from rag_package.owned_worker import execution_scope
from live_control import Control,LIMITS
ROOT=Path(__file__).resolve().parents[3];E=Path(__file__).resolve().parent;I=E/'input';OUT=E/'run001';PRIVATE=ROOT/'.rag-runs/p032-s1-live/run001'
MODELS={'e5':('intfloat/multilingual-e5-small','embedding'),'mmini':('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1','reranker'),'bge':('BAAI/bge-m3','embedding'),'bge-reranker':('BAAI/bge-reranker-v2-m3','reranker')}
QUESTIONS=read_json(I/'questions.json');QH=fingerprint(QUESTIONS)
def runtime_profile(key):
 p=read_json(PRIVATE/key/'prepared/profile.json');p['local_path']=str(PRIVATE/key/'prepared/model');p['timeout_seconds']=300
 if MODELS[key][1]=='embedding':embedding.profile(p)
 else:reranker.profile(p)
 dest=OUT/'profiles'/(key+'.json');write_json(dest,p);return dest

def setup():
 require(not OUT.exists(),'existing_run','s1');OUT.mkdir();PRIVATE.mkdir(parents=True,exist_ok=False)
 installed=read_json(E/'installation.json');require(str(Path(sys.executable))==installed['python'],'wrong_python','s1')
 frozen=read_json(I/'frozen-inputs.json')
 for n,h in frozen['files'].items():require(digest((I/n).read_bytes())==h,'changed_inputs','s1')
 plans={}
 for key,(model,role) in MODELS.items():
  model_catalog.plan(model,role,OUT/'plans'/key);plans[key]=model_catalog.load(OUT/'plans'/key)
 write_json(OUT/'manifest.json',{'schema_version':1,'scope':'P032 S1 only','adopted_plan':'3f727c9ce0cd59fdac1337b7bf25acca8bb87c0a','execution_kind':'live_public_hf_cpu','installation':installed,'sdk':embedding.versions(),'source':frozen,'plans':plans,'limits':{'wall_seconds':7200,'worker_seconds':300,'inference_workers':72,'reservations':LIMITS,'reranker_pairs':480,'download_jobs_per_model':1,'upper_retry':0,'rss_bytes':4*1024**3,'required_disk_free_bytes':14511255971},'settings':{'chunk_size':256,'overlap':64,'N':20,'K':5,'context_chars':2000,'RRF':60,'dtype':'float32','device':'cpu','batch':1,'tokens':512},'script_hashes':{n:digest((E/n).read_bytes()) for n in ('live_run.py','live_control.py')},'excluded_calls':{'LLM':0,'Ollama':0,'Drive':0,'evaluator':0,'P013_grant':0}})
 write_json(OUT/'ledger.json',{'status':'ready','active':None,'started_at':None,'jobs':[],'reservations':{k:0 for k in LIMITS},'reranker_smoke_pairs':0,'reranker_full_pairs':0,'download_attempts':[]})
 print(json.dumps({'status':'frozen_not_started','models':list(MODELS),'sdk':embedding.versions()}));return

def validate_manifest():
 m=read_json(OUT/'manifest.json');require(str(Path(sys.executable))==m['installation']['python'],'wrong_python','s1')
 for n,h in m['source']['files'].items():require(digest((I/n).read_bytes())==h,'changed_inputs','s1')
 for n,h in m['script_hashes'].items():require(digest((E/n).read_bytes())==h,'changed_runner','s1')
 require(embedding.versions()==m['sdk'],'changed_sdk','s1')
 for key in MODELS:require(model_catalog.load(OUT/'plans'/key)==m['plans'][key],'changed_plan','s1')
 return m

def prepare(control,key):
 require(key in MODELS,'unknown_model','s1')
 order=list(MODELS);previous=order[:order.index(key)]
 for earlier in previous:require(any(j['label']==earlier+'-smoke-complete' and j['status']=='complete' for j in control.state['jobs']),'previous_smoke_required','s1')
 pre={'pressure':pressure(),'disk_free':shutil.disk_usage(PRIVATE).free,'time':time.time()};write_json(OUT/(key+'-preflight.json'),pre)
 require(pre['disk_free']>=14511255971,'insufficient_overall_disk','s1')
 with control.job(key+'-prepare','preparation') as record:
  control.download(key)
  result=model_preparation.prepare(OUT/'plans'/key,PRIVATE/key/'prepared',execute_download=True,execute_conversion=True)
  record['preparation']=result;write_json(OUT/(key+'-preparation.json'),result)
  require(result['status']=='ready','model_preparation_failed','s1')
  require(result.get('diagnostic_status')=='saved','preparation_record_failed','s1')
 runtime_profile(key)

def smoke(control,key):
 pth=runtime_profile(key);rows=read_json(I/'build-bm25/chunks.json')
 # Same 20 canonical chunks for both embedding models, including birthday/annual evidence.
 smoke_rows=rows[:16]+rows[42:46];assert len(smoke_rows)==20
 if MODELS[key][1]=='embedding':
  p=embedding.read_profile(pth);results=[]
  with control.job(key+'-smoke-doc','embedding_smoke'):
   v,w=embedding.encode(p,[r['text'] for r in smoke_rows],[r['chunk_id'] for r in smoke_rows],'document',execute=True)
   results.append({'kind':'document','ids':[r['chunk_id'] for r in smoke_rows],'vectors':v,'work':w})
  for q in QUESTIONS[:2]:
   with control.job(key+'-smoke-'+q['id'],'embedding_smoke'):
    v,w=embedding.encode(p,[q['question']],[q['id']],'query',execute=True);results.append({'kind':'query','question':q,'vectors':v,'work':w})
 else:
  p=reranker.read_profile(pth);results=[]
  for q in QUESTIONS[:2]:
   with control.job(key+'-smoke-'+q['id'],'reranker_smoke',20):
    scores,w=reranker.score(p,q['question'],smoke_rows);results.append({'question':q,'scores':scores,'work':w})
 write_json(OUT/(key+'-smoke.json'),{'status':'PASS','scope':'20 source chunks and gt01/gt02 only, not full quality','model':MODELS[key][0],'results':results,'source_rows':smoke_rows})
 with control.job(key+'-smoke-complete','checkpoint'):pass

def cfg(key,method):
 c=read_json(I/'bm25.json');c['llm_config']=str(I/'llm-preview-only.json');c['retrieval']['method']=method
 c['embedding_config']=str(OUT/'profiles'/(key+'.json')) if method!='bm25' else None
 dest=OUT/'configs'/((key+'-' if key else '')+method+'.json');write_json(dest,c);return dest

def search(control,key):
 if key!='bm25':require(any(j['label']==key+'-smoke-complete' and j['status']=='complete' for j in control.state['jobs']),'smoke_required','s1')
 methods=['bm25'] if key=='bm25' else ['dense','hybrid'];build=I/'build-bm25' if key=='bm25' else OUT/'builds'/key
 if key!='bm25':
  c=cfg(key,'dense')
  with control.job(key+'-full-doc','embedding_full'):retrieval.build(I/'snapshot-installed',c,build,execute_retrieval=True)
 for method in methods:
  c=cfg('' if key=='bm25' else key,method);label='bm25' if key=='bm25' else key+'-'+method
  for q in QUESTIONS:
   out=OUT/'search'/label/q['id']
   with control.job(label+'-'+q['id'],'checkpoint' if key=='bm25' else 'embedding_full'):
    result=rag.ask(build,c,q['question'],out,execute=False,execute_retrieval=key!='bm25',qrels=I/'qrels.json',question_id=q['id'],questions_hash=QH,facts=I/'facts.json',questions=QUESTIONS)
    require(result['generation_requests']==0 and result['status'] in ('preview','abstained'),'unexpected_generation','s1')
   if key=='e5' and method=='hybrid':candidates.freeze(build,out,q['id'],20,OUT/'candidates'/q['id'])
 print(json.dumps({'status':'search_complete','key':key,'generation_calls':0}))

def rank(control,key):
 require(key in ('none','mmini','bge-reranker'),'unsupported_reranker','s1')
 if key!='none':require(any(j['label']==key+'-smoke-complete' and j['status']=='complete' for j in control.state['jobs']),'smoke_required','s1')
 for q in QUESTIONS:
  cp=OUT/'candidates'/q['id'];can,_,_=candidates.load(cp)
  with control.job(key+'-full-'+q['id'],'checkpoint' if key=='none' else 'reranker_full',0 if key=='none' else len(can['rows'])):
   r=reranking.run(cp,'none' if key=='none' else 'cross-encoder',OUT/'rerank'/key/q['id'],profile=None if key=='none' else OUT/'profiles'/(key+'.json'),top_k=5,context_budget_chars=2000,execute=key!='none',qrels=I/'qrels.json',facts=read_json(I/'facts.json'),questions=QUESTIONS)
   require(r['status']=='complete','rerank_failed','s1');reranking.load(OUT/'rerank'/key/q['id'])
 print(json.dumps({'status':'rerank_complete','key':key,'embedding_calls':0,'generation_calls':0}))

def main():
 action=sys.argv[1];key=sys.argv[2] if len(sys.argv)>2 else None
 if action=='setup':setup();return
 validate_manifest();control=Control(OUT/'ledger.json')
 try:
  with execution_scope(control):
   {'prepare':prepare,'smoke':smoke,'search':search,'rank':rank}[action](control,key)
 except BaseException as e:
  print(json.dumps({'status':'halted','action':action,'key':key,'error':getattr(e,'code',type(e).__name__),'automatic_retry':False}),flush=True);raise
if __name__=='__main__':main()
