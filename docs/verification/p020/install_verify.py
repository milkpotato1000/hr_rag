from pathlib import Path
import json,os,subprocess,shutil,tarfile,zipfile,tempfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
r=json.loads((OUT/'installation.json').read_text());installation=Path(r['base']);base=Path(tempfile.mkdtemp(prefix='verify-',dir=installation));shutil.copytree(installation/'dist',base/'dist');env=os.environ.copy();env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
commands=[]
def run(args):
 p=subprocess.run(list(map(str,args)),cwd=base,env=env,text=True,capture_output=True);commands.append({'args':list(map(str,args)),'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr});(OUT/'source-free-commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n');assert p.returncode==0,(p.stdout,p.stderr);return p.stdout
run(['uv','venv','--python',r['python'],base/'core'])
run(['uv','pip','install','--python',base/'core/bin/python','--no-deps',r['wheel']])
shutil.copytree(ROOT/'3. Hybrid RAG',base/'stage');shutil.copyfile(OUT/'installed_probe.py',base/'probe.py')
(OUT/'core-only.json').write_text(run([base/'core/bin/python',base/'probe.py']))
# Rebuild the actual sdist in the approved isolated build environment, then install separately.
sd=next((base/'dist').glob('*.tar.gz'));rebuild=base/'sdist-rebuild';rebuild.mkdir()
with tarfile.open(sd) as t:t.extractall(rebuild,filter='data')
source=next(rebuild.iterdir());run([ROOT/'.rag-runs/p028-build/.venv/bin/python','-m','build','--wheel','--no-isolation','--outdir',base/'rebuilt-dist',source])
rebuilt=next((base/'rebuilt-dist').glob('*.whl'))
with zipfile.ZipFile(r['wheel']) as a,zipfile.ZipFile(rebuilt) as b:
 for name in a.namelist():
  if name.startswith('rag_package/'):assert a.read(name)==b.read(name),name
run(['uv','venv','--python',r['python'],base/'sdist-env']);run(['uv','pip','install','--python',base/'sdist-env/bin/python','--no-deps',rebuilt]);shutil.rmtree(rebuild)
run([base/'sdist-env/bin/python','-m','rag_package','rerank-report','--run',base/'comparison','--out',base/'sdist-report'])
assert json.loads((base/'sdist-report/replayed.json').read_text())==json.loads((base/'report/replayed.json').read_text())
(OUT/'sdist-replay.json').write_text(json.dumps({'status':'PASS','package_bytes_equal':True,'sdk_absent':True,'source_removed':True,'report_same':True})+'\n')
print(base)
