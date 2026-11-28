"""Exercise the published first-answer command in a fresh first_handbook workspace."""
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
S8 = E.parent/'p032-s8'
sys.path.insert(0,str(S8))
import runtime as rt
read,write,need=rt.read,rt.write,rt.need
base=Path(read(E/'installation.json')['base'])/'rag-lab-first'
ws=base/'practice'
python=base/'env/bin/python'
out=ws/'first-answer'
private=E
rt.E,rt.LEDGER=E,E/'ledger.json'

def frozen():
    from rag_package.llm import core
    from rag_package.rag import answer_schema
    preview=read(ws/'evidence/result.json')
    first=read(base/'first-run.json')
    need(first['generation_calls']==preview['generation_requests']==0 and len(preview['contexts'])==5,'first_search')
    expected=core.preview(read(S8/'profile.json'),'generation',preview['messages'],response_schema=answer_schema(preview['contexts']))
    paths=[p for d in ('snapshot','bm25','documents','evidence') for p in sorted((ws/d).rglob('*')) if p.is_file()]
    return dict(body_hash=core.hash_json(expected['body']),source_sha=first['source_sha'],wheel_sha256=first['wheel_sha256'],
                question=first['question'],input_hashes={str(p.relative_to(ws)):rt.sha(p) for p in paths})

def prepare():
    from unittest.mock import patch
    from rag_package import llm_setup
    from rag_package.llm.transport import TransportError
    os.chdir(ws)
    for name in ['server_off','model_absent']:
        def metadata(method,url,*args):
            need(method=='GET' and url==rt.BASE+'/api/tags','unexpected_request')
            if name=='server_off':raise TransportError('connection_error',outcome_unknown=False)
            return {'models':[]}
        with patch.object(llm_setup,'http_transport',side_effect=metadata),patch('rag_package.llm.invoke',side_effect=AssertionError):
            r=llm_setup.first_handbook_answer()
        need(r['status']=='model_not_ready' and r['generation_requests']==0 and not out.exists(),'missing_model')
        write(E/(name+'.json'),r)
    write(E/'frozen.json',frozen())


def supervise():
    need(frozen()==read(E/'frozen.json'),'input_changed')
    need(not out.exists() and not rt.LEDGER.exists(),'already_started')
    rt.verify_parent=lambda:need(read(E.parent/'p032-s23/budget/server-closed.json')['listener_closed'],'previous_server')
    runpy.run_path(str(S8/'preflight.py'),run_name='__main__')
    client=None
    try:
        with rt.transact(rt.LEDGER) as c:c.claim()
        with (private/'cli.log').open('w') as log:
            client=subprocess.Popen(['../env/bin/rag-lab','first-answer','--execute'],cwd=ws,stdout=log,stderr=log,
                env=dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin',LANG='en_US.UTF-8',PYTHONPATH=str(E/'observer'),PYTHONDONTWRITEBYTECODE='1'))
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
    if Path(sys.executable)!=python:
        os.execv(python,[str(python),'-I',__file__,*sys.argv[1:]])
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='start':supervise()
