"""Create P028 isolated wheel-only/core/extras environments using explicit uv."""
from pathlib import Path
import json,os,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
base=Path(tempfile.mkdtemp(prefix='p028-installed-')).resolve();wheel=next((ROOT/'.rag-runs/p028-build/dist').glob('*.whl'))
python=ROOT/'.rag-runs/p028-build/.venv/bin/python';commands=[]
def run(args):
    p=subprocess.run([str(x) for x in args],cwd=base,text=True,capture_output=True)
    commands.append({'args':[str(x) for x in args],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    (OUT/'installation.json').write_text(json.dumps({'base':str(base),'commands':commands},indent=2)+'\n')
    assert p.returncode==0,(p.stdout,p.stderr)
for name in ('core','extras','rebuilt'):
    run(['uv','venv','--python',python,base/name])
    if name=='extras':
        run(['uv','pip','install','--python',base/name/'bin/python','--index-url','https://pypi.org/simple','--require-hashes','-r',ROOT/'rag_package/requirements-pdf.lock','-r',ROOT/'rag_package/requirements-drive.lock'])
    run(['uv','pip','install','--python',base/name/'bin/python','--no-deps',wheel])
    run(['uv','pip','check','--python',base/name/'bin/python'])
print(base)
