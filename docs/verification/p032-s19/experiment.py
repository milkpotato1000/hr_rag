"""Bound one installed handbook generation against the approved gt09 question."""
from pathlib import Path
import copy
import importlib.metadata
import json
import os
import runpy
import shutil
import subprocess
import sys
import time

E = Path(__file__).resolve().parent
S11 = E.parent/'p032-s11'
S8 = E.parent/'p032-s8'
S18 = E.parent/'p032-s18'
ROOT = E.parents[2]
sys.path.insert(0,str(S8))
import runtime as rt
read,write,need=rt.read,rt.write,rt.need
installation=read(S18/'installation.json')
base=Path(installation['base'])
ws=base/'s19-practice'
out=ws/'actual'
private=E
rt.E,rt.LEDGER=E,E/'ledger.json'
question='재택근무 전기요금의 월 지원 한도는 얼마인가요?'
review=ROOT/'docs/planning/reviews/P013-human-review.md'


def inputs():
    paths=['documents/handbook.pdf','chunk-fixed.json','handbook-sources.json','handbook-local.json','handbook-model.json']
    return {name:rt.sha(ws/name) for name in paths} | {'human_review':rt.sha(review),'s11_result':rt.sha(S11/'result.json')}


def prepare():
    from rag_package import pipeline,workspace
    workspace.init(ws)
    shutil.copyfile(S8/'profile.json',ws/'handbook-model.json')
    # Capture the general pipeline's prompt with no real transport or model.
    def fixture(method,url,headers,body,timeout):
        if method=='GET':return {'models':[{'name':'qwen3:4b','digest':rt.DIGEST}]}
        need(method=='POST' and url==rt.BASE+'/api/chat','unexpected_fixture_transport')
        return {'model':'qwen3:4b','done':True,'done_reason':'stop','message':{'role':'assistant',
                'content':json.dumps({'status':'abstained','answer':'fixture','citations':[]})}}
    plan=pipeline.run(ws/'handbook-sources.json',ws/'chunk-fixed.json',ws/'handbook-local.json',question,
                      ws/'fixture',execute=True,transport=fixture)
    need(plan['status']=='abstained','fixture_setup')
    result=read(ws/'fixture/answer/result.json')
    body=result['preview']['body'] if result['contexts'] else None
    parent=read(S11/'result.json')
    need(parent['source_fingerprint']==result['source_fingerprint'] and '### gt09 · '+question in review.read_text(),'source_review')
    need(inputs()['documents/handbook.pdf']==read(E.parent/'p032-s10/verified.json')['pdf_sha256'],'pdf_changed')
    old_ws=Path(read(S11/'setup.json')['practice'])
    for name,h in inputs().items():
        if name not in ('human_review','s11_result'):need(rt.sha(old_ws/name)==h,'s11_inputs_changed')
    need(plan['plan']['retrieval']==dict(method='bm25',candidate_k=20,top_k=5,context_budget_chars=4000,rrf_k=60) and plan['plan']['reranker'] is None,'search_config')
    if body:
        old=copy.deepcopy(parent['preview']['body'])
        def general(payload):
            value=copy.deepcopy(payload)
            prompt=json.loads(value['messages'][-1]['content'])
            need(set(prompt)=={'question','contexts'},'unexpected_prompt_fields')
            value['messages'][-1]['content']='question_and_contexts'
            del value['format']['properties']['citations']['items']['properties']['chunk_id']['enum']
            return value
        need(general(old)==general(body),'generation_settings')
        payload=json.loads(body['messages'][-1]['content'])
        need(payload['question']==question and [c['text'] for c in payload['contexts']]==[c['text'] for c in result['contexts']],'prompt_context')
    write(E/'planned.json',dict(question=question,source_fingerprint=result['source_fingerprint'],inputs=inputs(),
        wheel_sha256=installation['wheel_sha256'],contexts=result['contexts'],body=body))


def audit():
    frozen=read(E/'planned.json')
    need(inputs()==frozen['inputs'] and rt.sha(Path(installation['wheel']))==frozen['wheel_sha256'],'frozen_inputs')
    for name,h in installation['wheel_payload_hashes'].items():
        need(rt.sha(base/'env/lib/python3.12/site-packages'/name)==h,'installed_package')
    return frozen['body']


def worker():
    from rag_package.__main__ import main
    from rag_package.llm import core
    expected = audit()
    original = core.http_transport
    def bounded(method,url,headers,body,timeout):
        if method=='GET' and url==rt.BASE+'/api/tags':
            return rt.metadata('/api/tags',actor='adapter')
        need((method,url,timeout)==('POST',rt.BASE+'/api/chat',480),'unexpected_dispatch')
        need(body==expected,'request_mismatch')
        with rt.transact(rt.LEDGER) as c:
            c.reserve('first',core.hash_json(body),core.hash_json(expected),read(private/'health.json'))
        write(E/'dispatch.json',dict(body_hash=core.hash_json(body),user_payload=json.loads(body['messages'][-1]['content'])))
        raw=original(method,url,headers,body,timeout)
        with rt.transact(rt.LEDGER) as c:c.response('first')
        return raw
    core.http_transport=bounded
    os.chdir(ws)
    return main(['pipeline','--sources','handbook-sources.json','--chunk-config','chunk-fixed.json',
                 '--search-config','handbook-local.json','--question',question,'--out',str(out),'--execute'])


def supervise():
    need(audit() is not None,'no_context')
    need(not out.exists() and not rt.LEDGER.exists(),'already_started')
    rt.verify_parent=lambda:need(read(S11/'server-closed.json')['listener_closed'],'previous_server')
    runpy.run_path(str(S8/'preflight.py'),run_name='__main__')
    client=None
    try:
        with rt.transact(rt.LEDGER) as c:c.claim()
        with (private/'cli.log').open('w') as log:
            client=subprocess.Popen([sys.executable,'-I',__file__,'worker'],cwd=ws,stdout=log,stderr=log)
            def check():
                with rt.transact(rt.LEDGER) as c:c.check()
            rt.observe_client(client,check=check)
    finally:
        rt.reap_owned_client(client)
        deadline=time.monotonic()+60
        while rt.current_models(True)['models']:
            need(time.monotonic()<deadline,'unload_timeout')
            rt.append_sample(rt.sample())
            time.sleep(5)
        rt.normal_window()
        write(private/'first-observation.json',dict(unloaded_observed=True,client_reaped=True))
        runpy.run_path(str(S8/'close_server.py'),run_name='__main__')
    result=read(out/'answer/result.json')
    ok=(client.returncode==0 and result['status'] in ('answered','abstained') and
        result['provider_result']['identity_verification']['status']=='verified')
    with rt.transact(rt.LEDGER) as c:
        if ok:
            c.finish('first',True,True,True)
            c.s['status']='complete'
        else:c.halt('generation_failed')
    need(ok,'generation_failed')


if __name__=='__main__':
    python=Path(installation['python'])
    if Path(sys.executable)!=python:
        os.execv(python,[str(python),'-I',__file__,*sys.argv[1:]])
    if sys.argv[1]=='worker':raise SystemExit(worker())
    if sys.argv[1]=='start':supervise()
    elif sys.argv[1]=='prepare':prepare()
    else:audit()
