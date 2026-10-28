"""Execute committed protocol slots once, retain every response/error. No retries."""
import json,sys,subprocess,time,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p011';s=root/'1. Naive RAG';b=s/'variants/langchain';protocol=json.loads((ev/'protocol.json').read_text());cases={c['id']:c for c in protocol['cases']};out=ev/'runs';out.mkdir(exist_ok=True)
worker=Path(__file__).with_name('worker.py');ledger=ev/'ledger.jsonl'
def run(cid,impl,kind,round,control=None):
 name=f'{kind}-{round:02}-{cid}-{impl}';dest=out/(name+'.json')
 if dest.exists():raise RuntimeError('Refusing overwrite: '+name)
 c=cases[cid];stage=s if impl=='direct' else b;args={k:c[k] for k in ('question','retriever','corpus')}|protocol['settings'];start=time.perf_counter()
 process=subprocess.run([str(stage/'.venv/bin/python'),str(worker),str(stage),impl,json.dumps(args,ensure_ascii=False)],capture_output=True,text=True)
 try:value=json.loads(process.stdout)
 except Exception:value={'worker_error':True,'stdout':process.stdout}
 value.update(slot=name,case_id=cid,kind=kind,round=round,returncode=process.returncode,stderr=process.stderr,client_wall_ms=(time.perf_counter()-start)*1000,control=control)
 dest.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 dispatch=sum(x['url'].endswith('/api/chat') for x in value.get('wire',[]));line=dict(slot=name,dispatches=dispatch,result=value.get('result',{}).get('status','worker_error'),path=str(dest.relative_to(root)))
 with ledger.open('a') as f:f.write(json.dumps(line)+'\n')
 total=sum(json.loads(l)['dispatches'] for l in ledger.read_text().splitlines());print(name,line['result'],round_time(value['client_wall_ms']),'dispatch total',total,flush=True)
 if total>=310:raise RuntimeError('Dispatch safety limit')
def round_time(ms):return f'{ms/1000:.1f}s'
mode=sys.argv[1]
if mode=='warm':
 for impl in ['direct','langchain']:run('q03',impl,'warmup',0)
 for slot in protocol['slots']:run(slot['case_id'],slot['implementation'],'warm',slot['round'])
elif mode=='cold':
 sys.path.insert(0,str(s/'scripts'));import runtime;from runtime_common import LocalAPI
 for r in range(1,4):
  for j,cid in enumerate(protocol['cold_cases']):
   for impl in (['direct','langchain'] if (r+j)%2 else ['langchain','direct']):
    before=runtime.status();assert before['owned'];stopped=runtime.stop();after=runtime.start();ps=LocalAPI().call('/api/ps');assert ps.get('models')==[]
    run(cid,impl,'cold',r,dict(before=before,stopped=stopped,after=after,ps=ps,os_cache_cleared=False))
