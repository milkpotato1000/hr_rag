"""One installed, supervised partition choice on the complete S16 PDF."""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time

E = Path(__file__).resolve().parent
S8 = E.parent/'p032-s8'
S16 = E.parent/'p032-s16'
sys.path.insert(0,str(S8))
import runtime as rt

install = rt.read(E/'installation.json')
base = Path(install['base'])
python = Path(install['python'])
prior = Path(rt.read(S16/'installation.json')['base'])/'practice'
preset = prior/'내 문서 실습'
snap = prior/'내 문서 실습-preview/snapshot'
expected = rt.read(S16/'verified.json')
config = E/'config.json'
out = base/'selected'
rt.E, rt.LEDGER = E, E/'ledger.json'


def audit():
    from rag_package import chunk_artifact
    from rag_package.llm.core import hash_json
    sm, docs, _, _, _, _, windows = chunk_artifact.preflight(snap,config)
    rt.need(len(docs)==1 and docs[0]['text']==expected['text'] and sm['fingerprint']==expected['selected_source_fingerprint'],'source_changed')
    rt.need(rt.sha(preset/'original.pdf')==expected['selected']['selected_document']['original_sha256'],'pdf')
    rt.need(len(windows)==1,'window_count')
    w=windows[0]
    parent=E.parent/'p032-s18'
    s18=rt.read(parent/'frozen.json')
    previous=chunk_artifact.preflight(snap,parent/'config.json')[-1][0]
    old_body=previous['request']['body']
    body=w['request']['body']
    rt.need(hash_json(old_body)==s18['body_hash']==rt.read(parent/'ledger.json')['requests'][0]['body_hash'],'parent_body')
    schema={'type':'object','properties':{'candidate_id':{'type':'string','enum':['1','2']}},
            'additionalProperties':False,'required':['candidate_id']}
    rt.need(old_body['format']==body['format']==schema and body==dict(old_body,messages=body['messages']), 'options')
    rt.need(old_body['messages'][0]==body['messages'][0] and len(body['messages'])==2,'system')
    rt.need(w['candidates']==s18['candidates'], 'candidate_identity')
    data=json.loads(body['messages'][1]['content'])
    texts=[u['text'] for u in data['units']]
    rt.need([u['number'] for u in data['units']]==list(range(1,len(texts)+1)) and ''.join(texts)==expected['text'],'units')
    for compact,candidate in zip(data['candidates'],w['candidates'],strict=True):
        end=compact['end_unit_numbers']
        parts=[''.join(texts[a:b]) for a,b in zip([0]+end[:-1],end)]
        rt.need(compact['id']==candidate['id'] and parts==[p['text'] for p in candidate['pieces']], 'reconstruction')
    ends=[]
    for c in w['candidates']:
        parts=c['pieces']
        rt.need(''.join(i['text'] for i in parts)==expected['text'],'coverage')
        rt.need(all(i['text']==expected['text'][i['start']:i['end']] and len(i['text'])<=150 for i in parts),'offset')
        ends.append([i['end'] for i in parts])
    rt.need(ends==[[141,202],[103,202]],'section_choice')
    rt.need(rt.sha(Path(install['wheel']))==install['wheel_sha256'],'wheel')
    for path,h in install['wheel_payload_hashes'].items():
        rt.need(rt.sha(base/'env/lib/python3.12/site-packages'/path)==h,'installed_payload')
    return w,dict(pdf_sha256=rt.sha(preset/'original.pdf'),source_text=docs[0]['text'],source_hash=sm['fingerprint'],
                  old_input_bytes=len(old_body['messages'][1]['content'].encode()),new_input_bytes=len(body['messages'][1]['content'].encode()),
                  input=data,candidates=w['candidates'],parent_body_hash=s18['body_hash'],format=schema,messages_hash=w['request']['actual_messages_hash'],request_fingerprint=w['request']['request_fingerprint'],body_hash=hash_json(body),wheel_sha256=install['wheel_sha256'])


def prepare():
    from rag_package import chunk_artifact,pipeline
    pdf_lib=prior.parent/'env/lib/python3.12/site-packages'
    for name in ('pypdf','pypdf-6.21.2.dist-info'):
        shutil.copytree(pdf_lib/name,base/'env/lib/python3.12/site-packages'/name)
    w,frozen=audit()
    preview=chunk_artifact.build(snap,config,base/'chunk-preview')
    plan=pipeline.run(preset/'sources.json',config,preset/'search.json',expected['question'],base/'pipeline-preview')['plan']
    assert preview['requests'][0]['candidates']==plan['partition_windows'][0]['candidates']==w['candidates']
    assert plan['work_upper_bounds']['boundary_llm_requests']==1
    rt.write(E/'frozen.json',frozen)


def worker():
    from rag_package import chunk_artifact
    from rag_package.llm.core import hash_json
    w,frozen=audit()
    rt.need(frozen==rt.read(E/'frozen.json'),'freeze')
    original=chunk_artifact.http_transport
    def bounded(method,url,headers,body,timeout):
        if method=='GET' and url==rt.BASE+'/api/tags':
            return rt.metadata('/api/tags',actor='adapter')
        rt.need((method,url,timeout)==('POST',rt.BASE+'/api/chat',480) and body==w['request']['body'],'dispatch')
        with rt.transact(rt.LEDGER) as state:
            state.reserve('first',hash_json(body),frozen['body_hash'],rt.read(E/'health.json'))
        result=original(method,url,headers,body,timeout)
        with rt.transact(rt.LEDGER) as state:state.response('first')
        return result
    chunk_artifact.http_transport=bounded
    result=chunk_artifact.build(snap,config,out,execute=True)
    rt.write(E/'result.json',result)
    return 0 if result['status']=='ready' else 1


def supervise():
    _,frozen=audit()
    rt.need(frozen==rt.read(E/'frozen.json') and not rt.LEDGER.exists() and not out.exists(),'new_run')
    rt.verify_parent=lambda:rt.need(all(rt.read(E.parent/stage/'ledger.json')['status']=='halted' for stage in ('p032-s2i','p032-s2j','p032-s17','p032-s18')),'prior_status')
    runpy.run_path(str(S8/'preflight.py'),run_name='__main__')
    client=None
    try:
        with rt.transact(rt.LEDGER) as state:state.claim()
        client=subprocess.Popen([str(python),'-I',__file__,'worker'],cwd=base)
        def check():
            with rt.transact(rt.LEDGER) as state:state.check()
        rt.observe_client(client,check=check)
    finally:
        rt.reap_owned_client(client)
        deadline=time.monotonic()+60
        while rt.current_models(True)['models']:
            rt.need(time.monotonic()<deadline,'unload_timeout')
            rt.append_sample(rt.sample())
            time.sleep(5)
        rt.normal_window()
        rt.write(E/'first-observation.json',dict(unloaded_observed=True,client_reaped=True))
        runpy.run_path(str(S8/'close_server.py'),run_name='__main__')
    with rt.transact(rt.LEDGER) as state:
        if client.returncode:
            state.halt('chunking_failed')
        else:
            state.finish('first',True,True,True)
            state.s['status']='complete'


if __name__=='__main__':
    if Path(sys.executable)!=python:
        os.execv(python,[str(python),'-I',__file__,*sys.argv[1:]])
    os.chdir(base)
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='start':supervise()
    elif sys.argv[1]=='worker':sys.exit(worker())
