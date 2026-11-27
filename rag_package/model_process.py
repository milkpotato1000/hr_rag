"""Owned preparation workers, bounded time/disk/RSS. No existing server control."""
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .storage import RagError, read_json, write_json
from .model_catalog import check, LIMIT, HUB_VERSION


def dependency(name, version):
    try: actual=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: raise RagError('preparation_dependency_missing','model_preparation') from None
    check(actual==version,'preparation_dependency_version_mismatch')


def pressure():
    try:
        if sys.platform=='darwin':
            n=int(subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True,timeout=2).strip())
            state={'platform':'darwin','pressure_level':n,'pressure':{1:'normal',2:'warning',4:'critical'}.get(n,'unknown')}
            if n!=1:
                err=RagError('memory_pressure','model_preparation');err.measurement=state;raise err
            return state
        if sys.platform.startswith('linux'):
            mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
            check(mem['MemAvailable']>=1024**3,'memory_pressure')
            return {'platform':'linux','available_bytes':mem['MemAvailable'],'pressure':'available_memory_floor'}
    except (OSError,ValueError,KeyError,subprocess.SubprocessError): pass
    raise RagError('memory_observation_unavailable','model_preparation')


def rss(pid):
    try:
        if sys.platform.startswith('linux'):
            lines=Path('/proc/'+str(pid)+'/status').read_text().splitlines()
            return int(next(x for x in lines if x.startswith('VmRSS:')).split()[1])*1024
        if sys.platform=='darwin':
            return int(subprocess.check_output(['ps','-o','rss=','-p',str(pid)],text=True,timeout=2).strip())*1024
    except (OSError,ValueError,StopIteration,subprocess.SubprocessError):pass
    raise RagError('rss_observation_unavailable','model_preparation')


def disk_bytes(root):
    total=0;count=0
    for p in Path(root).rglob('*'):
        check(not p.is_symlink(),'unsafe_preparation_path')
        if p.is_dir():continue
        check(p.is_file(),'unsafe_preparation_path');total+=p.stat().st_size;count+=1
        # Source plus HF metadata and download partials; source recipe separately <=100.
        check(total<=LIMIT+16*1024**2 and count<=400,'preparation_disk_limit')
    return total


def run_worker(payload, directory, *, timeout, observation=None, monitor=pressure, rss_reader=rss):
    from .owned_worker import check_scope
    check_scope()
    op=payload['operation'];obs=observation if observation is not None else {}
    obs.update(attempted_jobs=1,workers_started=0,worker_exited=None,completed=False,peak_rss_bytes=None,rss_samples=0,retry_count=0)
    proc=None;start=time.monotonic();directory=Path(directory)
    try:
        if op in ('metadata','download'):dependency('huggingface-hub',HUB_VERSION)
        elif op=='conversion':
            dependency('torch','2.15.0');dependency('safetensors','0.8.0');obs['memory_precheck']=monitor()
        else:check(False,'unsupported_preparation_worker')
        inp=directory/(op+'-input.json');out=directory/(op+'-result.json')
        write_json(inp,payload)
        env={'PATH':os.defpath,'HF_HUB_DISABLE_TELEMETRY':'1','HF_HUB_DISABLE_IMPLICIT_TOKEN':'1','HF_HUB_DISABLE_XET':'1','HF_HUB_ETAG_TIMEOUT':'20','HF_HUB_DOWNLOAD_TIMEOUT':'20','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','TOKENIZERS_PARALLELISM':'false','HF_HOME':str(directory/'hf-cache'),'HF_TOKEN_PATH':str(directory/'absent-token')}
        if op=='conversion':env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        check_scope()
        proc=subprocess.Popen([sys.executable,'-m','rag_package.model_worker',str(inp),str(out)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
        obs.update(workers_started=1,worker_exited=False)
        while proc.poll() is None:
            check_scope()
            check(time.monotonic()-start<timeout,'preparation_timeout')
            if op=='conversion':
                obs['memory_latest']=monitor()
                if proc.poll() is None:
                    measured=rss_reader(proc.pid);obs['rss_samples']+=1;obs['peak_rss_bytes']=max(obs['peak_rss_bytes'] or 0,measured)
                    check(measured<4*1024**3,'conversion_rss_limit')
            if op=='download':disk_bytes(payload['destination'])
            time.sleep(.25)
        proc.wait();obs['worker_exited']=True
        check(proc.returncode==0,'preparation_worker_failed')
        result=read_json(out)
        check(isinstance(result,dict),'preparation_worker_failed')
        if 'error' in result:raise RagError(result['error'],'model_preparation')
        obs['completed']=True
        return result,obs
    except BaseException as e:
        if proc is not None:
            if proc.poll() is None:proc.kill()
            proc.wait();obs['worker_exited']=True
        if isinstance(e,(KeyboardInterrupt,SystemExit)):raise
        err=e if isinstance(e,RagError) else RagError('preparation_worker_failed','model_preparation');err.observation=obs;raise err from None
    finally:obs['elapsed_ms']=(time.monotonic()-start)*1000
