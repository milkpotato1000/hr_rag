"""Run precisely the next frozen question; smoke content gates are separate reviewed files."""
from runtime import *
import sys
if __name__=='__main__':
    qid=sys.argv[1];frozen=read(E/'frozen.json');owned_client=None
    with ownership(E/'owner.lock'):
        try:
            need(read(E/'preflight.json')['status']=='PASS','preflight_missing')
            for name,h in frozen['scripts'].items():need(sha(E/name)==h,'runner_changed')
            for name,h in frozen['input_files'].items():need(sha(ROOT/name)==h,'input_changed')
            need(sha(E/'profile.json')==frozen['profile_sha256'],'profile_changed')
            need(sha(Path(frozen['wheel']))==frozen['wheel_sha256'],'wheel_changed')
            for name,h in frozen['installed_files'].items():need(sha(Path(name))==h,'installed_file_changed')
            with transact(LEDGER) as c:
                if not c.s['claimed']:c.claim()
                c.check();need(len(c.s['requests'])<10 and qid==ORDER[len(c.s['requests'])],'order_or_duplicate')
                if qid=='gt03':
                    review=read(E/'smoke-review.json');need(review['reviewer']=='dev Codex source comparison' and review['passed'] is True,'smoke_review_missing')
                    for item in review['rows']:
                        need(sha(E/'answers'/item['question_id']/'result.json')==item['result_sha256'],'review_identity')
                        c.gate(item['question_id'],item['passed'])
            need(listener()==read(E/'server-ownership.json')['pid'],'server_changed');current_models();normal_window()
            start=time.monotonic();log=(E/(qid+'-cli.log')).open('w');env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','LANG':'en_US.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
            owned_client=subprocess.Popen([frozen['python'],'-I','-B',str(E/'worker.py'),qid],cwd=Path(frozen['python']).parent.parent.parent,env=env,stdout=log,stderr=log)
            def check_running():
                with transact(LEDGER) as c:c.check()
            warning,observations=observe_client(owned_client,check=check_running)
            code=owned_client.wait();log.close();result=read(E/'answers'/qid/'result.json')
            # Observe cleanup even when the strict provider rejected the response.
            cleanup_start=time.monotonic();normal=None;unloaded=False;lastps=0
            while time.monotonic()-cleanup_start<60:
                s=sample();append_sample(s)
                if s['pressure']==1:
                    if normal is None:normal=time.monotonic()
                else:normal=None
                if time.monotonic()-lastps>=5:
                    loaded=current_models(True);observations.append(loaded);unloaded=not loaded['models'];lastps=time.monotonic()
                if unloaded and normal is not None and time.monotonic()-normal>=30:break
                time.sleep(1)
            restored=normal is not None and time.monotonic()-normal>=30
            write(E/(qid+'-observation.json'),{'exit_code':code,'warning_observed':warning,'normal_restored':restored,'unloaded_observed':unloaded,'loaded_observations':observations,'client_reaped':True,'response_completed':result.get('provider_result',{}).get('status')=='complete','server_cancellation_not_inferred':True})
            provider=result.get('provider_result') or {};technical=code==0 and result['status'] in ('answered','abstained') and provider.get('status')=='complete' and provider.get('identity_verification',{}).get('status')=='verified'
            need(result['actual_messages_hash']==next(r['actual_messages_hash'] for r in frozen['rows'] if r['question_id']==qid),'actual_prompt_changed')
            with transact(LEDGER) as c:c.finish(qid,technical,unloaded,restored)
            print('COMPLETE '+qid+'; content review pending' if qid in ('gt01','gt02') else 'COMPLETE '+qid,flush=True)
        except BaseException as e:
            # Kill only this owned client. Shared Ollama inference may remain unknown.
            reap_owned_client(owned_client)
            try:
                with transact(LEDGER) as c:c.halt(type(e).__name__+':'+str(e))
            except Stop:pass
            write(E/(qid+'-failure.json'),{'error':type(e).__name__+':'+str(e),'at':time.time(),'owned_client_reaped':owned_client is None or owned_client.poll() is not None,'server_inference_cancellation':'not_proven','next_dispatch_allowed':False})
            print('HALTED '+str(e),flush=True);raise
