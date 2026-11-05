"""P013 durable sequential ledger and loopback-only, bounded model runner."""
import fcntl
import json
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from urllib import request, error
from evaluator import read, write, loads, digest, sha, resolve, payload, MODEL, DIGEST, PACKET
from freeze import approval_check


def verify(manifest_path):
    manifest_path=Path(manifest_path); out=manifest_path.parent; m=read(manifest_path)
    if m['schema_version']!='p013-manifest-v1' or digest({k:v for k,v in m.items() if k!='manifest_sha256'})!=m['manifest_sha256']: raise ValueError('manifest changed')
    for name,h in m['files'].items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or not (out/p).is_file() or sha((out/p).read_bytes())!=h: raise ValueError('frozen file changed: '+name)
    a,p=approval_check(out/'inputs')
    if p['packet_sha256']!=PACKET: raise ValueError('wrong GT version')
    for c in read(out/'cases.json'):
        if c['payload']!=payload(c['role'],c['data']) or digest(c['payload'])!=c['payload_sha256']: raise ValueError('dispatch payload/isolation mismatch')
    return m


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args): return None


def http(route, body=None, timeout=10):
    if route not in ('version','tags','ps','show','chat'): raise ValueError('unsupported local API route')
    data=json.dumps(body,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode() if body is not None else None
    op=request.build_opener(request.ProxyHandler({}),NoRedirect())
    req=request.Request('http://127.0.0.1:11434/api/'+route,data=data,headers={'Content-Type':'application/json'})
    with op.open(req,timeout=timeout) as r: result=loads(r.read().decode())
    if not isinstance(result,dict) or result.get('error'): raise ValueError('provider error')
    return result


def memory_sample():
    rows=subprocess.check_output(['ps','-axo','pid=,rss=,comm='],text=True)
    rss=sum(int(line.split(None,2)[1])*1024 for line in rows.splitlines() if 'ollama' in line.lower())
    pressure=int(subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True).strip())
    return dict(at=time.time(),ollama_rss_bytes=rss,pressure_level=pressure,stop=rss>12*1024**3 or pressure>=4)


def runtime_check(out):
    lock=read(out/'inputs/docs/verification/p019/model-lock.json')
    version=http('version'); tags=http('tags'); running=http('ps')
    if version.get('version')!='0.40.8': raise ValueError('runtime version mismatch')
    if {m['name']:m['digest'] for m in tags['models']}.get(MODEL)!=DIGEST: raise ValueError('model digest mismatch')
    if running['models']: raise ValueError('concurrent model loaded; no eviction')
    show=http('show',dict(model=MODEL,verbose=True))
    params=lambda s:sorted(tuple(line.split(None,1)) for line in s.splitlines() if line.strip())
    if show['template']!=lock['template'] or show.get('system') or params(show['parameters'])!=params(lock['parameters']): raise ValueError('template/parameters mismatch')
    if sha(json.dumps(show['model_info'],sort_keys=True))!=lock['model_info_sha256']: raise ValueError('tokenizer/model metadata mismatch')
    if sha(show['license'])!=lock['license_sha256']: raise ValueError('model license changed')
    if shutil.disk_usage(out).free<10*1024**3: raise ValueError('less than 10 GiB free')
    sample=memory_sample()
    if sample['stop']: raise ValueError('memory threshold/critical pressure')
    return dict(version=version,tags=tags,memory=sample,free_disk_bytes=shutil.disk_usage(out).free,template_sha256=sha(show['template']),model_info_sha256=lock['model_info_sha256'])


