"""Build explicit P032 S1 payload and install wheel into a new source-free environment."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tempfile,zipfile,tarfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
base=Path(tempfile.mkdtemp(prefix='p032-s1-installed-')).resolve();src=base/'build-source';src.mkdir();allow=json.loads((ROOT/'packaging/allowlist.json').read_text());commands=[]
def run(args):
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
    p=subprocess.run([str(x) for x in args],cwd=base,env=env,text=True,capture_output=True)
    commands.append({'args':[str(x) for x in args],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr});(OUT/'build-install-commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert p.returncode==0,(p.stdout,p.stderr)
for name in allow['modules']+allow['resources']+allow['sdist_extra']:
    p=src/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
run([ROOT/'.rag-runs/p028-build/.venv/bin/python','-m','build','--no-isolation','--outdir',base/'dist',src])
wheel=next((base/'dist').glob('*.whl'));sdist=next((base/'dist').glob('*.tar.gz'))
with zipfile.ZipFile(wheel) as z:
    names=z.namelist();assert {n for n in names if '.dist-info/' not in n}==set(allow['modules']+allow['resources'])
    for n in allow['modules']+allow['resources']:assert z.read(n)==(ROOT/n).read_bytes()
with tarfile.open(sdist) as t:
    paths=[m.name.split('/',1)[1] for m in t.getmembers() if m.isfile()]
    assert all(p in allow['modules']+allow['resources']+allow['sdist_extra'] or p in ('PKG-INFO','setup.cfg') or p.startswith('milkpotato_rag_lab.egg-info/') for p in paths)
run(['uv','venv','--python',ROOT/'.rag-runs/p028-build/.venv/bin/python',base/'env'])
run(['uv','pip','install','--python',base/'env/bin/python','--index-url','https://pypi.org/simple','--require-hashes','-r',ROOT/'rag_package/requirements-pdf.lock','-r',ROOT/'rag_package/requirements-drive.lock','-r',ROOT/'rag_package/requirements-retrieval.lock'])
run(['uv','pip','install','--python',base/'env/bin/python','--no-deps',wheel]);run(['uv','pip','check','--python',base/'env/bin/python'])
# Remove build source from this execution area: installed tests and browser cannot import it.
shutil.rmtree(src)
record={'status':'PASS','base':str(base),'python':str(base/'env/bin/python'),'wheel':str(wheel),'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'sdist_sha256':hashlib.sha256(sdist.read_bytes()).hexdigest(),'wheel_inventory':names,'sdist_inventory':paths,'developer_source_removed':True}
(OUT/'installation.json').write_text(json.dumps(record,indent=2)+'\n');print(base)
