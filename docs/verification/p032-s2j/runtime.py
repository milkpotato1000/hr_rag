"""S2d real loopback metadata and process measurements; no model dispatch here."""
from pathlib import Path
import json,os,shutil,subprocess,time,urllib.request,urllib.error
from control import *
E=Path(__file__).resolve().parent;ROOT=E.parents[2];LEDGER=E/'ledger.json';BASE='http://127.0.0.1:11434'
BINARY=ROOT/'1. Naive RAG/.runtime/ollama/ollama'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def metadata(endpoint,body=None,actor='supervisor'):
    with transact(LEDGER) as c:n=c.metadata(endpoint,actor)
    req=urllib.request.Request(BASE+endpoint,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(req,timeout=5) as r:raw=r.read(4*1024*1024+1)
        need(len(raw)<=4*1024*1024,'metadata_too_large');data=json.loads(raw)
    except Exception as e:
        with transact(LEDGER) as c:c.s['metadata'][n].update(status='failed',error=type(e).__name__)
        raise
    with transact(LEDGER) as c:c.s['metadata'][n]['status']='received'
    return data
def ps():
    p=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss=,comm='],capture_output=True,text=True,timeout=5)
    need(p.returncode==0,'process_measurement_failed');rows=[]
    for line in p.stdout.splitlines():
        x=line.strip().split(None,3)
        if len(x)==4:rows.append({'pid':int(x[0]),'ppid':int(x[1]),'rss_bytes':int(x[2])*1024,'comm':x[3]})
    return rows
def listener():
    p=subprocess.run(['/usr/sbin/lsof','-nP','-iTCP:11434','-sTCP:LISTEN','-Fp'],capture_output=True,text=True,timeout=5)
    need(p.returncode in (0,1),'listener_measurement_failed');ids={int(s[1:]) for s in p.stdout.splitlines() if s.startswith('p')};need(len(ids)<=1,'multiple_listeners');return next(iter(ids),None)
def sample():
    raw=subprocess.check_output(['/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True,timeout=5).strip();level=int(raw)
    rows=ps();ids={r['pid'] for r in rows if Path(r['comm']).name in ('ollama','llama-server')};ids.add(os.getpid())
    # Include all descendants of server and current supervisor; report only PID/RSS/name.
    changed=True
    while changed:
        old=len(ids);ids.update(r['pid'] for r in rows if r['ppid'] in ids);changed=len(ids)!=old
    observed=[{'pid':r['pid'],'rss_bytes':r['rss_bytes'],'name':Path(r['comm']).name} for r in rows if r['pid'] in ids]
    rss=sum(r['rss_bytes'] for r in observed);monitor_check(level,rss)
    return {'at':time.time(),'pressure':level,'rss_bytes':rss,'processes':observed,'disk_free':shutil.disk_usage(ROOT).free}
def append_sample(s):
    with (E/'resources.jsonl').open('a') as f:f.write(json.dumps(s)+'\n');f.flush()
    write(E/'health.json',s)
def normal_window(seconds=30,limit=60):
    start=time.monotonic();normal=None
    while time.monotonic()-start<limit:
        s=sample();append_sample(s);need(s['disk_free']>=2*1024**3,'disk_floor')
        if s['pressure']==1:
            if normal is None:normal=time.monotonic()
            if time.monotonic()-normal>=seconds:return
        else:normal=None
        time.sleep(1)
    raise Stop('normal_pressure_not_sustained')
def current_models(allow_active=False):
    data=metadata('/api/ps');need(isinstance(data.get('models'),list),'loaded_inventory_invalid')
    for m in data['models']:
        need(allow_active and m.get('name',m.get('model'))=='qwen3:4b' and m.get('digest')==DIGEST,'foreign_or_unexpected_loaded_model')
    return data

def observe_client(proc,*,check,measure=sample,persist=append_sample,loaded=current_models,clock=time.monotonic,sleep=time.sleep):
    started=clock();lastps=None;warning=False;observations=[]
    while proc.poll() is None:
        watchdog(clock()-started);check();s=measure();monitor_check(s['pressure'],s['rss_bytes']);persist(s);warning=warning or s['pressure']==2
        if lastps is None or clock()-lastps>=5:observations.append(loaded(True));lastps=clock()
        sleep(1)
    return warning,observations

def reap_owned_client(proc):
    if proc is None:return True
    if proc.poll() is None:proc.terminate()
    proc.wait(timeout=10)
    return proc.poll() is not None

def verify_parent():
    audit=read(ROOT/'docs/planning/reviews/p032-s2d-halt-audit.json')
    for name,digest in audit['artifacts'].items():
        need(sha(ROOT/name)==digest,'parent_changed')
    parent=read(E.parent/'p032-s2d/ledger.json')
    need(parent['status']=='halted' and len(parent['requests'])==1 and len(parent['metadata'])==30 and time.time()>parent['deadline'],'parent_not_closed')

    for name,digest in read(E/'parent-hashes.json').items():
        need(sha(ROOT/name)==digest,'parent_changed')
    need(read(E.parent/'p032-s2i/server-closed.json')['listener_closed'],'previous_server_not_closed')
