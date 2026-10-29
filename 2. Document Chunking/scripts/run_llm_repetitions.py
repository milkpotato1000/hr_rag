#!/usr/bin/env python3
"""Independent whole-corpus LLM runs; durable progress and failed attempts retained."""
import argparse,time,json
from pathlib import Path
from chunk_core import build
from experiment_common import ARTIFACTS,RUNTIME,new_id,work_lock,save_state
from document_common import read_json,write_json,atomic_directory
from model_runtime import Provider

def one(provider=None,progress=lambda x:None):
    provider=provider or Provider();rid=new_id('chunk');out=ARTIFACTS/rid;latest={};started=time.monotonic();before=provider.ledger.refresh()['llm_seconds']
    def update(value):
        latest.update(value);save_state(RUNTIME/'progress'/f'{rid}.json',dict(run_id=rid,**latest));progress(dict(run_id=rid,**latest))
    try:return build('llm-0',out,provider=provider,on_progress=update)
    except BaseException as exc:
        if not out.exists():
            with atomic_directory(out) as target:
                write_json(target/'attempts.json',latest);write_json(target/'manifest.json',dict(schema_version=1,run_id=rid,status='interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',reason=getattr(exc,'kind','execution'),error=str(exc),config={'id':'llm-0'},elapsed_ms=(time.monotonic()-started)*1000))
        raise
    finally:
        state=provider.ledger.refresh();used=state['llm_seconds']-before;extra=max(0,time.monotonic()-started-used);state['llm_seconds']+=extra
        state.setdefault('invocation_overhead',[]).append(dict(run_id=rid,seconds=extra));save_state(provider.ledger.path,state)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--count',type=int,choices=[1,2,3],default=3);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();a.output_dir.mkdir(exist_ok=False);rows=[]
    with work_lock():
        provider=Provider();provider.verify()
        for n in range(a.count):
            print('Starting independent corpus run',n+1,flush=True)
            def update(v):
                if v['completed_windows'] and len(v['records'])==v['completed_windows']:
                    print('run',n+1,'window',v['completed_windows'],'/',v['total_windows'],'seconds',round(v['elapsed_seconds'],1),flush=True)
            try:
                m=one(provider,update);rows.append(dict(status='complete',run_id=m['run_id'],elapsed_ms=m['elapsed_ms']))
            except Exception as e:
                rows.append(dict(status='failed',error=str(e),reason=getattr(e,'kind','execution')))
                if getattr(e,'kind','') in ('provider_unresolved','budget_exhausted'):break
            save_state(a.output_dir/'repetitions.json',dict(requested=a.count,runs=rows,cache_used=False,first_valid_run=next((r['run_id'] for r in rows if r['status']=='complete'),None)))
        write_json(a.output_dir/'ledger-after.json',provider.ledger.refresh())
    return 0 if len(rows)==a.count and all(r['status']=='complete' for r in rows) else 2
if __name__=='__main__':raise SystemExit(main())
