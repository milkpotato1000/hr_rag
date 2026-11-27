"""P032 S2c: fresh core-only build/install and model-free documented commands."""
from pathlib import Path
import base64,hashlib,importlib.metadata,json,os,re,shutil,subprocess,tarfile,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
BASE=Path(tempfile.mkdtemp(prefix='p032-s2c-installed-')).resolve()
COMMANDS=[]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def run(args,cwd=BASE,expected=0):
    # Explicit minimal environment: no user API variables, proxies or PYTHONPATH.
    env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','LANG':'en_US.UTF-8','PYTHONDONTWRITEBYTECODE':'1','PIP_NO_INDEX':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1'}
    p=subprocess.run([str(a) for a in args],cwd=cwd,env=env,capture_output=True,text=True)
    COMMANDS.append({'args':[str(a) for a in args],'cwd':str(cwd),'exit_code':p.returncode,'expected':expected,'stdout':p.stdout,'stderr':p.stderr})
    save('commands.json',COMMANDS)
    assert p.returncode==expected,COMMANDS[-1]
    return p.stdout
# Preserve every previous evidence file, fixed protected source/GT set, runtime and locks.
preserved={}
for directory in ('p032-s1','p032-s2a','p032-s2b','p032-s2b-recovery001'):
    for p in (ROOT/'docs/verification'/directory).rglob('*'):
        if p.is_file():preserved[str(p.relative_to(ROOT))]=sha(p)
protected=json.loads((ROOT/'docs/verification/p032-s1/preservation.json').read_text())['files']
for name,digest in protected.items():
    p=ROOT/name;assert sha(p)==digest,name;preserved[name]=digest
for name in subprocess.check_output(['git','ls-files','rag_package','packaging','pyproject.toml'],cwd=ROOT,text=True).splitlines():
    if name not in ('rag_package/resources/sample/START_HERE.md','rag_package/resources/manifest.json'):preserved[name]=sha(ROOT/name)
old=Path('/private/var/folders/vf/5r80qzss57n0fz_k0ckt_x7c0000gn/T/p032-s1-installed-xnqj3p_4/dist/milkpotato_rag_lab-0.1.0.dev1-py3-none-any.whl')
old_hash=sha(old);assert old_hash=='9342add625a9ed633dffb2fccb3bad27379e8cddaf9a06836ea5a224fe9f280a'
save('preservation.json',{'files':preserved,'protected_count':len(protected),'old_experiment_wheel':str(old),'old_wheel_sha256':old_hash})
# Reuse existing complete build environment; no pip install/build-tool replacement.
buildpy=ROOT/'.rag-runs/p028-build/.venv/bin/python'
audit=r'''
import base64,hashlib,importlib.metadata,json,re
from pathlib import Path
import build,setuptools,packaging,pyproject_hooks
lock=Path(__import__('sys').argv[1]).read_text();rows=[]
for name,version in re.findall(r'^([\w-]+)==([^\s]+)',lock,re.M):
    d=importlib.metadata.distribution(name);assert d.version==version
    count=0
    for f in d.files or []:
        p=d.locate_file(f);assert p.is_file(),str(p)
        if f.hash:
            actual=base64.urlsafe_b64encode(hashlib.new(f.hash.mode,p.read_bytes()).digest()).rstrip(b'=').decode();assert actual==f.hash.value,str(p);count+=1
    rows.append({'name':name,'version':version,'record_hashes':count})
print(json.dumps(rows))
'''
save('build-environment.json',{'python':str(buildpy),'lock_sha256':sha(ROOT/'packaging/requirements-build.lock'),'audit':json.loads(run([buildpy,'-I','-c',audit,ROOT/'packaging/requirements-build.lock'])),'new_installations':0})
src=BASE/'build-source';src.mkdir();allow=json.loads((ROOT/'packaging/allowlist.json').read_text())
for name in allow['modules']+allow['resources']+allow['sdist_extra']:
    target=src/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
run([buildpy,'-m','build','--no-isolation','--outdir',BASE/'dist',src])
wheel=next((BASE/'dist').glob('*.whl'));sdist=next((BASE/'dist').glob('*.tar.gz'))
with zipfile.ZipFile(wheel) as z:
    names=z.namelist();assert {n for n in names if '.dist-info/' not in n}==set(allow['modules']+allow['resources'])
    for n in allow['modules']+allow['resources']:assert z.read(n)==(ROOT/n).read_bytes()
with tarfile.open(sdist) as t:
    files=[m for m in t.getmembers() if m.isfile()];paths=[m.name.split('/',1)[1] for m in files]
    for m,name in zip(files,paths):
        assert name in allow['modules']+allow['resources']+allow['sdist_extra'] or name in ('PKG-INFO','setup.cfg') or name.startswith('milkpotato_rag_lab.egg-info/')
        if name in allow['modules']+allow['resources']:assert t.extractfile(m).read()==(ROOT/name).read_bytes()
