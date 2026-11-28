"""Use S8's actual identity, dispatch accounting, monitoring and ownership controls."""
from pathlib import Path
import os, runpy, signal, subprocess, sys, time
E = Path(__file__).resolve().parent
s8 = E.parent/'p032-s8'
sys.path.insert(0,str(s8))
import runtime as rt
rt.E = E
rt.LEDGER = E/'ledger.json'
cfg = rt.read(E/'setup.json')
ws = Path(cfg['practice'])
if sys.argv[1] == 'serve':
    from rag_package.llm import core
    from rag_package.__main__ import main
    original = core.http_transport
    def bounded(method,url,headers,body,timeout):
        if method=='GET' and url==rt.BASE+'/api/tags':
            return rt.metadata('/api/tags',actor='adapter')
        rt.need(method=='POST' and url==rt.BASE+'/api/chat' and timeout==480,'invalid_dispatch')
        payload=rt.json.loads(body['messages'][-1]['content'])
        rt.need(payload['question']==cfg['question'] and any(cfg['quote'] in c['text'] and 'BD-03' in c['text'] for c in payload['contexts']),'unexpected_context')
        rt.write(E/'dispatch.json',dict(question=payload['question'],contexts=payload['contexts'],at=time.time()))
        h=core.hash_json(body)
        with rt.transact(rt.LEDGER) as c:c.reserve('first',h,h,rt.read(E/'health.json'))
        raw=original(method,url,headers,body,timeout)
        with rt.transact(rt.LEDGER) as c:c.response('first')
        return raw
    core.http_transport=bounded
    os.chdir(ws)
    sys.exit(main(['serve','--workspace','.', '--sources','handbook-sources.json','--llm-config','handbook-model.json','--chunk-config','chunk-fixed.json','--allow-model-execution','--port','18791']))
if sys.argv[1]=='start':
    rt.verify_parent=lambda:rt.need(rt.read(s8/'server-closed.json')['listener_closed'],'previous_server')
    runpy.run_path(str(s8/'preflight.py'),run_name='__main__')
    with rt.transact(rt.LEDGER) as c:c.claim()
    client=subprocess.Popen([cfg['python'],'-I','-u',__file__,'serve'],cwd=ws)
    try:
        last=0
        while client.poll() is None:
            state=rt.read(rt.LEDGER)
            rt.append_sample(rt.sample())
            if state['requests'] and not state['requests'][0]['response_received']:
                rt.watchdog(time.time()-state['requests'][0]['reserved_at'])
                if time.monotonic()-last>=5:
                    rt.current_models(True)
                    last=time.monotonic()
            if (E/'release').exists():break
            time.sleep(1)
    finally:
        rt.reap_owned_client(client)
        loaded=rt.current_models()
        rt.normal_window()
        rt.write(E/'first-observation.json',dict(unloaded_observed=not loaded['models'],client_reaped=True))
        runpy.run_path(str(s8/'close_server.py'),run_name='__main__')
