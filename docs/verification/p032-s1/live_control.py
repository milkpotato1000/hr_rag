"""S1-only durable, conservative reservations; no resume/reset/retry operation."""
import time,contextlib
from rag_package.storage import read_json,RagError,require
from rag_package.ui_registry import atomic_json
LIMITS={'embedding_smoke':6,'embedding_full':42,'reranker_smoke':4,'reranker_full':20}
class Control:
 def __init__(self,path,*,clock=time.time,persist=atomic_json):
  self.path=path;self.clock=clock;self.persist=persist;self.state=read_json(path);self.current=None
  require(self.state['status']=='ready','run_not_ready','s1')
  require(self.state.get('active') is None,'unresolved_previous_job','s1')
 def save(self):self.persist(self.path,self.state)
 def check(self):
  require(self.state['status']=='ready','run_halted','s1')
  if self.state['started_at'] is not None:require(self.clock()<self.state['started_at']+7200,'s1_deadline','s1')
 def begin(self,label,category,pairs=0):
  self.check();require(self.current is None,'parallel_job_forbidden','s1')
  require(label not in [r['label'] for r in self.state['jobs']],'job_already_attempted','s1')
  self.current={'label':label,'category':category,'requested_pairs':pairs,'status':'intent','reserved':False,'workers_started':0,'completed_pairs':0}
  self.state['active']=label;self.state['jobs'].append(self.current);self.save()
 def before_spawn(self,command):
  require(self.current is not None,'unregistered_worker','s1');self.check();c=self.current['category']
  require(not self.current['reserved'],'multiple_workers_per_job','s1')
  module='rag_package.embedding_worker' if c.startswith('embedding') else 'rag_package.reranker_worker'
  require(command[-1]==module,'unexpected_worker','s1')
  n=self.state['reservations'];require(n[c]<LIMITS[c] and sum(n.values())<72,'worker_budget','s1')
  if c.startswith('reranker'):
   cap=80 if c=='reranker_smoke' else 400;key=c+'_pairs'
   require(self.state[key]+self.current['requested_pairs']<=cap,'pair_budget','s1');self.state[key]+=self.current['requested_pairs']
  n[c]+=1;self.current['reserved']=True;self.current['status']='dispatch_intent';self.save()
 def after_worker(self,obs):
  if self.current is None:return
  self.current['observation']=dict(obs);self.current['workers_started']=obs['workers_started']
  self.current['completed_pairs']=None if obs['workers_started'] else 0
  self.save()
 def start_clock(self):
  if self.state['started_at'] is None:self.state['started_at']=self.clock();self.save()
  self.check()
 @contextlib.contextmanager
 def job(self,label,category,pairs=0):
  self.begin(label,category,pairs)
  try:
   self.start_clock();yield self.current
   self.check();self.current['status']='complete'
   if category.startswith('reranker'):self.current['completed_pairs']=pairs
   obs=self.current.get('observation')
   require(obs is None or obs['resume_safe'],'worker_not_reaped','s1')
  except BaseException as e:
   self.current['status']='interrupted' if isinstance(e,(KeyboardInterrupt,SystemExit)) else 'failed'
   self.current['error']=getattr(e,'code',type(e).__name__);self.state['status']='halted';raise
  finally:
   self.current['finished_at']=self.clock();self.state['active']=None
   try:self.save()
   finally:self.current=None
 def download(self,key):
  self.check();require(key not in self.state['download_attempts'],'download_already_attempted','s1')
  self.state['download_attempts'].append(key);self.save()