run([buildpy,'-m','venv',BASE/'env'])
py=BASE/'env/bin/python';cli=BASE/'env/bin/rag-lab'
run([py,'-m','pip','install','--no-index','--no-deps',wheel]);run([py,'-m','pip','check'])
installed=json.loads(run([py,'-I','-c','import rag_package,importlib.metadata,json; print(json.dumps({"package":rag_package.__file__,"distributions":sorted((d.metadata["Name"],d.version) for d in importlib.metadata.distributions())}))']))
assert str(BASE/'env') in installed['package'];assert {n.lower() for n,v in installed['distributions']}=={'pip','milkpotato-rag-lab'}
# The source-free CLI wrapper denies network, child workers and provider key lookups.
wrapper=BASE/'offline_cli.py';wrapper.write_text('''import sys,os,socket,subprocess
from unittest.mock import patch
import rag_package
assert "/env/" in rag_package.__file__
def deny(*a,**k): raise AssertionError("S2c forbids network/worker/key access")
original=os._Environ.__getitem__
def no_key(self,key):
    if any(word in str(key).upper() for word in ("API_KEY","TOKEN","CREDENTIAL","SECRET")):deny()
    return original(self,key)
llm=sys.argv[1:2]==["--llm"]
if llm:
    from rag_package.llm.__main__ import main
    argv=sys.argv[2:]
else:
    from rag_package.__main__ import main
    argv=sys.argv[1:]
with patch.object(socket.socket,"connect",deny),patch.object(socket,"create_connection",deny),patch.object(socket,"getaddrinfo",deny),patch.object(subprocess,"Popen",deny),patch.object(os._Environ,"__getitem__",no_key):
    raise SystemExit(main(argv))
''')
shutil.copyfile(wrapper,OUT/'offline_cli.py')
def check(args,expected=0,cwd=None):return run([py,'-I',wrapper]+args,cwd or work,expected)
work=BASE/'practice';check(['init','--out',str(work)],cwd=BASE)
assert not (work/'.git').exists() and not (work/'rag_package').exists()
manifest=json.loads((ROOT/'rag_package/resources/manifest.json').read_text())
for item in manifest['files']:assert sha(work/item['path'])==item['sha256']
check(['--version']);check(['doctor']);doctor=json.loads(check(['doctor','--config','fixed.json'],3));assert doctor['status']=='needs_configuration' and doctor['live_checks']=='not_checked'
check(['snapshot','--sources','sources.json','--out','.rag-runs/snapshot-01'])
for method in ('fixed','recursive','structure'):
    check(['build','--snapshot','.rag-runs/snapshot-01','--config',method+'.json','--out','.rag-runs/'+method+'-01'])
    check(['ask','--run','.rag-runs/'+method+'-01','--config',method+'.json','--question','생일 휴가 자격과 신청 기한은?','--out','.rag-runs/answer-'+method])
check(['compare','--snapshot','.rag-runs/snapshot-01','--configs','fixed.json','recursive.json','structure.json','--questions','questions.json','--out','.rag-runs/compare-01'])
for method in ('fixed','recursive','structure'):
    check(['chunk','--snapshot','.rag-runs/snapshot-01','--config','chunk-'+method+'.json','--out','.rag-runs/chunk-'+method])
    check(['chunk-replay','--run','.rag-runs/chunk-'+method])
check(['build','--snapshot','.rag-runs/snapshot-01','--config','rag-frozen.json','--out','.rag-runs/frozen-index'])
check(['ask','--run','.rag-runs/frozen-index','--config','rag-frozen.json','--question','생일 휴가 자격은?','--out','.rag-runs/frozen-answer'])
for method in ('semantic','llm'):check(['chunk','--snapshot','.rag-runs/snapshot-01','--config','chunk-'+method+'.json','--out','.rag-runs/'+method+'-preview'])
for mode,output in [('local','my-llm-preview.json'),('api','my-api-preview.json')]:
    r=json.loads(check(['llm-configure','--spec','llm-spec-'+mode+'.json','--out',output]));assert r['http_requests']==r['secrets_read']==r['generation_requests']==0
    check(['doctor','--llm-config',output],3);check(['--llm','validate','--config',output])
check(['model-catalog']);check(['model-plan','--model','intfloat/multilingual-e5-small','--role','embedding','--out','.rag-runs/e5-plan']);check(['model-prepare','--plan','.rag-runs/e5-plan','--out','.rag-runs/e5-ready']);check(['retrieval-preview','--config','rag-hybrid.json'])
for command in ('init','doctor','snapshot','build','ask','compare','chunk','chunk-replay','chunk-report','llm-configure','model-plan','model-prepare','serve','rerank'):
    check([command,'--help'])
# Resource/config regression against installed package, not checkout imports.
testfile=BASE/'test_installable.py';shutil.copyfile(ROOT/'tests/rag_package/test_installable.py',testfile)
run([py,'-I',testfile],cwd=BASE)
comparison=json.loads((work/'.rag-runs/compare-01/summary.json').read_text())
assert all(r['status']=='preview' and not r['dispatch_attempted'] for r in comparison['rows'])
for name,digest in preserved.items():assert sha(ROOT/name)==digest,name
assert sha(old)==old_hash
save('installation.json',{'status':'PASS','adoption':'9be41de90ec370d67db4e2af4bf70e5636d5c2bf','source_head_at_build':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'base':str(BASE),'python':str(py),'wheel':str(wheel),'wheel_sha256':sha(wheel),'sdist':str(sdist),'sdist_sha256':sha(sdist),'wheel_inventory':names,'sdist_inventory':paths,'installed':installed,'source_free_cwd':str(work),'PYTHONPATH':'unset','isolated_python':True,'no_network_worker_key_guard':True,'preview_rows':len(comparison['rows']),'preserved_files':len(preserved),'model_calls':0,'network_calls':0,'existing_environment_modified':False,'old_wheel_preserved':True,'resource_sha256':sha(ROOT/'rag_package/resources/manifest.json')})
print('PASS '+str(BASE))
