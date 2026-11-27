"""Verify pinned source bytes, prepare a separate runtime export, publish once."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
from . import embedding, reranker
from .storage import RagError, read_json, write_json, new_output, exclusive_rename
from .ui_registry import atomic_json
from .model_catalog import load, check, LIMIT, RECIPES
from .model_process import run_worker

LOCK=threading.Lock()


def regular(path):
    p=Path(path).absolute()
    check(all(not x.is_symlink() for x in (p,*p.parents)) and p.is_file(),'unsafe_source_file')
    return p


def hashes(path, size=None):
    p=regular(path);length=p.stat().st_size
    check(length<=LIMIT and (size is None or length==size),'source_size_mismatch')
    sha=hashlib.sha256();oid=hashlib.sha1(b'blob '+str(length).encode('ascii')+b'\0');actual=0
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):
            actual+=len(b);check(actual<=length,'source_size_mismatch');sha.update(b);oid.update(b)
    check(actual==length,'source_size_mismatch')
    return {'sha256':sha.hexdigest(),'git_blob_oid':oid.hexdigest(),'size':actual}


def verify_sources(plan, root):
    root=Path(root).absolute();check(root.is_dir() and all(not p.is_symlink() for p in (root,*root.parents)),'unsafe_source_directory')
    result={}
    for row in plan['files']:
        actual=hashes(root/row['path'],row['size'])
        check(actual['sha256']==row['lfs_sha256'] if row['lfs_sha256'] is not None else actual['git_blob_oid']==row['git_blob_oid'],'source_hash_mismatch')
        result[row['path']]=actual
    return result


def make_profile(plan, manifest):
    p={'schema_version':1,'model_id':plan['repo_id'],'revision':plan['revision'],'local_path':'model','file_manifest':manifest,
       'device':'cpu','dtype':'float32','batch_size':1,'timeout_seconds':120}
    if plan['role']=='embedding':p.update(max_input_tokens=512,max_chunks=5000);return embedding.profile(p)
    p.update(max_pair_tokens=512);return reranker.profile(p)


def model_check(path):
    from .workspace import dependency
    raw=read_json(path);model=raw.get('model_id') if isinstance(raw,dict) else None
    check(model in RECIPES,'unsupported_model')
    role=RECIPES[model][1];module=embedding if role=='embedding' else reranker
    p=module.read_profile(path);module.check_files(p)
    deps=[dependency(k,v) for k,v in reranker.SDK_VERSIONS.items()]
    return {'status':'prepared','role':role,'model_id':model,'revision':p['revision'],'sdk':deps,'inference':'unverified','quality':'unverified',
            'inference_calls':0,'network_requests':0,'secrets_read':0}


def prepare(plan_dir,out,*,source=None,execute_download=False,execute_conversion=False,download_backend=None,converter=None,
            persist=atomic_json,publish=exclusive_rename,disk_free=None,worker_timeout=None):
    plan=load(plan_dir);out=new_output(Path(out).absolute())
    check(plan['status']=='ready','unresolved_source_plan')
    planning=read_json(Path(plan_dir)/'planning.json') if (Path(plan_dir)/'planning.json').exists() else {}
    fixture_origin=bool(planning.get('metadata_fixture_calls'))
    needs=plan['conversion']!='native-copy'
    reason='conversion_confirmation_required' if needs and not execute_conversion else 'download_confirmation_required' if source is None and not execute_download else None
    if reason:
        return {'status':'preview','reason':reason,'plan_sha256':plan['plan_sha256'],'source_bytes':plan['total_bytes'],
                'required_disk_free_bytes':3*plan['total_bytes']+1024**3,'network_requests':0,'inference_calls':0,'artifact_written':False}
    out.parent.mkdir(parents=True,exist_ok=True)
    check(all(not p.is_symlink() for p in (out.parent,*out.parent.parents)),'unsafe_output_directory')
    free=shutil.disk_usage(out.parent).free if disk_free is None else disk_free(out.parent)
    check(free>=3*plan['total_bytes']+1024**3,'insufficient_disk_space')
    journal=out.with_name(out.name+'.preparation.json');new_output(journal)
    # Exclusive process-wide lock also covers separate CLI invocations under this user.
    import fcntl
    lockpath=Path(tempfile.gettempdir())/('rag-lab-preparation-'+str(os.getuid())+'.lock')
    lockfd=os.open(lockpath,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RagError('preparation_busy','model_preparation') from None
        with LOCK:
            tmp=Path(tempfile.mkdtemp(prefix='.'+out.name+'-preparing-',dir=out.parent))
            export=tmp/'export';export.mkdir();modeldir=export/'model';modeldir.mkdir()
            diagnostic={'schema_version':1,'status':'in_progress','phase':'preflight','plan_sha256':plan['plan_sha256'],
                        'execution_kind':'test_fixture' if fixture_origin or download_backend or converter else 'local_import' if source else 'hf_download',
                        'work':{'download':{'requested_jobs':int(source is None),'workers_started':0,'fixture_calls':0,'completed':False},
                                'conversion':{'requested_jobs':int(needs),'workers_started':0,'fixture_calls':0,'completed':False},'inference_calls':0,'retry_count':0},
                        'inference':'unverified','quality':'unverified'}
            published=False;start=time.monotonic()
            try:
                # Initial exclusive write prevents overlapping use of the same intended output.
                with journal.open('x',encoding='utf-8') as f:
                    json.dump(diagnostic,f,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
                persist(journal,diagnostic)
                if source is None:
                    source=tmp/'download';source.mkdir();diagnostic['phase']='download';persist(journal,diagnostic)
                    payload={'operation':'download','plan':plan,'destination':str(source)}
                    obs=diagnostic['work']['download']
                    if download_backend:
                        obs['fixture_calls']=1;download_backend(payload);obs['completed']=True
                    else:
                        result,_=run_worker(payload,tmp,timeout=worker_timeout or 900,observation=obs);obs['sdk']=result
                diagnostic['phase']='source_verification';persist(journal,diagnostic)
                originals=verify_sources(plan,source)
                total=0
                for row in plan['files']:
                    if row['path']=='pytorch_model.bin':continue
                    src=regular(Path(source)/row['path']);dest=modeldir/row['path'];dest.parent.mkdir(parents=True,exist_ok=True)
                    with src.open('rb') as fin,dest.open('xb') as fout:
                        while True:
                            b=fin.read(1024*1024)
                            if not b:break
                            total+=len(b);check(total<=LIMIT,'export_size_limit');fout.write(b)
                    check(hashes(dest)==originals[row['path']],'source_changed_during_copy')
                conversion={'method':'native-copy','tools':{},'options':{},'output_weight_sha256':originals.get('model.safetensors',{}).get('sha256')}
                if needs:
                    diagnostic['phase']='conversion';persist(journal,diagnostic)
                    payload={'operation':'conversion','source':str(regular(Path(source)/'pytorch_model.bin')),'destination':str(modeldir/'model.safetensors')}
                    obs=diagnostic['work']['conversion']
                    if converter:
                        obs['fixture_calls']=1;conversion=converter(payload);obs['completed']=True
                    else:conversion,_=run_worker(payload,tmp,timeout=worker_timeout or 300,observation=obs)
                    check(hashes(payload['source'])==originals['pytorch_model.bin'],'source_changed_during_conversion')
                    check(conversion.get('source_weight_sha256')==originals['pytorch_model.bin']['sha256'] and conversion.get('output_weight_sha256')==hashes(modeldir/'model.safetensors')['sha256'],'conversion_hash_mismatch')
                sidecar={'schema_version':1,'repo_id':plan['repo_id'],'revision':plan['revision'],'plan_sha256':plan['plan_sha256'],
                         'original_files':{row['path']:{'size':row['size'],'source_git_blob_oid':row['git_blob_oid'],'lfs_sha256':row['lfs_sha256'],'local_sha256':originals[row['path']]['sha256'],'local_git_blob_oid':originals[row['path']]['git_blob_oid']} for row in plan['files']},'conversion':conversion,'execution_kind':diagnostic['execution_kind']}
                write_json(modeldir/'source-provenance.json',sidecar)
                manifest={p.relative_to(modeldir).as_posix():hashes(p)['sha256'] for p in sorted(modeldir.rglob('*')) if p.is_file()}
                check(len(manifest)<=100 and sum((modeldir/n).stat().st_size for n in manifest)<=LIMIT,'export_size_limit')
                profile=make_profile(plan,manifest);write_json(export/'profile.json',profile);model_check(export/'profile.json')
                write_json(export/'source-plan.json',plan)
                diagnostic.update(status='ready',phase='publication_intent',elapsed_ms=(time.monotonic()-start)*1000)
                write_json(export/'preparation.json',diagnostic);persist(journal,diagnostic)
                publish(export,out);published=True
                diagnostic['phase']='published';persist(journal,diagnostic)
                return dict(diagnostic,diagnostic_status='saved')
            except BaseException as e:
                if published:
                    return dict(diagnostic,status='ready',phase='published',diagnostic_status='ack_write_failed',automatic_retry=False)
                diagnostic.update(status='interrupted' if isinstance(e,(KeyboardInterrupt,SystemExit)) else 'failed',error=e.code if isinstance(e,RagError) else 'preparation_io_or_worker_failed',elapsed_ms=(time.monotonic()-start)*1000)
                try:persist(journal,diagnostic)
                except (OSError,UnicodeError,RagError):diagnostic['diagnostic_status']='write_failed'
                return diagnostic
    finally:
        os.close(lockfd)
