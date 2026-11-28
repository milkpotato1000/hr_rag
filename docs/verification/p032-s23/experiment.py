"""Compare frozen S22 contexts with separate, single-dispatch supervised runs."""
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

ROOT = Path(__file__).resolve().parents[3]
REPORT = Path(__file__).resolve().parent
S22 = REPORT.parent/'p032-s22'
S8 = REPORT.parent/'p032-s8'
sys.path.insert(0,str(S8))
import runtime as rt
read,write,need = rt.read,rt.write,rt.need
label = sys.argv[2]
need(label in ('baseline','budget'),'unknown_variant')
E = REPORT/label
installation = read(S22/'installation.json')
base = Path(installation['base'])
ws = base/'practice'
question = read(S22/'inputs.json')['question']
index = ws/label/'index'
private = E
out = base/('s23-answer-'+label)
config = E/'search.json'
rt.E,rt.LEDGER = E,E/'ledger.json'

def prepare():
    E.mkdir(exist_ok=False)
    c=read(ws/label/'search.json')
    c['llm_config']='../../p032-s8/profile.json'
    write(config,c)
    subprocess.run([installation['python'],'-I','-m','rag_package','ask','--run',index,'--config',config,
                    '--question',question,'--out',base/('s23-preview-'+label)],cwd=ws,check=True,stdout=subprocess.DEVNULL)
    preview=read(base/('s23-preview-'+label)/'result.json')
    expected=read(S22/'results.json')[label]
    need(preview['contexts']==expected['contexts'] and preview['retrieval_trace']['bm25']==expected['ranking'],'s22_contexts')
    body=preview['preview']['body']
    passed=json.loads(body['messages'][-1]['content'])
    need(passed['question']==question and [(c['chunk_id'],c['text']) for c in passed['contexts']]==
         [(c['chunk_id'],c['text']) for c in expected['contexts']],'preview_payload')
    write(E/'planned.json',dict(question=question,body=body,context_chars=sum(len(c['text']) for c in passed['contexts']),
          config_hash=rt.sha(config),index_manifest=rt.sha(index/'manifest.json'),profile_hash=rt.sha(S8/'profile.json')))
    if label=='budget':
        other=read(REPORT/'baseline/planned.json')['body']
        def normalized(value):
            value=copy.deepcopy(value)
            del value['format']['properties']['citations']['items']['properties']['chunk_id']['enum']
            value['messages'][-1]['content']=question
            return value
        need(normalized(other)==normalized(body),'model_settings_changed')
        full=read(REPORT/'baseline/search.json')
        need(c==dict(full,retrieval=dict(full['retrieval'],context_budget_chars=400)),'other_config_changed')

def audit():
    frozen=read(E/'planned.json')
    need(rt.sha(config)==frozen['config_hash'] and rt.sha(index/'manifest.json')==frozen['index_manifest'] and
         rt.sha(S8/'profile.json')==frozen['profile_hash'] and rt.sha(Path(installation['wheel']))==installation['wheel_sha256'],'frozen_inputs')
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
    return main(['ask','--run',str(index),'--config',str(config),'--question',question,'--out',str(out),'--execute'])


def supervise():
    need(audit() is not None,'no_context')
    need(not out.exists() and not rt.LEDGER.exists(),'already_started')
    previous=REPORT/'baseline' if label=='budget' else REPORT.parent/'p032-s19'
    rt.verify_parent=lambda:need(read(previous/'server-closed.json')['listener_closed'] and read(previous/'ledger.json')['status']=='complete','previous_gate')
    runpy.run_path(str(S8/'preflight.py'),run_name='__main__')
    client=None
    try:
        with rt.transact(rt.LEDGER) as c:c.claim()
        with (private/'cli.log').open('w') as log:
            client=subprocess.Popen([sys.executable,'-I',__file__,'worker',label],cwd=ws,stdout=log,stderr=log)
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
    result=read(out/'result.json')
    write(E/'result.json',result)
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
