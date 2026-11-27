"""Complete locked distribution + RECORD content audit, independent of SDK imports."""
from pathlib import Path
import re,csv,hashlib,base64,json,zipfile,importlib.metadata as md,subprocess,sys,os,time

def norm(s):return re.sub(r'[-_.]+','-',s).lower()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def locked(text):return {norm(n):v for n,v in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\]+)',text,re.M)}
def audit(site,lock,wheel):
 site=Path(site);expected=locked(Path(lock).read_text());found={norm(d.metadata['Name']):d for d in md.distributions(path=[str(site)]) if d.metadata['Name']}
 for name,version in expected.items():
  if name not in found:raise ValueError('missing_distribution:'+name)
  if found[name].version!=version:raise ValueError('version_mismatch:'+name)
 checked=0;excluded=[];distributions={}
 for name,d in sorted(found.items()):
  records=d.read_text('RECORD');metadata=d.read_text('METADATA')
  if records is None or metadata is None:raise ValueError('missing_record_metadata:'+name)
  distributions[name]=d.version
  for path,digest,size in csv.reader(records.splitlines()):
   p=Path(d.locate_file(path)).resolve()
   if not p.is_file():raise ValueError('missing_file:'+path)
   if digest:
    algo,encoded=digest.split('=',1)
    if algo!='sha256':raise ValueError('unsupported_digest:'+algo)
    actual=base64.urlsafe_b64encode(bytes.fromhex(sha(p))).decode().rstrip('=')
    if actual!=encoded:raise ValueError('file_hash_mismatch:'+path)
    if size and p.stat().st_size!=int(size):raise ValueError('file_size_mismatch:'+path)
    checked+=1
   else:excluded.append(path)
 with zipfile.ZipFile(wheel) as z:
  names=[n for n in z.namelist() if n.startswith('rag_package/') and not n.endswith('/')]
  for name in names:
   if not (site/name).is_file() or hashlib.sha256(z.read(name)).hexdigest()!=sha(site/name):raise ValueError('product_wheel_mismatch:'+name)
 return {'status':'PASS','locked_distributions':expected,'installed_distributions':distributions,'hashed_files_checked':checked,'unhashed_generated_or_record_files':excluded,'wheel_product_files':len(names)}

def clean_env():return {'PATH':os.defpath,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','HF_HUB_DISABLE_IMPLICIT_TOKEN':'1','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}
def import_check(python,script,timeout=60):
 p=subprocess.run([str(python),'-B','-I',str(script)],cwd='/private/tmp',env=clean_env(),text=True,capture_output=True,timeout=timeout)
 if p.returncode:raise ValueError('sdk_import_failed:'+p.stderr[-2000:])
 r=json.loads(p.stdout)
 if r.get('status')!='PASS':raise ValueError('sdk_import_failed')
 return r

if __name__=='__main__':
 E=Path(__file__).resolve().parent;state=json.loads((E/'preparation.json').read_text());deadline=state['preparation_deadline']
 assert time.time()<deadline
 try:
  report=audit(Path(sys.prefix)/'lib/python3.12/site-packages',state['lock'],state['wheel'])
  pip=json.loads((E/'pip-report.json').read_text());allowed=set(re.findall(r'--hash=sha256:([a-f0-9]{64})',Path(state['lock']).read_text()))|{state['wheel_sha256']}
  artifacts=[]
  for item in pip['install']:
   d=item['download_info'];h=d['archive_info']['hashes']['sha256'];assert h in allowed
   url=d['url'];assert url.startswith('https://files.pythonhosted.org/') or url==Path(state['wheel']).as_uri()
   artifacts.append({'name':item['metadata']['name'],'version':item['metadata']['version'],'url':url,'sha256':h})
  report['distribution_archives']=artifacts
  report['sdk_import']=import_check(sys.executable,E/'import_only.py',min(60,deadline-time.time()))
  p=subprocess.run([sys.executable,'-B','-I','-m','rag_package','--help'],env=clean_env(),cwd='/private/tmp',capture_output=True,text=True,timeout=min(30,deadline-time.time()));assert p.returncode==0
  (E/'installed-cli-help.log').write_text(p.stdout+p.stderr)
  assert time.time()<deadline
  report.update(finished_at=time.time(),preparation_deadline=deadline,model_calls=0)
  (E/'environment-audit.json').write_text(json.dumps(report,indent=2)+'\n')
  state.update(status='PASS',finished_at=time.time());(E/'environment-ready.json').write_text(json.dumps(state,indent=2)+'\n')
  print(json.dumps({'status':'PASS','locked_distributions':len(report['locked_distributions']),'hashed_files_checked':report['hashed_files_checked'],'model_calls':0}))
 except BaseException as e:
  state.update(status='halted',error=str(e),finished_at=time.time());(E/'environment-ready.json').write_text(json.dumps(state,indent=2)+'\n');raise
