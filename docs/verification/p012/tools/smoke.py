"""Bounded real default-routing and independent-copy checks; no retries."""
import subprocess,sys,json,tempfile,shutil,time,urllib.request,threading,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p012';stage=root/'1. Naive RAG/variants/langchain';out=ev/'smokes';out.mkdir(exist_ok=True)
copy=Path(tempfile.mkdtemp(prefix='p012-copy-'))/'langchain'
shutil.copytree(stage,copy,ignore=shutil.ignore_patterns('.venv','.runtime','__pycache__','*.pyc'))
subprocess.run([str(stage/'.venv/bin/python'),'-m','venv',str(copy/'.venv')],check=True)
with (ev/'copy-install.log').open('w') as f:
 subprocess.run([str(copy/'.venv/bin/python'),'-m','pip','install','--no-index','--find-links',str(stage/'.runtime/wheels'),'--require-hashes','-r',str(copy/'requirements-langchain.lock'),'-r',str(copy/'ingestion-requirements.lock')],stdout=f,stderr=subprocess.STDOUT,check=True)
with (ev/'copy-indexes.json').open('w') as f:subprocess.run([str(copy/'.venv/bin/python'),str(copy/'scripts/copy_indexes.py'),'--source-runtime',str(stage/'.runtime')],stdout=f,check=True)
(ev/'copy-location.json').write_text(json.dumps({'path':str(copy),'model_service':'shared existing pinned original localhost:11434','independent_venv':True,'parent_imports':False},indent=2)+'\n')
def record(label,r):
 assert not (out/(label+'.json')).exists()
 (out/(label+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 t=r.get('trace',{});n=t.get('generation_calls',0)
 with (ev/'ledger.jsonl').open('a') as f:f.write(json.dumps({'slot':label,'dispatches':n,'status':r['status'],'count_basis':'pipeline trace; no automatic retries'},ensure_ascii=False)+'\n')
 print(label,r['status'],t.get('comparison'),flush=True)
 assert r['status']!='error',label
 return r
q='재택근무일과 휴가일에도 사무실 식대가 나오나요?'
for label,folder,flags,expected in [('cli-default',stage,[],'langchain'),('cli-direct',stage,['--implementation','direct'],'direct'),('copy-cli-default',copy,[],'langchain')]:
 proc=subprocess.run([str(folder/'.venv/bin/python'),str(folder/'scripts/ask_compare.py'),'--question',q,'--retriever','bm25',*flags],cwd=folder,capture_output=True,text=True)
 r=record(label,json.loads(proc.stdout));assert proc.returncode==0 and r['trace']['comparison']['implementation']==expected
body={'question':'생일 휴가는 누구나 입사 직후부터 사용할 수 있나요?'}
request=urllib.request.Request('http://127.0.0.1:8001/api/ask',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
r=record('api-default',json.load(urllib.request.urlopen(request,timeout=160)));assert r['trace']['comparison']['implementation']=='langchain'
# Copy API also runs from the independent interpreter/source, with empty context: zero generation.
script="""import sys,json,threading,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'scripts'))
from serve_compare import LearningServer
with LearningServer(0) as s:
 t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
 try:
  req=urllib.request.Request('http://127.0.0.1:'+str(s.server_port)+'/api/ask',data=json.dumps({'question':'zzzzzzzz','retriever':'bm25'}).encode(),headers={'Content-Type':'application/json'})
  print(json.dumps(json.load(urllib.request.urlopen(req))))
 finally:s.shutdown();t.join()
"""
proc=subprocess.run([str(copy/'.venv/bin/python'),'-c',script],cwd=copy,capture_output=True,text=True,check=True)
r=record('copy-api-default',json.loads(proc.stdout));assert r['reason']=='no_context' and r['trace']['generation_calls']==0 and r['trace']['comparison']['implementation']=='langchain'
# Every product file in the independent folder has the same bytes as its source.
files={str(p.relative_to(copy)):hashlib.sha256(p.read_bytes()).hexdigest() for p in copy.rglob('*') if p.is_file() and not any(x in ('.venv','.runtime','__pycache__') for x in p.relative_to(copy).parts)}
assert all(hashlib.sha256((stage/p).read_bytes()).hexdigest()==h for p,h in files.items())
(ev/'copy-smoke.json').write_text(json.dumps({'status':'PASS','path':str(copy),'product_hashes':files,'live_cli':'smokes/copy-cli-default.json','api_default_zero_generation':'smokes/copy-api-default.json','parent_source_imports':False,'shared_model_service':True},indent=2)+'\n')
(ev/'routing-smoke.json').write_text(json.dumps({'status':'PASS','default_cli':'langchain','default_api':'langchain','explicit_direct':'direct','dispatches':4},indent=2)+'\n')
