"""Attach the S8 ownership ledger to the exact installed CLI for this experiment."""
import os
from pathlib import Path
import sys
try:
    evidence=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(evidence.parent/'p032-s8'))
    import runtime as rt
    from rag_package import llm_setup
    from rag_package.llm import core
    rt.E,rt.LEDGER=evidence,evidence/'ledger.json'
    expected=rt.read(evidence/'frozen.json')['body_hash']
    original=core.http_transport
    def observed(method,url,headers,body,timeout):
        if method=='GET' and url==rt.BASE+'/api/tags':
            return rt.metadata('/api/tags',actor='adapter')
        if method=='POST' and url==rt.BASE+'/api/show' and body=={'model':'qwen3:4b'}:
            return rt.metadata('/api/show',body,actor='adapter')
        rt.need((method,url,timeout)==('POST',rt.BASE+'/api/chat',480),'unexpected_request')
        with rt.transact(rt.LEDGER) as c:c.reserve('first',core.hash_json(body),expected,rt.read(evidence/'health.json'))
        raw=original(method,url,headers,body,timeout)
        with rt.transact(rt.LEDGER) as c:c.response('first')
        return raw
    core.http_transport=observed
    llm_setup.http_transport=observed
except BaseException:
    os._exit(78)
