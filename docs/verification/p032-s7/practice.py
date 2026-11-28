"""Exercise the shipped guide in the fresh installation, using only local files."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

E = Path(__file__).resolve().parent
root = E.parents[2]
def read(p):
    return json.loads(p.read_text())
def save(p, v):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n')

base = Path(read(E/'installation.json')['base'])
ws = base/'practice'
site = Path('env/lib/python3.12/site-packages')
old = Path(read(E.parent/'p032-s3/installation.json')['base'])
# Reuse only the pinned PDF reader from the verified S3 installation.
for name in ('pypdf','pypdf-6.21.2.dist-info'):
    shutil.copytree(old/site/name,base/site/name)
env = {'PATH':str(base/'env/bin')+':/usr/bin:/bin','PIP_NO_INDEX':'1','PYTHONDONTWRITEBYTECODE':'1','LANG':'en_US.UTF-8'}
def run(args, cwd):
    p = subprocess.run(args,cwd=cwd,env=env,text=True,capture_output=True)
    with (E/'practice.log').open('a') as f:
        f.write(f'{args[0]} {args[1]} exit={p.returncode}\n'+p.stdout+p.stderr)
    p.check_returncode()
run(['python','-c','import pypdf; assert pypdf.__version__=="6.21.2"'],base)
run(['rag-lab','init','--out','practice'],base)
audit=read(root/'docs/planning/reviews/p032-s2d-input-audit.json')
pdf=root/audit['source_pdf']
assert hashlib.sha256(pdf.read_bytes()).hexdigest()==audit['source_pdf_sha256']
shutil.copyfile(pdf,ws/'documents/handbook.pdf')
run(['rag-lab','snapshot','--sources','handbook-sources.json','--out','.rag-runs/pdf'],ws)
source=(ws/'.rag-runs/pdf/handbook/canonical.txt').read_text()
full='생일 특별휴가는 사용 3영업일 전까지 휴가 시스템에서 신청하고 팀장의 승인을 받아야 한다.'
assert source.count(full)==1 and full in (ws/'.rag-runs/pdf/handbook/page-1.txt').read_text()
a=source.index(full)
save(E/'target.json',dict(pdf_sha256=audit['source_pdf_sha256'],source_sha256=hashlib.sha256(source.encode()).hexdigest(),page=1,start=a,deadline_end=a+len(full.split('하고')[0]),end=a+len(full),before=source[a-40:a],quote=full,after=source[a+len(full):a+len(full)+40]))
guide=(ws/'HANDBOOK.md').read_text().split('## PDF 청킹 비교')[1]
commands=guide.split('```sh\n')[1].split('\n```')[0]
run(['/bin/sh','-ec',commands],ws)
hierarchy=(ws/'HANDBOOK.md').read_text().split('## 장·절·조항 경로')[1]
run(['/bin/sh','-ec',hierarchy.split('```sh\n')[1].split('\n```')[0]],ws)
previous=Path(read(E.parent/'p032-s6/installation.json')['base'])/'practice/.rag-runs'
for m in ('fixed','recursive','structure'):
    name='handbook-chunk-'+m
    run(['rag-lab','chunk-replay','--run',str(previous/name)],ws)
    assert read(previous/name/'chunks.json')==read(ws/'.rag-runs'/name/'chunks.json')
