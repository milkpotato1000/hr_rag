"""Pinned local-only HF profiles and one owned subprocess per embedding operation."""
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import threading
import time
from .llm.config import fields, number, ValidationError, read_json as input_json
from .storage import RagError, require, digest, fingerprint

CATALOG={
    'intfloat/multilingual-e5-small':{'dimension':384,'query_prefix':'query: ','document_prefix':'passage: ','pooling':'mean','limit':512,'license':'MIT','url':'https://huggingface.co/intfloat/multilingual-e5-small'},
    'BAAI/bge-m3':{'dimension':1024,'query_prefix':'','document_prefix':'','pooling':'cls','limit':8192,'license':'MIT','url':'https://huggingface.co/BAAI/bge-m3'},
}
SDK=('sentence-transformers','torch','transformers','tokenizers','safetensors')
LOCK=threading.Lock()

def profile(value):
    try:
        fields(value,{'schema_version','model_id','revision','local_path','file_manifest','device','dtype','max_input_tokens','batch_size','timeout_seconds','max_chunks'},set(),'embedding')
        require(type(value['schema_version']) is int and value['schema_version']==1,'invalid_embedding_schema','embedding')
        require(value['model_id'] in CATALOG,'unsupported_embedding','embedding')
        require(isinstance(value['revision'],str) and re.fullmatch('[0-9a-f]{40}',value['revision']),'invalid_revision','embedding')
        require(isinstance(value['local_path'],str) and bool(value['local_path']),'invalid_model_path','embedding')
        require(value['device'] in ('cpu','mps') and value['dtype']=='float32','unsupported_runtime','embedding')
        for name,lo,hi in (('max_input_tokens',1,CATALOG[value['model_id']]['limit']),('batch_size',1,8),('timeout_seconds',1,300),('max_chunks',1,5000)):number(value[name],lo,hi,name,True)
        manifest=value['file_manifest'];require(isinstance(manifest,dict) and len(manifest)<=100,'invalid_file_manifest','embedding')
        for name,h in manifest.items():
            p=PurePosixPath(name)
            require(bool(name) and str(p)==name and not p.is_absolute() and '..' not in p.parts and '\\' not in name and isinstance(h,str) and re.fullmatch('[0-9a-f]{64}',h),'invalid_file_manifest','embedding')
        return value
    except (ValidationError,TypeError):raise RagError('invalid_embedding_config','embedding') from None

def configured(p):return p['revision']!='0'*40 and bool(p['file_manifest']) and not p['local_path'].startswith('EXAMPLE_')

def read_profile(path):
    p=profile(input_json(path));p=dict(p)
    if not Path(p['local_path']).is_absolute() and not p['local_path'].startswith('EXAMPLE_'):p['local_path']=str(Path(path).absolute().parent/p['local_path'])
    return p

def versions():
    try:return {name:importlib.metadata.version(name) for name in SDK}
    except importlib.metadata.PackageNotFoundError:raise RagError('retrieval_dependency_missing','embedding') from None

def identity(p):
    return {'model_id':p['model_id'],'revision':p['revision'],'file_manifest':p['file_manifest'],'device':p['device'],'dtype':p['dtype'],
            'max_input_tokens':p['max_input_tokens'],'catalog':CATALOG[p['model_id']],'normalization':'l2','algorithm':'exact-cosine-v1'}

def check_files(p):
    require(configured(p),'embedding_configuration_required','embedding')
    root=Path(p['local_path']).absolute()
    require(all(not x.is_symlink() for x in (root,*root.parents)) and root.is_dir(),'unsafe_model_path','embedding')
    actual=[];total=0
    for path in root.rglob('*'):
        require(not path.is_symlink(),'unsafe_model_path','embedding')
        if path.is_dir():continue
        require(path.is_file(),'unsafe_model_file','embedding');actual.append(path.relative_to(root).as_posix())
        total+=path.stat().st_size;require(len(actual)<=100 and total<=4*1024**3,'model_file_limit','embedding')
    require(set(actual)==set(p['file_manifest']),'model_manifest_mismatch','embedding')
    require('config.json' in actual and 'modules.json' in actual and any(x.endswith('.safetensors') for x in actual),'model_structure_required','embedding')
    require(not any(Path(x).suffix.lower() in ('.bin','.pt','.pth','.pkl','.pickle','.py','.so','.dylib') for x in actual),'unsafe_model_file','embedding')
    import hashlib
    for name,h in p['file_manifest'].items():
        hasher=hashlib.sha256()
        with (root/name).open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):hasher.update(block)
        require(hasher.hexdigest()==h,'model_file_hash_mismatch','embedding')
    modules=input_json(root/'modules.json')
    require(isinstance(modules,list) and len(modules) in (2,3),'unsupported_model_modules','embedding')
    expected=['sentence_transformers.models.Transformer','sentence_transformers.models.Pooling','sentence_transformers.models.Normalize']
    modern=['sentence_transformers.base.modules.transformer.Transformer','sentence_transformers.sentence_transformer.modules.pooling.Pooling','sentence_transformers.base.modules.normalize.Normalize']
    for n,m in enumerate(modules):
        require(isinstance(m,dict) and m.get('type') in (expected[n],modern[n]),'unsupported_model_modules','embedding')
        mp=m.get('path');require(isinstance(mp,str) and (mp=='' if n==0 else mp in ('1_Pooling','2_Normalize')),'unsafe_module_path','embedding')
    cfg=input_json(root/'config.json');require(cfg.get('hidden_size')==CATALOG[p['model_id']]['dimension'] and not cfg.get('auto_map'),'model_dimension_mismatch','embedding')
    pool=input_json(root/'1_Pooling/config.json');mode=CATALOG[p['model_id']]['pooling']
    require(pool.get('pooling_mode_'+('mean_tokens' if mode=='mean' else 'cls_token')) is True or pool.get('pooling_mode')==mode,'pooling_mismatch','embedding')
    require(pool.get('include_prompt',True) is True,'pooling_mismatch','embedding')
    for key,val in pool.items():
        if key.startswith('pooling_mode_') and isinstance(val,bool):require(val==(key=='pooling_mode_'+('mean_tokens' if mode=='mean' else 'cls_token')),'pooling_mismatch','embedding')
    return root

