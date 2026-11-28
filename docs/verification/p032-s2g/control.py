"""Dedicated S2e accounting; not the P013 ledger or runtime. No I/O on import."""
import copy,fcntl,hashlib,json,os,time
from contextlib import contextmanager
from pathlib import Path
DIGEST='359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7'
ORDER=[f'gt{i:02}' for i in range(1,11)]
class Stop(RuntimeError):pass
def need(ok,code):
    if not ok:raise Stop(code)
def read(p):return json.loads(Path(p).read_text())
def write(p,value):
    p=Path(p);tmp=p.with_suffix(p.suffix+'.tmp-'+str(os.getpid()))
    with tmp.open('w') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def initial():return {'status':'prepared','claimed':False,'started_at':None,'deadline':None,'metadata':[],'requests':[], 'gates':[], 'active':None,'server_start_attempts':0,'limits':{'generation':10,'wall_seconds':5400,'http_seconds':480,'watchdog_seconds':510,'metadata':1200,'metadata_timeout':5,'rss_bytes':8*1024**3},'automatic_retries':0}
class State:
    def __init__(self,value,clock=time.time):self.s=copy.deepcopy(value);self.clock=clock
    def check(self):
        need(self.s['status'] in ('prepared','running'),'halted')
        need(self.s['deadline'] is None or self.clock()<self.s['deadline'],'deadline')
    def claim(self):
        self.check();need(not self.s['claimed'],'duplicate_run');self.s.update(claimed=True,status='running')
    def metadata(self,endpoint,actor):
        self.check();need(endpoint in ('/api/tags','/api/show','/api/ps','/api/version'),'metadata_endpoint');need(len(self.s['metadata'])<1200,'metadata_cap')
        self.s['metadata'].append({'endpoint':endpoint,'actor':actor,'at':self.clock(),'status':'attempted'});return len(self.s['metadata'])-1
    def reserve(self,qid,body_hash,expected,health):
        self.check();need(self.s['claimed'],'not_claimed');need(self.s['active'] is None,'parallel');n=len(self.s['requests']);need(n<10,'generation_cap');need(qid==ORDER[n],'order_or_duplicate');need(body_hash==expected,'prompt_identity')
        need(health['pressure']==1 and health['rss_bytes']<=8*1024**3,'resource');need(0<=self.clock()-health['at']<=3,'stale_measurement');need(health['disk_free']>=2*1024**3,'disk')
        need(self.s['gates']==ORDER[:min(n,2)],'smoke_gate')
        if self.s['started_at'] is None:self.s['started_at']=self.clock();self.s['deadline']=self.clock()+5400
        self.s['active']=qid;self.s['requests'].append({'question_id':qid,'reserved_at':self.clock(),'dispatch_attempted':True,'response_received':False,'server_completion':'unknown','status':'dispatch_intent','body_hash':body_hash})
    def response(self,qid):
        need(self.s['active']==qid,'unregistered_response');self.s['requests'][-1]['response_received']=True
    def finish(self,qid,technical,unloaded,normal):
        self.check();need(self.s['active']==qid,'active_identity');need(technical and unloaded and normal,'incomplete_or_failed');self.s['requests'][-1].update(status='complete',server_completion='response_and_unloaded_observed',finished_at=self.clock());self.s['active']=None
    def gate(self,qid,passed):
        self.check();need(passed,'smoke_content_failed');need(qid==ORDER[len(self.s['gates'])] and len(self.s['gates'])<2,'gate_order');need(any(r['question_id']==qid and r['status']=='complete' for r in self.s['requests']),'gate_before_completion');self.s['gates'].append(qid)
    def halt(self,code):
        self.s['status']='halted';self.s.setdefault('first_error',{'code':str(code),'at':self.clock()})
@contextmanager
def transact(path):
    path=Path(path)
    with path.with_suffix('.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX);state=State(read(path))
        try:
            need(not path.with_suffix('.halted').exists(),'halted_marker');yield state;write(path,state.s)
        except BaseException as e:
            state.halt(type(e).__name__+':'+str(e))
            try:path.with_suffix('.halted').touch(exist_ok=True)
            finally:write(path,state.s)
            raise
@contextmanager
def ownership(path):
    with Path(path).open('a') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Stop('another_s2d_owner')
        try:yield
        finally:fcntl.flock(f,fcntl.LOCK_UN)
def monitor_check(pressure,rss):
    need(type(pressure) is int and pressure in (1,2,4),'measurement_failed');need(type(rss) is int and rss>=0,'measurement_failed');need(pressure<4,'critical_pressure');need(rss<=8*1024**3,'rss_limit')
def watchdog(elapsed):need(elapsed<510,'watchdog_timeout')
def identity(tags,version,show):
    need(version.get('version')=='0.40.8','runtime_mismatch')
    matches=[x for x in tags.get('models',[]) if x.get('name')=='qwen3:4b' or x.get('model')=='qwen3:4b']
    need(len(matches)==1 and matches[0].get('digest')==DIGEST,'model_identity_mismatch')
    need(show.get('details',{}).get('quantization_level')=='Q4_K_M','quantization_mismatch')
    need(show.get('model_info',{}).get('general.architecture')=='qwen3','architecture_mismatch')
