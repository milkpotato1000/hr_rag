"""Bound one recursive local generation against frozen S11 and S12 inputs."""
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
S12 = E.parent/'p032-s12'
S8 = E.parent/'p032-s8'
sys.path.insert(0,str(S8))
import runtime as rt
read, write, need = rt.read, rt.write, rt.need
installation = read(S12/'installation.json')
base = Path(installation['base'])
ws = base/'practice'
private = base/'s13-control'
private.mkdir(exist_ok=True)
rt.E, rt.LEDGER = private, private/'ledger.json'
old = Path(read(S11/'setup.json')['practice'])/'.rag-runs/ui/artifacts'/read(S11/'live-job.json')['id']/'result'
out = ws/'s13-recursive'
question = read(S11/'setup.json')['question']
quote = read(S11/'review.json')['source_quote']


def normalized(body):
    value = copy.deepcopy(body)
    prompt = json.loads(value['messages'][-1]['content'])
    ids = [c['chunk_id'] for c in prompt.pop('contexts')]
    allowed = value['format']['properties']['citations']['items']['properties']['chunk_id'].pop('enum')
    need(ids == allowed and len(ids)==5, 'citation_scope')
    value['messages'][-1]['content'] = prompt
    return value


def audit():
    from rag_package import pipeline
    from rag_package.llm.core import hash_json
    baseline = pipeline.replay(old)
    fixed = read(old/'answer/result.json')
    need(fixed == read(S11/'result.json') and baseline['answer']==fixed['answer'],'baseline_changed')
    prior = read(S11/'ledger.json')['requests']
    need(len(prior)==1 and prior[0]['status']=='complete' and hash_json(fixed['preview']['body'])==prior[0]['body_hash'],'baseline_dispatch')
    fixture = pipeline.replay(ws/'recursive')
    need(fixture['execution_kind']=='test_fixture','expected_fixture')
    expected = read(ws/'recursive/answer/result.json')['preview']['body']
    plan = baseline['plan']
    need(fixture['question']==baseline['question']==question,'question')
    config = read(ws/'chunk-recursive.json')
    need(config==dict(plan['chunking'],method='recursive') and config==fixture['plan']['chunking'],'chunk_config')
    for key in ['source_fingerprint','retrieval','embedding','reranker','generation']:
        need(fixture['plan'][key]==plan[key],key)
    actual_pdf = rt.sha(ws/'documents/handbook.pdf')
    need(actual_pdf==rt.sha(old/'snapshot/handbook/original.pdf')==read(E.parent/'p032-s10/verified.json')['pdf_sha256'],'pdf')
    need(normalized(expected)==normalized(fixed['preview']['body']),'request_options')
    need(read(ws/'handbook-model.json')==read(S8/'profile.json') and rt.DIGEST==read(S11/'identity-observed.json')['selected_models'][0]['digest'],'model')
    need(rt.sha(Path(installation['wheel']))==installation['wheel_sha256'],'installed_wheel')
    for name,h in installation['wheel_payload_hashes'].items():
        need(rt.sha(base/'env/lib/python3.12/site-packages'/name)==h,'installed_payload')
    write(E/'inputs.json',dict(question=question,question_hash=rt.hashlib.sha256(question.encode()).hexdigest(),pdf_sha256=actual_pdf,
         parent_manifest_sha256=rt.sha(old/'manifest.json'),parent_report_sha256=rt.sha(S11/'result.json'),
         source_fingerprint=plan['source_fingerprint'],retrieval=plan['retrieval'],fixed=plan['chunking'],recursive=config,
         digest=rt.DIGEST,normalized_request_hash=hash_json(normalized(expected)),options=expected['options'],
         system_prompt_sha256=rt.hashlib.sha256(expected['messages'][0]['content'].encode()).hexdigest(),
         parent_body_sha256=prior[0]['body_hash'],expected_recursive_body_sha256=hash_json(expected),
         package_version=importlib.metadata.version('milkpotato-rag-lab'),wheel_sha256=installation['wheel_sha256'],
         baseline_wheel_sha256=read(S11/'setup.json')['wheel_sha256']))
    return expected


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
        raw=original(method,url,headers,body,timeout)
        with rt.transact(rt.LEDGER) as c:c.response('first')
        return raw
    core.http_transport=bounded
    os.chdir(ws)
    return main(['pipeline','--sources','handbook-sources.json','--chunk-config','chunk-recursive.json',
                 '--search-config','handbook-local.json','--question',question,'--out',str(out),'--execute'])


def supervise():
    audit()
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
    else:audit()
