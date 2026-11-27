from pathlib import Path
import json,os,subprocess,shutil,tarfile,zipfile,tempfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'final-install-current'
r=json.loads((OUT/'installation.json').read_text());installation=Path(r['base']);base=Path(tempfile.mkdtemp(prefix='verify-',dir=installation));shutil.copytree(installation/'dist',base/'dist');env=os.environ.copy();env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
commands=[]
def run(args):
 p=subprocess.run(list(map(str,args)),cwd=base,env=env,text=True,capture_output=True);commands.append({'args':list(map(str,args)),'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr});(OUT/'final-source-free-commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n');assert p.returncode==0,(p.stdout,p.stderr);return p.stdout
run(['uv','venv','--python',r['python'],base/'core'])
run(['uv','pip','install','--python',base/'core/bin/python','--no-deps',r['wheel']]);shutil.copyfile(OUT/'installed_probe.py',base/'probe.py')
(OUT/'final-core-only.json').write_text(run([base/'core/bin/python',base/'probe.py']))
sd=next((base/'dist').glob('*.tar.gz'));rebuild=base/'sdist-rebuild';rebuild.mkdir()
with tarfile.open(sd) as t:t.extractall(rebuild,filter='data')
source=next(rebuild.iterdir());run([ROOT/'.rag-runs/p028-build/.venv/bin/python','-m','build','--wheel','--no-isolation','--outdir',base/'rebuilt-dist',source])
rebuilt=next((base/'rebuilt-dist').glob('*.whl'))
with zipfile.ZipFile(r['wheel']) as a,zipfile.ZipFile(rebuilt) as b:
 for name in a.namelist():
  if name.startswith('rag_package/'):assert a.read(name)==b.read(name),name
run(['uv','venv','--python',r['python'],base/'sdist-env']);run(['uv','pip','install','--python',base/'sdist-env/bin/python','--no-deps',rebuilt]);shutil.rmtree(rebuild)
a=json.loads(run([base/'sdist-env/bin/python','-m','rag_package','model-catalog']));b=json.loads(run([base/'core/bin/python','-m','rag_package','model-catalog']));assert a==b
(OUT/'final-sdist-replay.json').write_text(json.dumps({'status':'PASS','package_bytes_equal':True,'sdk_absent':True,'source_removed':True,'catalog_same':True})+'\n')
print(base)
