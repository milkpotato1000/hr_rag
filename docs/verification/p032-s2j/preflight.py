"""One bounded server/identity preflight, after control tests. No generation."""
from runtime import *
import urllib.error
if __name__=='__main__':
    verify_parent()
    need(not LEDGER.exists(),'already_preflighted');write(LEDGER,initial());owned=None
    with ownership(E/'owner.lock'):
        try:
            sample0=sample();append_sample(sample0);need(sample0['disk_free']>=2*1024**3,'disk_floor')
            pid=listener()
            if pid is None:
                need(BINARY.is_file() and os.access(BINARY,os.X_OK),'ollama_not_installed')
                with transact(LEDGER) as c:need(c.s['server_start_attempts']==0,'server_start_cap');c.s['server_start_attempts']=1
                env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':os.environ['HOME'],'OLLAMA_HOST':'127.0.0.1:11434','OLLAMA_MODELS':str(ROOT/'1. Naive RAG/.runtime/models'),'OLLAMA_NO_CLOUD':'1','OLLAMA_MAX_LOADED_MODELS':'1','OLLAMA_NUM_PARALLEL':'1'}
                owned=subprocess.Popen([str(BINARY),'serve'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                write(E/'server-ownership.json',{'owned':True,'pid':owned.pid,'binary':str(BINARY),'binary_sha256':sha(BINARY),'started_at':time.time()})
                deadline=time.monotonic()+10
                while listener() is None:
                    need(owned.poll() is None,'owned_server_exited');need(time.monotonic()<deadline,'owned_server_start_timeout');time.sleep(.5)
                pid=listener();need(pid==owned.pid,'listener_ownership_mismatch')
            else:write(E/'server-ownership.json',{'owned':False,'pid':pid,'observed_at':time.time()})
            version=metadata('/api/version');tags=metadata('/api/tags');show=metadata('/api/show',{'model':'qwen3:4b'})
            # Never retain template or raw inventory of unrelated installed models.
            selected=[m for m in tags.get('models',[]) if m.get('name')=='qwen3:4b' or m.get('model')=='qwen3:4b']
            record={'version':version,'selected_models':selected,'show_details':show.get('details'),'model_info':show.get('model_info'),'capabilities':show.get('capabilities'),'license_present':bool(show.get('license')),'historical_hf_origin':'Qwen/Qwen3-4B-Thinking-2507 (historical record, not server-verified HF provenance)'}
            write(E/'identity-observed.json',record);identity(tags,version,show);loaded=current_models();write(E/'loaded-before.json',loaded)
            # OS window and actual run ownership/loaded0 are repeated immediately before any dispatch.
            normal_window();write(E/'preflight.json',{'status':'PASS','identity_match':True,'loaded_zero':True,'server_pid':pid,'owned_server':owned is not None,'generation_requests':0,'metadata_requests':len(read(LEDGER)['metadata']),'at':time.time()})
            print('PASS preflight; generation0',flush=True)
        except BaseException as e:
            with transact(LEDGER) as c:c.halt(type(e).__name__+':'+str(e))
            write(E/'preflight.json',{'status':'BLOCKED','error':type(e).__name__+':'+str(e),'generation_requests':0,'at':time.time()})
            if owned is not None and owned.poll() is None:owned.terminate();owned.wait(timeout=10)
            print('BLOCKED '+type(e).__name__+':'+str(e),flush=True)
            raise
