"""P032 S2c: fresh core-only build/install and model-free documented commands."""
from pathlib import Path
import base64,hashlib,importlib.metadata,json,os,re,shutil,subprocess,tarfile,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
BASE=Path(tempfile.mkdtemp(prefix='p032-s3-installed-')).resolve()
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

save('installation.json', {'base':str(BASE),'python':str(py),'wheel':str(wheel),'sdist':str(sdist),'wheel_sha256':sha(wheel),'sdist_sha256':sha(sdist),'wheel_payload_hashes':{n:sha(ROOT/n) for n in allow['modules']+allow['resources']},'installed':installed})
