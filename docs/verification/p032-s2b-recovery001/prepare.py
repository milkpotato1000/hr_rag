"""Exactly one isolated, hash-locked install; no model operations or retries."""
from pathlib import Path
import hashlib,json,subprocess,time,os,shutil,sys
E=Path(__file__).resolve().parent;ROOT=E.parents[2];P=E.parent/'p032-s2b';BASE=ROOT/'.rag-runs/p032-s2b-recovery001';ENV=BASE/'env'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def hashes(root):return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()}
def write(name,x):(E/name).write_text(json.dumps(x,indent=2)+'\n')
assert not BASE.exists(),'one environment only'
start=time.time();deadline=min(start+900,1795808563.61378)
assert start<deadline and shutil.disk_usage(ROOT).free>=8*1024**3
old=json.loads((E.parent/'p032-s1/continuation001/install/installation.json').read_text());oldenv=Path(old['python']).parents[1]
write('preservation.json',{'parent_commit':'4576841c4a2c56b37430cb39f230536c1c2858b2','parent_files':hashes(P),'old_environment':str(oldenv),'old_environment_files':hashes(oldenv),'old_environment_symlinks':{str(p.relative_to(oldenv)):os.readlink(p) for p in oldenv.rglob('*') if p.is_symlink()}})
assert sha(old['wheel'])==old['wheel_sha256']=='9342add625a9ed633dffb2fccb3bad27379e8cddaf9a06836ea5a224fe9f280a'
lock=ROOT/'rag_package/requirements-retrieval.lock';assert sha(lock)=='f7988bdf801f51e27ce7538805bd9c9ca8202c0d714c13901e53f9365891b32f'
BASE.mkdir();(BASE/'wheel.txt').write_text(Path(old['wheel']).as_uri()+' --hash=sha256:'+old['wheel_sha256']+'\n')
env={'PATH':os.defpath,'PYTHONDONTWRITEBYTECODE':'1','PIP_CONFIG_FILE':os.devnull,'PIP_DISABLE_PIP_VERSION_CHECK':'1','PIP_NO_INPUT':'1'}
commands=[]
state={'started_at':start,'preparation_deadline':deadline,'original_deadline':1795808563.61378,'environment':str(ENV),'python':str(ENV/'bin/python'),'wheel':old['wheel'],'wheel_sha256':old['wheel_sha256'],'lock':str(lock),'lock_sha256':sha(lock),'status':'preparing','model_calls':0,'automatic_retry':0}
write('preparation.json',state)
def run(args):
 remaining=deadline-time.time();assert remaining>0,'preparation deadline'
 p=subprocess.run(list(map(str,args)),env=env,cwd='/private/tmp',capture_output=True,text=True,timeout=remaining)
 commands.append({'args':list(map(str,args)),'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr});write('install-commands.json',commands)
 assert p.returncode==0,'preparation command failed'
try:
 run([old['python'],'-B','-I','-m','venv',ENV])
 run([ENV/'bin/python','-B','-I','-m','pip','install','--isolated','--index-url','https://pypi.org/simple','--retries','0','--timeout','30','--only-binary=:all:','--no-cache-dir','--require-hashes','--report',E/'pip-report.json','-r',lock,'-r',BASE/'wheel.txt'])
 run([ENV/'bin/python','-B','-I','-m','pip','check'])
 state.update(status='installed_audit_pending',finished_install_at=time.time());write('preparation.json',state)
 print(json.dumps({'status':state['status'],'python':state['python'],'remaining_preparation_seconds':deadline-time.time()}))
except BaseException as e:
 state.update(status='halted',error=type(e).__name__,finished_at=time.time());write('preparation.json',state);raise
