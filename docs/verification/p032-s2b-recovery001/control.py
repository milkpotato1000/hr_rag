"""S2b reviewed child control; original clock and explicit cumulative limits."""
from pathlib import Path
import time,shutil,os,copy
from rag_package.storage import read_json,RagError,require
from rag_package.ui_registry import atomic_json

METHODS=('fixed','recursive','structure','semantic')
ORDER=['semantic-boundary']+[label for m in METHODS for label in [m+'-index',*[m+'-gt'+str(n).zfill(2) for n in range(1,11)]]]

def initial():
    return {'schema_version':1,'status':'ready','claimed':False,'started_at':1795804963.61378,'deadline':1795808563.61378,'parent_workers':1,'parent_requested_items':567,'parent_completed_items':None,'cumulative_limits':{'workers':46,'items':2463},
            'reserved_workers':0,'reserved_items':0,'active':None,'operations':[], 'gates':[],
            'limits':{'workers':45,'items':1896,'wall_seconds':3600,'worker_seconds':300,'rss_bytes':4*1024**3,'disk_free_bytes':2*1024**3},
            'automatic_retries':0,'S1_clock_or_budget_reset':False}

class Control:
    def __init__(self,path,*,clock=time.time,persist=atomic_json,disk=None):
        self.path=Path(path);self.marker=self.path.with_suffix('.halted');self.clock=clock;self.persist=persist
        self.disk=disk or (lambda:shutil.disk_usage(self.path.parent).free)
        self.state=read_json(path);self.current=None
        require(not self.marker.exists() and self.state['status']=='ready' and not self.state['claimed'] and self.state['active'] is None and not self.state['operations'] and self.state['reserved_workers']==0 and self.state['reserved_items']==0,'s2b_not_restartable','s2b')
    def save(self):self.persist(self.path,self.state)
    def halt(self,error):
        self.state['status']='halted'
        self.state.setdefault('first_error',{'code':getattr(error,'code',type(error).__name__),'time':self.clock()})
        # Separate durable stop survives a primary journal write failure.
        try:
            with self.marker.open('x') as f:
                f.write(self.state['first_error']['code']+'\n');f.flush();os.fsync(f.fileno())
        except FileExistsError:pass
        except OSError:self.state['halt_marker_write_failed']=True
        try:self.save()
        except BaseException:self.state['journal_write_failed']=True
    def claim(self):
        require(self.state['status']=='ready' and not self.state['claimed'],'s2b_not_restartable','s2b')
        self.state.update(status='running',claimed=True)
        try:self.save()
        except BaseException as e:self.halt(e);raise
    def check(self):
        require(self.state['status']=='running' and self.state['claimed'] and not self.marker.exists(),'s2b_halted','s2b')
        if self.state['deadline'] is not None:require(self.clock()<self.state['deadline'],'s2b_deadline','s2b')
    def begin(self,label,items):
        self.check();require(self.current is None,'s2b_parallel_forbidden','s2b')
        n=len(self.state['operations']);require(n<len(ORDER) and ORDER[n]==label,'s2b_order_mismatch','s2b')
        require(type(items) is int and items>0,'s2b_invalid_items','s2b')
        maximum=567 if label=='semantic-boundary' or label=='semantic-index' else {'fixed-index':201,'recursive-index':257,'structure-index':264}.get(label,1)
        require(items<=maximum,'s2b_stage_items','s2b')
        if label.endswith('-gt03'):require(label[:-5] in self.state['gates'],'s2b_missing_two_question_gate','s2b')
        self.current={'label':label,'requested_items':items,'status':'intent','reserved':False,'workers_started':0,'completed_items':0,'started_at':self.clock()}
        self.state['active']=label;self.state['operations'].append(self.current);self.save()
    def before_spawn(self,command):
        self.check();
        require(self.state['started_at']==1795804963.61378 and self.state['deadline']==1795808563.61378,'recovery_clock_changed','s2b')
        require(self.state['parent_workers']==1 and self.state['parent_requested_items']==567 and self.state['parent_completed_items'] is None,'recovery_parent_changed','s2b')
        require(self.state['parent_workers']+self.state['reserved_workers']+1<=46,'s2b_worker_budget','s2b')
        require(self.current is not None,'s2b_unregistered_worker','s2b')
        require(self.state['parent_requested_items']+self.state['reserved_items']+self.current['requested_items']<=2463,'s2b_item_budget','s2b')
        require(self.current is not None,'s2b_unregistered_worker','s2b')
        require(command[-1]=='rag_package.embedding_worker' and not self.current['reserved'],'s2b_unexpected_worker','s2b')
        require(self.state['reserved_workers']<45,'s2b_worker_budget','s2b')
        require(self.state['reserved_items']+self.current['requested_items']<=1896,'s2b_item_budget','s2b')
        free=self.disk();require(free>=2*1024**3,'s2b_disk_floor','s2b')
        self.check();self.current.update(reserved=True,status='dispatch_intent',disk_free_bytes=free)
        self.state['reserved_workers']+=1;self.state['reserved_items']+=self.current['requested_items'];self.save()
    def after_worker(self,obs):
        require(self.current is not None,'s2b_unregistered_observation','s2b')
        self.current['observation']=copy.deepcopy(obs);self.current['workers_started']=obs.get('workers_started',0)
        self.current['completed_items']=None if obs.get('workers_started') else 0
        self.save()
    def computed(self,items):
        require(self.current is not None and items==self.current['requested_items'],'s2b_item_result_mismatch','s2b')
        self.current['completed_items']=items;self.save()
    def finish(self):
        self.check();op=self.current;require(op is not None and op['reserved'] and op['workers_started']==1,'s2b_missing_worker','s2b')
        obs=op.get('observation',{});require(obs.get('resume_safe') is True and obs.get('worker_exited') is True,'s2b_worker_not_reaped','s2b')
        require(op['completed_items']==op['requested_items'],'s2b_unknown_completion','s2b')
        op.update(status='complete',finished_at=self.clock());self.state['active']=None
        if op['label'].endswith('-gt02'):self.state['gates'].append(op['label'][:-5])
        self.save();self.current=None
    def operation(self,label,items,call,validate,checkpoint):
        try:
            self.begin(label,items)
            result=call();validate(result);checkpoint(result);self.finish();return result
        except BaseException as error:
            if self.current is not None:
                self.current.update(status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',error=getattr(error,'code',type(error).__name__),finished_at=self.clock())
                self.state['active']=None
            self.halt(error);self.current=None;raise
    def protect(self,call):
        """Also latch errors before an operation starts (config/identity parsing)."""
        def wrapped(*args,**kwargs):
            try:self.check();return call(*args,**kwargs)
            except BaseException as error:self.halt(error);raise
        return wrapped
    def complete(self):
        self.check();require(len(self.state['operations'])==45 and all(x['status']=='complete' for x in self.state['operations']),'s2b_incomplete','s2b')
        self.state.update(status='complete',finished_at=self.clock());self.save()
