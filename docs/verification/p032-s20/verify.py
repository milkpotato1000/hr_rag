"""Verify the common first-run entry point, independent manual path and recovery."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

E=Path(__file__).resolve().parent
ROOT=E.parents[2]
base=Path(json.loads((E/'setup.json').read_text())['base'])
source=base/'rag-lab-source'
success=base/'rag-lab-first'
wheels=ROOT/'.rag-runs/p032-s20/wheels'
py=Path(sys.executable)
env=dict(os.environ,PIP_NO_INDEX='1',PIP_FIND_LINKS=wheels.as_uri(),PIP_DISABLE_PIP_VERSION_CHECK='1')
env.pop('PYTHONPATH',None)
records=[]
def run(cmd,cwd=source,code=0):
    p=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True)
    records.append({'cmd':[str(a) for a in cmd],'exit':p.returncode,'cwd':str(cwd)})
    assert p.returncode==code,(p.stdout,p.stderr)
    return p.stdout
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

first=read(success/'first-run.json')
assert first['source_sha']==run(['git','rev-parse','HEAD']).strip()
assert not run(['git','status','--porcelain'])
assert first['search']==first['install']=='complete' and first['generation_calls']==0
pdf=source/'rag_package/resources/sample/documents/handbook.pdf'
pdf_hash=sha(pdf)
assert first['pdf_sha256']==pdf_hash
before={p:sha(p) for p in [success/'practice/documents/handbook.pdf',success/'first-run.json',success/'commands.log']}
start=[py,'scripts/first_handbook.py','--out']
run(start+[success],code=2)
assert before=={p:sha(p) for p in before}
empty=base/'empty wheels';empty.mkdir()
broken=base/'failed install'
run(start+[broken,'--wheelhouse',empty],code=1)
failed=read(broken/'first-run.json')
assert failed['failed_stage']=='build_dependencies' and failed['search']=='pending'
fail_hash=sha(broken/'first-run.json')
recovered=base/'recovered practice'
run(start+[recovered,'--wheelhouse',wheels])
assert fail_hash==sha(broken/'first-run.json')
assert read(recovered/'first-run.json')['matches']==first['matches']
guide=(source/'README.md').read_text()
requests=[line for line in guide.splitlines() if line.startswith('> 현재 dev 소스')]
assert len(requests)==2 and requests[0]==requests[1]
ws=success/'practice'
cli=success/'env/bin/rag-lab'
run([cli,'generation-setup','--provider','ollama','--model','qwen3:4b','--out','my-local'],ws)
preset=json.loads(run([cli,'pipeline-setup','--llm-config','my-local/model.json','--chunk-config','chunk-fixed.json','--method','bm25','--out','my-search'],ws))
cmd=shlex.split(preset['commands']['pipeline_preview'])
assert cmd[0]=='rag-lab' and '--execute' not in cmd
assert json.loads(run([cli,*cmd[1:]],ws))['status']=='preview'
# Execute the documented manual procedure in the disposable clone with local wheels.
build=source/'.rag-runs/build-env'
run([py,'-m','venv',build])
run([build/'bin/python','-m','pip','install','--require-hashes','-r','packaging/requirements-build.lock'])
run([build/'bin/python','-m','build','--no-isolation','--outdir','.rag-runs/dist'])
manual_env=base/'rag-lab-env'
manual=base/'rag-lab-practice'
run([py,'-m','venv',manual_env],base)
mp=manual_env/'bin/python';mc=manual_env/'bin/rag-lab'
run([mp,'-m','pip','install','--no-deps',next((source/'.rag-runs/dist').glob('*.whl'))],base)
run([mc,'init','--out',manual],base)
run([mc,'doctor','--config','fixed.json'],manual,3)
lock=run([mp,'-c','from importlib.resources import files; print(files("rag_package")/"requirements-pdf.lock")'],manual).strip()
run([mp,'-m','pip','install','--require-hashes','-r',lock],manual)
run([mc,'snapshot','--sources','handbook-sources.json','--out','.rag-runs/pdf'],manual)
run([mc,'build','--snapshot','.rag-runs/pdf','--config','fixed.json','--out','.rag-runs/bm25'],manual)
run([mc,'ask','--run','.rag-runs/bm25','--config','fixed.json','--question',first['question'],'--out','.rag-runs/preview'],manual)
assert read(manual/'.rag-runs/preview/result.json')['contexts']==read(ws/'evidence/result.json')['contexts']
assert sha(manual/'documents/handbook.pdf')==sha(pdf)==pdf_hash
proof={'first':first,'manual_contexts_match':True,'contexts':read(ws/'evidence/result.json')['contexts'],
       'existing_result_preserved':True,'failure':failed,'recovered_with_new_out':True,'commands':records}
(E/'verified.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
