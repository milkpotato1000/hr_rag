"""Read the browser output and replay six prior search configurations as previews."""
from pathlib import Path
import json
import subprocess
import tempfile

here=Path(__file__).resolve().parent
def read(p):
    return json.loads(p.read_text())
base=Path(read(here/'installation.json')['base'])
ws=base/'practice'
ui=ws/'.rag-runs/ui'
verified=read(here/'verified.json')
cli_report=read(ws/'내 문서 실습-preview/pipeline.json')
jobs=[read(p) for p in (ui/'jobs').glob('*.json')]
assert len(jobs)==2
questions=[]
for job in jobs:
    report=read(ui/'artifacts'/job['id']/'result/pipeline.json')
    assert job['status']=='completed' and job['dispatch_attempted'] is False
    assert report['plan']==cli_report['plan']
    questions.append(report['question'])
assert set(questions)=={verified['question'],'교육 휴가 규정은 몇 버전인가요?'}
old=Path(read(here.parent/'p032-s15/installation.json')['base'])/'practice'
with tempfile.TemporaryDirectory() as tmp:
    for name in read(here.parent/'p032-s15/verified.json')['cases']:
        before=read(old/(name+'-preview')/'pipeline.json')
        out=Path(tmp)/name
        args=['pipeline','--sources','handbook-sources.json','--chunk-config',name+'/chunk.json',
              '--search-config',name+'/search.json','--question',before['question'],'--out',str(out)]
        if (old/name/'reranker.json').is_file():
            args+=['--reranker-profile',name+'/reranker.json']
        raw=subprocess.check_output([base/'env/bin/rag-lab',*args],cwd=old,text=True)
        assert json.loads(raw)==before
print('Two browser previews match CLI source and settings. S15 six saved configurations reproduced.')