class Ledger:
    def __init__(self,out,manifest):
        self.out=Path(out); self.path=self.out/'ledger.json';self.manifest=manifest
        if not self.path.exists(): write(self.path,dict(manifest_sha256=manifest,calls=[],pending=None,unresolved=False,started_at=None))

    def state(self):
        s=read(self.path)
        if s['manifest_sha256']!=self.manifest or [c['sequence'] for c in s['calls']]!=list(range(1,len(s['calls'])+1)): raise ValueError('ledger identity changed')
        if len({c['case_id'] for c in s['calls']})!=len(s['calls']): raise ValueError('duplicate request/no retry')
        for c in s['calls']:
            if sha((self.out/c['artifact']).read_bytes())!=c['artifact_sha256']: raise ValueError('call artifact changed')
        return s

    def reserve(self,case):
        s=self.state();now=time.time()
        if s['pending'] or s['unresolved']: raise ValueError('unresolved request; no automatic retry')
        if any(c['case_id']==case['id'] for c in s['calls']): raise ValueError('request already dispatched')
        if len(s['calls'])>=304 or sum(c['stage']==case['stage'] for c in s['calls'])>={'extraction':16,'judge':68,'e2e':220}[case['stage']]: raise ValueError('request budget exhausted')
        if s['started_at'] is not None and now-s['started_at']>=14400: raise ValueError('wall cap exhausted')
        s['started_at']=s['started_at'] or now
        event=dict(sequence=len(s['calls'])+1,case_id=case['id'],stage=case['stage'],role=case['role'],payload_sha256=case['payload_sha256'],started_at=now)
        s['pending']=event;write(self.path,s,immutable=False)
        return event,min(180,14400-(now-s['started_at']))

    def finish(self,event,result,unresolved=False):
        s=self.state()
        if s['pending']!=event: raise ValueError('reservation mismatch')
        name=f"calls/{event['sequence']:03d}.json";write(self.out/name,result)
        s['calls'].append(dict(event,artifact=name,artifact_sha256=sha((self.out/name).read_bytes()),status=result['status']))
        s['pending']=None;s['unresolved']=unresolved;write(self.path,s,immutable=False)


def invoke(out,ledger,case):
    verify(out/'manifest.json')
    # Check the actual installed vocabulary/template; count the rendered payload.
    runtime=runtime_check(out)
    import gzip
    from tokenization import QwenTokenizer
    show=loads(gzip.decompress((out/'inputs/docs/verification/p019/model-show.json.gz').read_bytes()).decode())
    count=QwenTokenizer(show['model_info']).count(case['payload']['messages'])
    if count!=case['input_tokens'] or count>case['input_limit']: raise ValueError('input_limit_exceeded or tokenizer mismatch')
    if count+case['payload']['options']['num_predict']+512>8192: raise ValueError('context reservation exceeded')
    event,timeout=ledger.reserve(case)
    result=dict(schema_version='p013-call-v1',case_id=case['id'],manifest_sha256=ledger.manifest,payload=case['payload'],payload_sha256=case['payload_sha256'],
        request_dispatched=True,input_tokens=count,runtime=runtime,status='failed',model_digest=DIGEST)
    stop=threading.Event(); samples=[]; monitor_errors=[]
    def monitor():
        while not stop.is_set():
            try: samples.append(memory_sample())
            except Exception as exc: monitor_errors.append(str(exc));break
            stop.wait(1)
    thread=threading.Thread(target=monitor,daemon=True);thread.start();started=time.monotonic();unresolved=False
    try:
        response=http('chat',case['payload'],timeout);result['raw_response']=response
        if response.get('model')!=MODEL or response.get('done') is not True or response.get('done_reason')!='stop': raise ValueError('partial/length/provider response')
        if response['message'].get('thinking'): raise ValueError('unexpected thinking')
        if response.get('prompt_eval_count')!=count: raise ValueError('actual prompt token count mismatch')
        value=loads(response['message']['content']);result['parsed']=value
        result['resolved']=resolve(case['role'],case['data'],value)
        result['status']='valid' if result['resolved'].get('status')!='incomplete' else 'incomplete'
    except Exception as exc:
        result['error']=str(exc)
        unresolved=isinstance(exc,(TimeoutError,socket.timeout,error.URLError)) and not isinstance(exc,error.HTTPError)
    finally:
        stop.set();thread.join(timeout=2)
        memory_stop=bool(monitor_errors) or not samples or any(s['stop'] for s in samples)
        result.update(seconds=time.monotonic()-started,memory_samples=samples,memory_errors=monitor_errors,
            memory_stop=memory_stop,memory_scope='1-second sum of Ollama RSS; not hard sandbox or GPU memory')
        if memory_stop: unresolved=True
        ledger.finish(event,result,unresolved)
    print(case['id'],result['status'],round(result['seconds'],2),'seconds',flush=True)
    return result


def extraction_comparison(case,expected,result):
    """Exact agreement can pass; paraphrases require human semantic review.

    Never use the evaluator model to approve its own extraction. Counts labelled
    exact diagnostics are not claimed as semantic extraction quality.
    """
    if result['status']!='valid': return dict(status='failed',precision=None,recall=None,f1=None,error=result.get('error','incomplete extraction'))
    gs=result['resolved']['claims'];rs=expected['expected_claims'];matches=[]
    for g in gs:
        for r in rs:
            spans_g={(o['start'],o['end'],o['quote']) for o in g['occurrences']}
            spans_r={(o['start'],o['end'],o['quote']) for o in r['occurrences']}
            if g['text']==r['text'] and spans_g==spans_r: matches.append((g['id'],r['id']))
    from evaluator import correctness
    diag=correctness([g['id'] for g in gs],[r['id'] for r in rs],matches)
    exact=len(gs)==len(rs)==diag['tp']
    return dict(status='pass' if exact else 'review_required',precision=diag['precision'] if exact else None,recall=diag['recall'] if exact else None,
        f1=diag['f1'] if exact else None,exact_diagnostic=diag,expected_claims=rs,generated_claims=gs,
        human_semantic_review=None,reason='exact text and all occurrence spans agree' if exact else 'Non-identical extraction requires independent semantic review; no automatic semantic failure or approval.')


