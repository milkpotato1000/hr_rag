"""Explicit adopted continuation; immutable parent, inherited budgets and deadline."""
import copy,time
from pathlib import Path
from live_control import Control
from rag_package.storage import read_json,write_json,digest,require
LIMITS={'embedding_smoke':6,'embedding_full':42,'reranker_smoke':5,'reranker_full':20}
START=1795801676.159772
ADOPTED='b6b57a9e11ac68e55b0bb475343a4df4092b5586'
def verify_parent(parent,identity):
 for name,h in identity.items():require(digest((parent/name).read_bytes())==h,'parent_changed','s1')
def initial(parent,identity):
 verify_parent(parent,identity);state=read_json(parent/'ledger.json')
 require(state['status']=='halted' and state['active'] is None,'parent_not_resumable','s1')
 require(state['started_at']==START and state['reservations']=={'embedding_smoke':3,'embedding_full':21,'reranker_smoke':1,'reranker_full':0} and state['reranker_smoke_pairs']==20 and state['reranker_full_pairs']==0 and state['download_attempts']==['e5','mmini'],'parent_counters_changed','s1')
 for j in state['jobs']:
  if j.get('workers_started'):require(j.get('observation',{}).get('worker_exited') is True and j['observation'].get('resume_safe') is True,'unresolved_previous_worker','s1')
 new=copy.deepcopy(state);new.update(status='ready',parent_identity=identity,execution_id='continuation001',adopted_plan=ADOPTED)
 return new
class Continuation(Control):
 def __init__(self,path,parent,identity,**kwargs):
  verify_parent(parent,identity);super().__init__(path,**kwargs)
  require(self.state.get('adopted_plan')==ADOPTED and self.state['started_at']==START,'continuation_identity','s1')
  self.check()
 def begin(self,label,category,pairs=0):
  if label=='mmini-smoke-gt01':label='continuation001:'+label
  super().begin(label,category,pairs)
 def before_spawn(self,command):
  require(self.current is not None,'unregistered_worker','s1');self.check();c=self.current['category']
  require(c in LIMITS and not self.current['reserved'],'multiple_workers_per_job','s1')
  module='rag_package.embedding_worker' if c.startswith('embedding') else 'rag_package.reranker_worker'
  require(command[-1]==module,'unexpected_worker','s1');n=self.state['reservations']
  require(n[c]<LIMITS[c] and sum(n.values())<73,'worker_budget','s1')
  if c.startswith('reranker'):
   cap=100 if c=='reranker_smoke' else 400;key=c+'_pairs'
   require(self.state[key]+self.current['requested_pairs']<=cap,'pair_budget','s1');self.state[key]+=self.current['requested_pairs']
  n[c]+=1;self.current.update(reserved=True,status='dispatch_intent');self.save()
 def download(self,key):
  require(key in ('bge','bge-reranker'),'repeat_preparation_forbidden','s1');super().download(key)
