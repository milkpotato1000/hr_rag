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
S8 = E.parent/'p032-s8'
S16 = E.parent/'p032-s16'
S25 = E.parent/'p032-s25'
ROOT = E.parents[2]
sys.path.insert(0,str(S8))
import runtime as rt
read,write,need=rt.read,rt.write,rt.need
base=Path(read(S25/'installation.json')['base'])
python=base/'rag-lab-first/env/bin/python'
ws=base/'selected-pdf-s26'
out=ws/'actual'
private=E
rt.E,rt.LEDGER=E,E/'ledger.json'
reference=read(S16/'verified.json')
question=reference['question']
pdf=ROOT/'2. Document Chunking/data/source-v3/output/pdf/training.pdf'

def cli(args):
    import contextlib,io
    from rag_package.__main__ import main
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):code=main(args)
    result=json.loads(buf.getvalue())
    need(code==0,str(result.get('error','cli_failure')))
    return result

def selected(profile,folder):
    return cli(['pipeline-setup','--llm-config',profile,'--chunk-config','chunk-fixed.json','--method','bm25',
        '--document',str(pdf),'--title','자격시험 교육 휴가 규정','--synthetic','--question',question,'--out',folder])

def arguments(selection,destination,execute=False):
    import shlex
    cmd=shlex.split(selection['commands']['pipeline_preview'])
    need(cmd[:2]==['rag-lab','pipeline'],'preview_entry')
    cmd[cmd.index('--out')+1]=destination
    return cmd[1:]+(['--execute'] if execute else [])

def inputs():
    first=base/'rag-lab-first/practice'
    return {'selected_pdf':rt.sha(pdf),'default_pdf':rt.sha(ws/'documents/handbook.pdf'),
        'default_answer':rt.sha(first/'first-answer/answer/result.json'),'default_index':rt.sha(first/'bm25/manifest.json')}

def prepare():
    from rag_package import pipeline
    cli(['init','--out',str(ws)])
    os.chdir(ws)
    shutil.copyfile(S8/'profile.json','historical.json')
    selection=selected('historical.json','offline-selection')
    cmd=arguments(selection,'fixture',True)
    def fixture(method,url,headers,body,timeout):
        if method=='GET':return {'models':[{'name':'qwen3:4b','digest':rt.DIGEST}]}
        return {'model':'qwen3:4b','done':True,'done_reason':'stop','message':{'role':'assistant',
            'content':json.dumps(dict(status='abstained',answer='fixture',citations=[]))}}
    from unittest.mock import patch
    from rag_package.llm import core
    with patch.object(core,'http_transport',fixture):cli(cmd)
    result=read(ws/'fixture/answer/result.json')
    need(result['source_fingerprint']==reference['selected_source_fingerprint'] and result['question']==question,'s16_identity')
    need(len(result['contexts'])==1 and result['contexts'][0]['text']==reference['text'],'s16_context')
    need(inputs()['selected_pdf']==reference['selected']['selected_document']['original_sha256'] and
         inputs()['default_pdf']==reference['default_pdf_sha256'],'pdf_identity')
    write(E/'planned.json',dict(body=result['preview']['body'],inputs=inputs(),question=question,document_id=result['contexts'][0]['document_id']))

def audit():
    frozen=read(E/'planned.json')
    need(frozen['inputs']==inputs(),'protected_input_changed')
    return frozen['body']

def worker():
    from rag_package import llm_setup
    from rag_package.llm import core
    expected=audit()
    original=core.http_transport
    def bounded(method,url,headers,body,timeout):
        if method=='GET' and url==rt.BASE+'/api/tags':return rt.metadata('/api/tags',actor='adapter')
        if method=='POST' and url==rt.BASE+'/api/show' and body=={'model':'qwen3:4b'}:
            return rt.metadata('/api/show',body,actor='adapter')
        need((method,url,timeout)==('POST',rt.BASE+'/api/chat',480) and body==expected,'unexpected_dispatch')
        with rt.transact(rt.LEDGER) as c:c.reserve('first',core.hash_json(body),core.hash_json(expected),read(E/'health.json'))
        raw=original(method,url,headers,body,timeout)
        with rt.transact(rt.LEDGER) as c:c.response('first')
        return raw
    os.chdir(ws)
    llm_setup.http_transport=core.http_transport=bounded
    cli(['generation-setup','--provider','ollama','--model','qwen3:4b','--inspect-local','--out','my-local'])
    model=read(ws/'my-local/model.json')
    profile=model['profiles'][model['roles']['generation']]
    need(profile['identity']['expected_digest']==rt.DIGEST,'generation_digest')
    selection=selected('my-local/model.json','내 문서 실습')
    preview=cli(arguments(selection,'selected-preview'))
    plan=preview['plan']
    need(plan['source_fingerprint']==reference['selected_source_fingerprint'] and
        plan['source_fingerprint']!=reference['default_source_fingerprint'] and
        preview['question']==question and plan['retrieval']['method']=='bm25' and plan['reranker'] is None and
        plan['generation_profile']==profile,'preview_mismatch')
    write(E/'selection.json',selection)
    write(E/'preview.json',preview)
    actual=cli(arguments(selection,'actual',True))
    return 0 if actual['status'] in ('answered','abstained') else 1


def supervise():
    need(audit() is not None,'no_context')
    need(not out.exists() and not rt.LEDGER.exists(),'already_started')
    rt.verify_parent=lambda:need(read(S25/'server-closed.json')['listener_closed'],'previous_server')
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
    if Path(sys.executable)!=python:
        os.execv(python,[str(python),'-I',__file__,*sys.argv[1:]])
    if sys.argv[1]=='worker':raise SystemExit(worker())
    if sys.argv[1]=='start':supervise()
    elif sys.argv[1]=='prepare':prepare()
    else:audit()