def replay(out):
    m=verify(out/'manifest.json');cases={c['id']:c for c in read(out/'cases.json')};expectations=read(out/'expectations.json')
    if (out/'ledger.json').exists(): state=Ledger(out,m['manifest_sha256']).state()
    else: state=dict(calls=[],pending=None,unresolved=False)
    rows=[]
    for event in state['calls']:
        result=read(out/event['artifact']);case=cases[event['case_id']]
        if result['payload']!=case['payload'] or event['payload_sha256']!=case['payload_sha256']: raise ValueError('call not frozen input')
        if result['status']=='valid' and resolve(case['role'],case['data'],result['parsed'])!=result['resolved']: raise ValueError('parsed/resolved changed')
        if case['role']=='extraction': comparison=extraction_comparison(case,expectations[case['id']],result)
        elif result['status']!='valid': comparison=dict(status='failed')
        else:
            expected=expectations[case['id']]
            if case['role']=='judge': actual={i['claim_id']:i['label'] for i in result['resolved']['items']};wanted=expected['labels']
            else: actual={i['generated_id']+':'+p['reference_id']:p['label'] for i in result['resolved']['items'] for p in i['pairs']};wanted=expected['pairs']
            comparison=dict(status='pass' if actual==wanted else 'failed',expected=wanted,actual=actual)
        rows.append(dict(case_id=case['id'],stage=case['stage'],role=case['role'],question=case['data'].get('question'),data=case['data'],
            result_status=result['status'],comparison=comparison,seconds=result['seconds'],artifact=event['artifact']))
    gates={}
    for stage,total in [('extraction',16),('judge',68)]:
        selected=[r for r in rows if r['stage']==stage]
        gates[stage]=dict(expected=total,dispatched=len(selected),passed=sum(r['comparison']['status']=='pass' for r in selected),
            status='PASS' if len(selected)==total and all(r['comparison']['status']=='pass' for r in selected) and not state['unresolved'] else 'NOT_PASSED')
    return dict(schema_version='p013-report-v1',manifest_sha256=m['manifest_sha256'],packet_sha256=PACKET,model_requests=len(rows),
        pending=state['pending'],unresolved=state['unresolved'],gates=gates,cases=rows,ground_truth_approval='version-bound human sidecar',
        actual_rag_evaluated=False,model_quality_generalization=False)


def run(manifest,stage):
    out=Path(manifest).parent;m=verify(manifest)
    # Runtime code must be exactly the code frozen before the first request.
    for path in Path(__file__).parent.glob('*.py'):
        frozen=out/'code'/path.name
        if not frozen.exists() or path.read_bytes()!=frozen.read_bytes(): raise ValueError('runtime code differs from frozen experiment')
    report=replay(out)
    if stage!='extraction' and report['gates']['extraction']['status']!='PASS': raise ValueError('S2 extraction gate not passed; downstream calls prohibited')
    if stage=='e2e' and report['gates']['judge']['status']!='PASS': raise ValueError('S3 judge gate not passed; S4 prohibited')
    if stage=='e2e': raise ValueError('S4 export integration must be verified before live dispatch')
    if not (out/'s1-verification.json').exists(): raise ValueError('S1 offline gate missing')
    s1=read(out/'s1-verification.json')
    if s1.get('status')!='PASS' or s1.get('manifest_sha256')!=m['manifest_sha256']: raise ValueError('S1 offline gate mismatch')
    for name,h in s1['evidence_files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts or sha((out/name).read_bytes())!=h: raise ValueError('S1 evidence changed')
    with (out/'.runner.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ledger=Ledger(out,m['manifest_sha256'])
        for case in read(out/'cases.json'):
            if case['stage']!=stage: continue
            state=ledger.state()
            if state['pending'] or state['unresolved']: raise ValueError('unresolved runtime stop')
            if any(c['case_id']==case['id'] for c in state['calls']): continue
            invoke(out,ledger,case)
        return replay(out)
