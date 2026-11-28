from pathlib import Path
import json,shutil,subprocess
E=Path(__file__).resolve().parent
ROOT=E.parents[2]
def read(p):
    return json.loads(p.read_text())
def save(p,v):
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
base=Path(read(E/'installation.json')['base'])
prev=Path(read(E.parent/'p032-s8/frozen.json')['practice'])
site=Path('env/lib/python3.12/site-packages')
pdfenv=Path(read(E.parent/'p032-s7/installation.json')['base'])
for n in ('pypdf','pypdf-6.21.2.dist-info'):
    shutil.copytree(pdfenv/site/n,base/site/n)
cli=base/'env/bin/rag-lab'
ws=base/'practice'
subprocess.run([cli,'init','--out',ws],cwd=base,check=True,stdout=subprocess.DEVNULL)
for n in ('documents/handbook.pdf','handbook-model.json','pipeline-search.json'):
    shutil.copyfile(prev/n,ws/n)
shutil.copytree(prev/'.rag-runs/pipeline-live',ws/'.rag-runs/pipeline-live')
for name,folder in [('e5','e5'),('mmini','mmini')]:
    parent=ROOT/'.rag-runs/p032-s1-live/run001'/folder/'prepared'
    cfg=read(parent/'profile.json')
    cfg['local_path']=str(parent/'model')
    save(ws/(name+'.json'),cfg)
subprocess.run([cli,'llm-configure','--spec','llm-spec-api.json','--out','handbook-api.json'],cwd=ws,check=True,stdout=subprocess.DEVNULL)
args=read(E.parent/'p032-s8/frozen.json')['cli_args']
preview=json.loads(subprocess.check_output([cli,*args,'--out','.rag-runs/new-cli-preview'],cwd=ws,text=True))
save(E/'cli-preview.json',preview)
assert preview['plan']==read(E.parent/'p032-s8/preview.json')['plan']
