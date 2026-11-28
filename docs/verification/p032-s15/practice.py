"""Exercise the installed CLI and served UI without enabling model execution."""
from pathlib import Path
import hashlib
import json
import shlex
import shutil
import subprocess
import time
import urllib.request
import uuid

E=Path(__file__).resolve().parent
root=E.parents[2]
def read(p):
    return json.loads(p.read_text())
base=Path(read(E/'installation.json')['base'])
ws=base/'practice'
env={'PATH':str(base/'env/bin')+':/usr/bin:/bin','LANG':'en_US.UTF-8','PYTHONUNBUFFERED':'1',
     'PYTHONDONTWRITEBYTECODE':'1','PIP_NO_INDEX':'1'}
site=Path('env/lib/python3.12/site-packages')
previous=Path(read(E.parent/'p032-s7/installation.json')['base'])
for name in ('pypdf','pypdf-6.21.2.dist-info'):
    shutil.copytree(previous/site/name,base/site/name)
def run(args,cwd=ws,ok=True):
    p=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=120)
    assert (p.returncode==0)==ok,(args,p.stdout,p.stderr)
    return json.loads(p.stdout)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
run(['rag-lab','init','--out','practice'],cwd=base)
run(['rag-lab','generation-setup','--provider','ollama','--model','qwen3:4b','--out','my local'])
prepared=root/'.rag-runs/p032-s1-live'
paths={model:prepared/parent/model/'prepared/profile.json' for parent,model in [
    ('run001','e5'),('run001','mmini'),('continuation001','bge'),('continuation001','bge-reranker')]}
protected=[*paths.values(),ws/'my local/model.json',ws/'chunk-handbook.json',ws/'documents/handbook.pdf']
before=[sha(p) for p in protected]
common=['rag-lab','pipeline-setup','--llm-config','my local/model.json','--chunk-config','chunk-handbook.json',
        '--top-k','3','--candidate-k','12','--context-budget-chars','1700']
rows={}
cases=[('bm25 off','bm25',None,None),('dense e5','dense','e5',None),('hybrid e5','hybrid','e5',None),
       ('hybrid bge','hybrid','bge',None),('mmini on','hybrid','bge','mmini'),('bge on','hybrid','bge','bge-reranker')]
for label,method,embed,rank in cases:
    cmd=common+['--method',method,'--out',label]
    if embed:cmd+=['--embedding-config',str(paths[embed])]
    if rank:cmd+=['--reranker-config',str(paths[rank])]
    result=run(cmd)
    plan=run(shlex.split(result['commands']['pipeline_preview']))
    assert plan['question']=='생일 특별휴가를 신청하면 누구의 승인을 받아야 하나요?'
    assert plan['plan']['retrieval']==result['retrieval'] and plan['generation_requests']==0
    args=shlex.split(result['commands']['serve'])+['--port','0']
    ui=subprocess.Popen(args,cwd=ws,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        line=ui.stdout.readline()
        assert line,(args,ui.stderr.read())
        origin=json.loads(line)['url']
        def get(path):
            return json.load(urllib.request.urlopen(origin+path,timeout=10))['data']
        boot=get('/api/bootstrap')
        assert len(boot['configs'])==1, 'shared generation profile registered twice'
        defaults=boot['pipeline_defaults']
        assert defaults['question']==plan['question'] and defaults['retrieval']==result['retrieval'] and not boot['allow_model_execution']
        ids=[x['id'] for x in boot['inputs']]
        def model_id(kind,key):
            return next((x['model_id'] for x in boot[kind] if x['id']==defaults[key]),None)
        for role,choice,kind,key in [('embedding',embed,'embedding_configs','embedding_id'),('reranker',rank,'reranker_configs','reranker_id')]:
            expected=read(paths[choice]) if choice else None
            assert model_id(kind,key)==(expected['model_id'] if expected else None)
            identity=plan['plan'][role]
            assert (identity['revision'] if identity else None)==(expected['revision'] if expected else None)
        request=dict(kind='pipeline',request_id=str(uuid.uuid4()),input_ids=ids,question=plan['question'],execute=False,
                     llm_config_id=defaults['llm_id'],chunk_config_id=defaults['chunk_id'],retrieval=defaults['retrieval'],
                     embedding_config_id=defaults['embedding_id'] or None,reranker_config_id=defaults['reranker_id'] or None)
        post=urllib.request.Request(origin+'/api/jobs',data=json.dumps(request).encode(),headers={
            'Content-Type':'application/json','X-Rag-Session':boot['session_token']})
        job=json.load(urllib.request.urlopen(post,timeout=10))['data']
        for _ in range(100):
            job=get('/api/jobs/'+job['id'])
            if job['status'] in ('completed','failed'):break
            time.sleep(.1)
        assert job['status']=='completed',job
        actual=get('/api/artifacts/'+job['artifact_ids'][0])['result']
        assert actual['plan']==plan['plan'],(actual['plan'],plan['plan'])
        rows[label]=dict(selection=result['models'],retrieval=result['retrieval'],generation=plan['plan']['generation'],
                         source=plan['plan']['source_fingerprint'],chunk=plan['plan']['chunking'],ui_cli_plans_equal=True)
    finally:
        ui.terminate();ui.wait(timeout=5)
for left,right,field in [('hybrid e5','hybrid bge','embedding'),('hybrid bge','mmini on','reranker'),('mmini on','bge on','reranker')]:
    a,b=rows[left].copy(),rows[right].copy()
    ma,mb=a.pop('selection').copy(),b.pop('selection').copy()
    assert ma.pop(field,None)!=mb.pop(field,None) and ma==mb and a==b
for extra in (['--method','dense'],['--method','bm25','--embedding-config',str(paths['e5'])],
              ['--method','dense','--embedding-config',str(paths['mmini'])],
              ['--method','bm25','--reranker-config',str(paths['e5'])],
              ['--method','dense','--embedding-config','embedding-e5.json'],
              ['--method','bm25','--top-k','13'],['--method','bm25','--context-budget-chars','0']):
    error=run(common+extra+['--out','invalid'],ok=False)
    assert error['status']=='error' and not (ws/'invalid').exists()
old_sha=sha(ws/'bm25 off/search.json')
assert run(common+['--method','bm25','--out','bm25 off'],ok=False)['error']['code']=='output_exists'
assert sha(ws/'bm25 off/search.json')==old_sha and before==[sha(p) for p in protected]
(E/'verified.json').write_text(json.dumps(dict(cases=rows,protected_inputs_sha256=before,
            models='Existing S1 prepared files; no fixture weights',inference_calls=0),ensure_ascii=False,indent=2)+'\n')
print('PASS six installed CLI and UI plans, one-variable comparisons, protected inputs, rejected configurations')
