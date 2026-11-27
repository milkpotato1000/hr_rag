"""Explicit S1 follow-up; never modifies parent or repeats successful E5 jobs."""
from pathlib import Path
import sys,json,shutil,time
import live_run as live
from continuation_control import Continuation,initial,ADOPTED,START,verify_parent,LIMITS
from rag_package.storage import read_json,write_json,digest,require
from rag_package.owned_worker import execution_scope
E=Path(__file__).resolve().parent;PARENT=E/'run001';OUT=E/'continuation001';RUN=OUT/'run';PRIVATE=live.ROOT/'.rag-runs/p032-s1-live/continuation001'
ALLOWED={('smoke','mmini'),('rank','mmini'),('prepare','bge'),('smoke','bge'),('search','bge'),('prepare','bge-reranker'),('smoke','bge-reranker'),('rank','bge-reranker')}
SCRIPTS=('continuation_run.py','continuation_control.py','live_control.py','live_run.py')
def setup():
 require(not RUN.exists(),'existing_run','s1');RUN.mkdir();PRIVATE.mkdir(exist_ok=False)
 require(digest((PARENT/'ledger.json').read_bytes())==read_json(E/'final-checks.json')['parent_ledger_sha256'],'parent_changed','s1')
 identity={p.relative_to(PARENT).as_posix():digest(p.read_bytes()) for p in PARENT.rglob('*') if p.is_file()}
 state=initial(PARENT,identity)
 require(time.time()<START+7200,'s1_deadline','s1')
 installed=read_json(OUT/'install/installation.json');require(str(Path(sys.executable))==installed['python'],'wrong_python','s1')
 for name in ('plans','candidates'):shutil.copytree(PARENT/name,RUN/name)
 (RUN/'profiles').mkdir();(RUN/'configs').mkdir()
 for key in ('e5','mmini'):shutil.copyfile(PARENT/'profiles'/(key+'.json'),RUN/'profiles'/(key+'.json'))
 parent=read_json(PARENT/'manifest.json')
 write_json(RUN/'manifest.json',{'execution_id':'continuation001','adopted_plan':ADOPTED,'parent_commit':'90a8318','parent_identity':identity,'parent_started_at':START,'deadline':START+7200,'source':parent['source'],'plans':parent['plans'],'sdk':parent['sdk'],'installation':installed,'script_hashes':{n:digest((E/n).read_bytes()) for n in SCRIPTS},'limits':{'inference_workers':73,'reranker_pairs':500,'reservations':LIMITS,'extra_inference_workers':48,'rss_bytes':4*1024**3,'worker_seconds':300,'upper_retry':0}})
 write_json(RUN/'ledger.json',state)
 print(json.dumps({'status':'frozen_continuation_not_executed','started_at':START,'deadline':START+7200,'inherited':state['reservations']}))
def validate():
 m=read_json(RUN/'manifest.json');require(m['adopted_plan']==ADOPTED,'wrong_adoption','s1');verify_parent(PARENT,m['parent_identity'])
 require(str(Path(sys.executable))==m['installation']['python'],'wrong_python','s1')
 for n,h in m['script_hashes'].items():require(digest((E/n).read_bytes())==h,'changed_runner','s1')
 for n,h in m['source']['files'].items():require(digest((live.I/n).read_bytes())==h,'changed_input','s1')
 require(live.embedding.versions()==m['sdk'],'changed_sdk','s1')
 for key in live.MODELS:require(live.model_catalog.load(RUN/'plans'/key)==m['plans'][key],'changed_plan','s1')
 return m
original_runtime=live.runtime_profile
def runtime_profile(key):
 if key=='mmini':
  dest=RUN/'profiles/mmini.json';require(dest.read_bytes()==(PARENT/'profiles/mmini.json').read_bytes(),'changed_prepared_profile','s1');return dest
 require(key in ('bge','bge-reranker'),'successful_model_replay_forbidden','s1');return original_runtime(key)
def main():
 action=sys.argv[1]
 if action=='setup':setup();return
 key=sys.argv[2];require((action,key) in ALLOWED,'scope_not_allowed','s1');m=validate()
 live.OUT=RUN;live.PRIVATE=PRIVATE;live.runtime_profile=runtime_profile
 c=Continuation(RUN/'ledger.json',PARENT,m['parent_identity'])
 original_score=live.reranker.score
 def observed_score(*args,**kwargs):
  label=c.current['label'];dest=RUN/'score-observations';dest.mkdir(exist_ok=True)
  try:
   result=original_score(*args,**kwargs)
  except BaseException as e:
   write_json(dest/(label.replace(':','-')+'.json'),{'error':getattr(e,'code',type(e).__name__),'work':getattr(e,'work',None)})
   raise
  write_json(dest/(label.replace(':','-')+'.json'),{'scores':result[0],'work':result[1]})
  return result
 live.reranker.score=observed_score
 try:
  with execution_scope(c):{'prepare':live.prepare,'smoke':live.smoke,'search':live.search,'rank':live.rank}[action](c,key)
 except BaseException as e:
  # Unique action fails once; preserve observed work/diffs without model retries.
  write_json(RUN/(action+'-'+key+'-failure.json'),{'error':getattr(e,'code',type(e).__name__),'work':getattr(e,'work',None),'automatic_retry':False})
  raise
if __name__=='__main__':main()
