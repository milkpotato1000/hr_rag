"""Directly owned inference workers: concurrent pipe I/O, pressure/RSS and cleanup."""
import contextlib
import contextvars
import json
import os
import subprocess
import sys
import threading
import time
from .model_process import pressure, rss
from .storage import RagError, require

# An experiment may impose a stricter deadline and durable dispatch ledger.
CONTROL=contextvars.ContextVar('rag_owned_execution_control',default=None)

@contextlib.contextmanager
def execution_scope(control):
    token=CONTROL.set(control)
    try:yield
    finally:CONTROL.reset(token)


def check_scope():
    c=CONTROL.get()
    if c is not None:c.check()


def communicate_owned(command, text, timeout, *, env, observation=None, on_started=None,
                      monitor=None, rss_reader=None, cancel=None, stage='worker', timeout_code='worker_timeout'):
    obs=observation if observation is not None else {};monitor=monitor or pressure;rss_reader=rss_reader or rss
    start=time.monotonic();deadline=start+timeout;proc=None;thread=None;box={};done=threading.Event();primary=None
    obs.update(workers_started=0,worker_exited=None,completed=False,samples=[],sampling_target_ms=250,
               sampling_max_gap_ms=None,sampled_peak_rss_bytes=None,measurement='owned PID RSS samples + OS pressure; gaps include measurement latency; not instantaneous/system/GPU peak',resume_safe=False)
    def guard():
        check_scope()
        require(cancel is None or not cancel.is_set(),'worker_cancelled',stage)
        require(time.monotonic()<deadline,timeout_code,stage)
    def consume():
        try:box['output']=proc.communicate(text,timeout=max(.001,deadline-time.monotonic()))
        except BaseException as e:box['error']=e
        finally:done.set()
    try:
        guard();obs['preflight']=monitor();guard()
        c=CONTROL.get()
        if c is not None:c.before_spawn(command)
        guard()
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        obs.update(workers_started=1,worker_exited=False)
        if on_started:on_started()
        thread=threading.Thread(target=consume,name='owned-worker-pipes',daemon=True);thread.start()
        previous=start
        while not done.is_set():
            guard();state=monitor();guard()
            # A process may exit while pressure is being measured; do not query a reaped PID.
            if proc.poll() is None:
                try:resident=rss_reader(proc.pid)
                except RagError:
                    if proc.poll() is not None:break
                    raise
                guard();now=time.monotonic()
                sample={'elapsed_ms':(now-start)*1000,'gap_ms':(now-previous)*1000,'rss_bytes':resident,'os':state};previous=now
                obs['samples'].append(sample);obs['sampling_max_gap_ms']=max(obs['sampling_max_gap_ms'] or 0,sample['gap_ms']);obs['sampled_peak_rss_bytes']=max(obs['sampled_peak_rss_bytes'] or 0,resident)
                require(resident<4*1024**3,'worker_rss_limit',stage)
            done.wait(.25)
        # Child exit may precede communicate's final pipe result. Join before inspecting box.
        while thread.is_alive():
            guard();thread.join(timeout=.05)
        guard()
        if 'error' in box:
            if isinstance(box['error'],subprocess.TimeoutExpired):raise RagError(timeout_code,stage)
            raise box['error']
        # communicate owns pipe draining, wait confirms direct child termination.
        proc.wait(timeout=max(.001,deadline-time.monotonic()));thread.join(timeout=5)
        require(not thread.is_alive(),'worker_io_not_stopped',stage)
        obs['worker_exited']=proc.poll() is not None;require(obs['worker_exited'],'worker_not_stopped',stage)
        obs['returncode']=proc.returncode;obs['completed']=proc.returncode==0;obs['resume_safe']=True
        return box['output'][0],box['output'][1],proc.returncode
    except BaseException as e:
        primary=e
        obs['error']=getattr(e,'code',type(e).__name__)
        obs['failure_elapsed_ms']=(time.monotonic()-start)*1000
        if hasattr(e,'measurement'):obs['failure_measurement']=e.measurement
        if proc is not None:
            try:
                if proc.poll() is None:proc.kill()
                proc.wait(timeout=5)
                if thread is not None:thread.join(timeout=5)
                obs['worker_exited']=proc.poll() is not None
                obs['io_thread_exited']=thread is None or not thread.is_alive()
                obs['resume_safe']=obs['worker_exited'] and obs['io_thread_exited']
            except BaseException:obs['resume_safe']=False
        else:obs['resume_safe']=True
        if isinstance(e,(KeyboardInterrupt,SystemExit)):e.observation=obs;raise
        err=e if isinstance(e,RagError) else RagError('worker_io_failed',stage);err.observation=obs;primary=err;raise err from None
    finally:
        obs['elapsed_ms']=(time.monotonic()-start)*1000
        obs['final_observation_gap_ms']=obs['elapsed_ms']-(obs['samples'][-1]['elapsed_ms'] if obs['samples'] else 0)
        if obs['sampling_max_gap_ms'] is not None:obs['sampling_max_gap_ms']=max(obs['sampling_max_gap_ms'],obs['final_observation_gap_ms'])
        c=CONTROL.get()
        if c is not None:
            try:c.after_worker(obs)
            except BaseException as record_error:
                obs['recording_error']=type(record_error).__name__
                obs['recording_status']='failed_after_worker'
                if primary is not None:
                    primary.recording_error=type(record_error).__name__
                    # Keep original cancellation/pressure/IO failure and cleanup observation.
                else:
                    err=record_error if isinstance(record_error,(KeyboardInterrupt,SystemExit)) else RagError('worker_recording_failed',stage)
                    err.observation=obs;raise err from None


def invoke(module,payload,timeout,**kwargs):
    text=json.dumps(payload,ensure_ascii=False,allow_nan=False)
    env={'PATH':os.defpath,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','HF_HUB_DISABLE_IMPLICIT_TOKEN':'1','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    return communicate_owned([sys.executable,'-m',module],text,timeout,env=env,**kwargs)
