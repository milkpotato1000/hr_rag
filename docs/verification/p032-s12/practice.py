"""Create two explicitly synthetic answers, then compare saved results offline."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
from unittest.mock import patch

E = Path(__file__).resolve().parent
def read(p):
    return json.loads(p.read_text())
base = Path(read(E/'installation.json')['base'])
ws = base/'practice'
py = base/'env/bin/python'
if Path(sys.executable) != py:
    previous = Path(read(E.parent/'p032-s7/installation.json')['base'])
    site = Path('env/lib/python3.12/site-packages')
    for name in ('pypdf','pypdf-6.21.2.dist-info'):
        shutil.copytree(previous/site/name,base/site/name)
    os.chdir(base)
    os.execv(py,[str(py),'-I',str(Path(__file__).resolve())])
from rag_package import pipeline
from rag_package.storage import write_json, RagError
from rag_package.workspace import init
init(ws)
shutil.copyfile(E.parent/'p032-s8/profile.json',ws/'handbook-model.json')
os.chdir(ws)
question = read(E.parent/'p032-s11/setup.json')['question']
quote = read(E.parent/'p032-s11/setup.json')['quote']
digest = read(ws/'handbook-model.json')['profiles']['local']['identity']['expected_digest']
def fixture(method,url,headers,body,timeout):
    if method == 'GET':
        return {'models':[{'name':'qwen3:4b','digest':digest}]}
    chunks=json.loads(body['messages'][-1]['content'])['contexts']
    cited=next(c for c in chunks if quote in c['text'])
    answer={'status':'answered','answer':'합성 예시 · 팀장','citations':[{'chunk_id':cited['chunk_id']}]}
    return {'model':'qwen3:4b','done':True,'done_reason':'stop','message':{'role':'assistant','content':json.dumps(answer)}}
for name in ('fixed','recursive'):
    result=pipeline.run('handbook-sources.json',f'chunk-{name}.json','handbook-local.json',question,ws/name,execute=True,transport=fixture)
    assert result['status']=='answered',result
s8=Path(read(E.parent/'p032-s8/frozen.json')['practice'])/'.rag-runs/pipeline-live'
s11=Path(read(E.parent/'p032-s11/setup.json')['practice'])/'.rag-runs/ui/artifacts'/read(E.parent/'p032-s11/review.json')['job']/'result'
for name,path in [('s8',s8),('s11',s11)]:
    shutil.copytree(path,ws/name)
def file_state(folder):
    return {str(f.relative_to(folder)):hashlib.sha256(f.read_bytes()).hexdigest() for f in folder.rglob('*') if f.is_file()}
def compare(a,b,name):
    before=[file_state(ws/x) for x in (a,b)]
    commands=[str(base/'env/bin/rag-lab'),'pipeline-compare','--runs',a,b]
    cli=json.loads(subprocess.check_output(commands,cwd=ws,text=True))
    with patch('rag_package.llm.invoke',side_effect=AssertionError('unexpected inference')):
        assert cli==pipeline.compare(ws/a,ws/b)
    assert before==[file_state(ws/x) for x in (a,b)]
    write_json(E/name,cli)
    return cli
pair=compare('fixed','recursive','fixture-comparison.json')
assert pair['changed']==['chunk.method'] and pair['interpretation']=='single_setting'
for side in pair['runs']:
    assert side['execution_kind']=='test_fixture' and len(side['contexts'])==5
    assert side['answer']['citations'][0]['quote'] in [c['text'] for c in side['contexts']]
historical=compare('s8','s11','historical-comparison.json')
assert not historical['same_question'] and historical['interpretation']=='different_inputs'
assert [r['answer']['answer'] for r in historical['runs']]==['3영업일 전','팀장']
shutil.copytree(ws/'fixed',ws/'tampered')
(ws/'tampered/pipeline.json').write_text('{}')
try:
    pipeline.compare(ws/'tampered',ws/'recursive')
except RagError as exc:
    assert exc.code=='stale_file_hash'
else:
    raise AssertionError('modified report accepted')
print('installed CLI / source preservation / model-free replay / fixture pair / archived live pair / tamper: PASS')
