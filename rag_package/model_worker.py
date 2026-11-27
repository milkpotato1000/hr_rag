"""Isolated HF metadata/download and tensor-only conversion. Never model inference."""
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from .storage import read_json, write_json, RagError
from .model_catalog import check, recipe, hexadecimal, LIMIT


def fetch_metadata(model, revision):
    from huggingface_hub import model_info
    info=model_info(model,revision=revision,files_metadata=True,timeout=20,token=False)
    check(info.id==model and hexadecimal(info.sha,40) and not info.private and not info.gated,'unsupported_hub_repository')
    wanted=recipe(model);seen=set();rows=[]
    for f in info.siblings:
        name=f.rfilename
        check(isinstance(name,str) and name and name not in seen and '\\' not in name and not any(ord(c)<32 for c in name),'invalid_remote_metadata')
        path=PurePosixPath(name);check(str(path)==name and not path.is_absolute() and '..' not in path.parts,'invalid_remote_metadata');seen.add(name)
        if name not in wanted:continue
        lfs=f.lfs
        rows.append({'path':name,'size':f.size,'git_blob_oid':f.blob_id,'lfs_sha256':lfs.sha256 if lfs is not None else None})
    check({r['path'] for r in rows}==wanted,'source_recipe_mismatch')
    return {'revision':info.sha,'files':rows,'observed_at':datetime.now(timezone.utc).isoformat()}


def download(plan,destination):
    from huggingface_hub import snapshot_download
    # Explicit revision + allowlist; SDK may internally retry and re-read metadata.
    snapshot_download(plan['repo_id'],revision=plan['revision'],local_dir=destination,
                      allow_patterns=[r['path'] for r in plan['files']],token=False,
                      max_workers=1,etag_timeout=20,dry_run=False)
    return {'download_jobs_completed':1,'http_request_count':None,'sdk_internal_retries':'SDK controlled; top-level retry 0'}


def filehash(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def convert(source,destination):
    import torch
    import safetensors
    from safetensors.torch import save_file
    from collections import OrderedDict
    import gc
    from safetensors import safe_open
    check(torch.__version__.split('+')[0]=='2.15.0' and safetensors.__version__=='0.8.0','conversion_sdk_mismatch')
    state=torch.load(source,weights_only=True,map_location='cpu',mmap=True)
    check(type(state) in (dict,OrderedDict) and 0<len(state)<=100000,'unsupported_tensor_state')
    supported={torch.float64,torch.float32,torch.float16,torch.bfloat16,torch.int64,torch.int32,torch.int16,torch.int8,torch.uint8,torch.bool}
    clean={};before={};total=0;storages=set()
    def describe(t):
        # NumPy shares the contiguous CPU bytes. Hash bounded memoryviews, not full copies.
        flat=t.contiguous().reshape(-1).view(torch.uint8)
        view=memoryview(flat.numpy());h=hashlib.sha256()
        for start in range(0,len(view),1024*1024):h.update(view[start:start+1024*1024])
        return {'dtype':str(t.dtype),'shape':list(t.shape),'value_sha256':h.hexdigest(),'bytes':len(view)}
    for key,t in state.items():
        check(isinstance(key,str) and bool(key) and type(t) is torch.Tensor and t.layout==torch.strided and t.device.type=='cpu' and t.dtype in supported,'unsupported_tensor_state')
        total+=t.numel()*t.element_size();check(total<=LIMIT,'tensor_size_limit')
        before[key]=describe(t)
        storage=t.untyped_storage().data_ptr()
        # Keep ordinary contiguous mmap tensors; only detach alias/noncontiguous views.
        if not t.is_contiguous() or storage in storages:
            clean[key]=t.detach().clone(memory_format=torch.contiguous_format)
        else:clean[key]=t.detach()
        if t.numel():storages.add(storage)
    save_file(clean,destination,metadata={'format':'pt'})
    del t,state,clean;gc.collect()
    # Read one mapped output tensor at a time after releasing the source state.
    after={}
    with safe_open(destination,framework='pt',device='cpu') as f:
        check(f.metadata()=={'format':'pt'} and set(f.keys())==set(before),'conversion_metadata_mismatch')
        for key in f.keys():after[key]=describe(f.get_tensor(key))
    check(before==after,'conversion_value_mismatch')
    return {'method':'tensor-only-bin-to-safetensors','tools':{'torch':'2.15.0','safetensors':'0.8.0'},
            'options':{'weights_only':True,'map_location':'cpu','mmap':True,'copy_policy':'noncontiguous_or_shared_storage_only','hash_chunk_bytes':1048576,'release_source_before_output_verification':True,'format':'pt'},
            'source_weight_sha256':filehash(source),'output_weight_sha256':filehash(destination),'tensors':before,'tensor_bytes':total,'forward_calls':0}


def main():
    try:
        p=read_json(sys.argv[1]);op=p['operation']
        if op=='metadata':r=fetch_metadata(p['model'],p['revision'])
        elif op=='download':r=download(p['plan'],p['destination'])
        elif op=='conversion':r=convert(p['source'],p['destination'])
        else:check(False,'unsupported_preparation_worker')
    except BaseException as e:r={'error':e.code if isinstance(e,RagError) else 'preparation_worker_failed'}
    write_json(sys.argv[2],r)

if __name__=='__main__':main()