def normalize(vectors,count,dimension):
    require(isinstance(vectors,list) and len(vectors)==count,'vector_count','embedding');result=[]
    for row in vectors:
        require(isinstance(row,list) and len(row)==dimension and all(type(x) in (float,int) and math.isfinite(x) for x in row),'invalid_vector','embedding')
        norm=math.sqrt(sum(x*x for x in row));require(math.isfinite(norm) and norm>0,'zero_vector','embedding');result.append([x/norm for x in row])
    return result

def encode(p,texts,ids,kind,*,execute=False,backend=None,allow_whitespace=False, observation=None,expected_sdk=None):
    profile(p);require(kind in ('query','document') and len(texts)==len(ids),'invalid_embedding_input','embedding')
    require(len(texts)<=p['max_chunks'] and all(isinstance(x,str) and (bool(x) if allow_whitespace else bool(x.strip())) for x in texts),'embedding_input_limit','embedding')
    require(execute,'retrieval_execution_required','embedding')
    started=time.monotonic()
    observed=observation if observation is not None else {}
    observed.update(requested_items=len(texts), attempted_jobs=1, workers_started=0, backend_calls=0, completed_items=0, worker_exited=None)
    with LOCK:
        if backend is not None:
            observed.update(backend_calls=1,completed_items=None)
            response=backend(p,texts,ids,kind)
        else:
            check_files(p);sdk=versions()
            if expected_sdk is not None:require(sdk==expected_sdk,'embedding_sdk_mismatch','embedding')
            # An explicit minimal environment never inherits provider tokens or HF credentials.
            env={'PATH':os.defpath,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
            proc=subprocess.Popen([sys.executable,'-m','rag_package.embedding_worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
            observed.update(workers_started=1,completed_items=None,worker_exited=False)
            try:stdout,_=proc.communicate(json.dumps({'profile':p,'texts':texts,'ids':ids,'kind':kind}),timeout=p['timeout_seconds'])
            except subprocess.TimeoutExpired:
                proc.kill();proc.communicate();observed['worker_exited']=proc.poll() is not None;require(proc.poll() is not None,'worker_not_stopped','embedding');raise RagError('embedding_timeout','embedding') from None
            except BaseException:
                if proc.poll() is None:proc.kill()
                proc.communicate();observed['worker_exited']=proc.poll() is not None
                raise
            observed['worker_exited']=proc.poll() is not None
            require(proc.returncode==0,'embedding_worker_failed','embedding')
            try:response=json.loads(stdout)
            except (ValueError,TypeError):raise RagError('embedding_worker_failed','embedding') from None
            if response.get('error'):
                err=RagError(response['error'],'embedding');err.offending_ids=response.get('offending_ids',[]);raise err
        if backend is None and expected_sdk is not None:require(response.get('sdk_versions')==expected_sdk,'embedding_sdk_mismatch','embedding')
        vectors=normalize(response['vectors'],len(texts),CATALOG[p['model_id']]['dimension'])
        observed['completed_items']=len(texts)
    return vectors,{'jobs':1,'documents':len(texts) if kind=='document' else 0,'queries':len(texts) if kind=='query' else 0,'elapsed_ms':(time.monotonic()-started)*1000,
                    'sdk_versions':response.get('sdk_versions',{}),'peak_rss_bytes':response.get('peak_rss_bytes'),'rss_method':response.get('rss_method','unavailable'),'sampling_interval_ms':None,
                    'execution_kind':'test_fixture' if backend is not None else 'local_hf','worker_exited':True}
