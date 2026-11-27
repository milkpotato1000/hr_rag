"""Offline, reviewed HF recipes and immutable source plans. No SDK import."""
import json
import re
from importlib.resources import files
from pathlib import PurePosixPath, Path
from .storage import require, fingerprint, read_json, write_json, staging

LIMIT = 4 * 1024**3
HUB_VERSION = '2.5.0'
RECIPES = {
    'intfloat/multilingual-e5-small': ('e5', 'embedding', 'MIT'),
    'BAAI/bge-m3': ('bge', 'embedding', 'MIT'),
    'BAAI/bge-reranker-v2-m3': ('bge-reranker', 'reranker', 'Apache-2.0'),
    'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1': ('mmini-reranker', 'reranker', 'Apache-2.0'),
}
FIELDS = {'schema_version','status','origin','recipe_id','repo_id','role','revision','files','total_bytes','conversion','license','source_observed_at','metadata_sdk','plan_sha256'}


def check(ok, code='invalid_source_plan'):
    require(ok, code, 'model_preparation')


def hexadecimal(v, n):
    return isinstance(v, str) and re.fullmatch('[0-9a-f]{'+str(n)+'}', v) is not None


def metadata(model):
    check(isinstance(model, str) and model in RECIPES, 'unsupported_model')
    name, _, _ = RECIPES[model]
    return json.loads(files('rag_package').joinpath('resources/models/'+name+'.json').read_text(encoding='utf-8'))


def recipe(model):
    m = metadata(model)
    return {f['path'] for f in m['files']}


def catalog():
    result = []
    for model, (name, role, license) in RECIPES.items():
        m = metadata(model)
        result.append({'model_id': model, 'role': role, 'recipe_id': name+'-v1', 'license': license,
                       'source': 'https://huggingface.co/'+model, 'license_source': 'https://huggingface.co/'+model+'/tree/'+m['revision'],
                       'revision': m['revision'], 'source_observed_at': m['observed_date'],
                       'source_bytes': m['total_source_bytes'], 'memory_requirement': 'unmeasured',
                       'conversion': conversion(model), 'preparation': 'not_prepared',
                       'inference': 'unverified', 'quality': 'unverified'})
    return {'models': result, 'network_requests': 0, 'inference_calls': 0, 'secrets_read': 0}


def conversion(model):
    return 'tensor-only-bin-to-safetensors' if model == 'BAAI/bge-m3' else 'native-copy'


def validate(plan):
    check(isinstance(plan, dict) and set(plan) == FIELDS)
    check(type(plan['schema_version']) is int and plan['schema_version'] == 1)
    model = plan['repo_id']; metadata(model)
    name, role, license = RECIPES[model]
    check(plan['recipe_id'] == name+'-v1' and plan['role'] == role and plan['license'] == license)
    check(plan['conversion'] == conversion(model))
    check(plan['status'] in ('ready','unresolved_preview'))
    check(plan['origin'] in ('packaged_metadata','fetched_metadata','unresolved_ref'))
    check(plan['metadata_sdk'] == {'huggingface-hub': HUB_VERSION})
    check(hexadecimal(plan['plan_sha256'], 64) and plan['plan_sha256'] == fingerprint({k:v for k,v in plan.items() if k!='plan_sha256'}))
    if plan['status'] == 'unresolved_preview':
        check(plan['origin'] == 'unresolved_ref' and isinstance(plan['revision'],str) and bool(plan['revision']) and plan['files']==[] and type(plan['total_bytes']) is int and plan['total_bytes']==0 and plan['source_observed_at'] is None)
        return plan
    check(plan['origin'] != 'unresolved_ref' and hexadecimal(plan['revision'],40))
    check(isinstance(plan['source_observed_at'],str) and bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}(T[0-9:.+Z-]+)?',plan['source_observed_at'])))
    rows = plan['files']; check(isinstance(rows,list) and 1 <= len(rows) <= 100)
    names = []
    for r in rows:
        check(isinstance(r,dict) and set(r)=={'path','size','git_blob_oid','lfs_sha256'})
        n=r['path']; check(isinstance(n,str) and n and '\\' not in n and not any(ord(c)<32 for c in n))
        p=PurePosixPath(n); check(str(p)==n and not p.is_absolute() and '..' not in p.parts)
        check(type(r['size']) is int and 0 < r['size'] <= LIMIT)
        check(hexadecimal(r['git_blob_oid'],40) and (r['lfs_sha256'] is None or hexadecimal(r['lfs_sha256'],64)))
        names.append(n)
    check(names==sorted(set(names)) and set(names)==recipe(model),'source_recipe_mismatch')
    check(type(plan['total_bytes']) is int and plan['total_bytes']==sum(r['size'] for r in rows) and plan['total_bytes']<=LIMIT)
    if plan['origin']=='packaged_metadata':
        m=metadata(model)
        check(plan['revision']==m['revision'] and rows==sorted(m['files'],key=lambda r:r['path']) and plan['source_observed_at']==m['observed_date'],'packaged_metadata_mismatch')
    return plan


def make_plan(model, role, revision=None, fetched=None):
    m=metadata(model);name,expected,license=RECIPES[model];check(role==expected,'model_role_mismatch')
    check(revision is None or isinstance(revision,str) and revision.strip() and len(revision)<=200,'invalid_revision')
    if fetched is not None:
        check(isinstance(fetched,dict) and set(fetched)=={'revision','files','observed_at'} and isinstance(fetched['files'],list),'invalid_remote_metadata')
    unresolved = revision is not None and revision!=m['revision'] and fetched is None
    p={'schema_version':1,'status':'unresolved_preview' if unresolved else 'ready',
       'origin':'unresolved_ref' if unresolved else 'fetched_metadata' if fetched else 'packaged_metadata',
       'recipe_id':name+'-v1','repo_id':model,'role':role,'revision':revision if unresolved else fetched['revision'] if fetched else m['revision'],
       'files':[] if unresolved else sorted(fetched['files'] if fetched else m['files'],key=lambda r:r['path']),
       'conversion':conversion(model),'license':license,'source_observed_at':None if unresolved else fetched['observed_at'] if fetched else m['observed_date'],
       'metadata_sdk':{'huggingface-hub':HUB_VERSION}}
    p['total_bytes']=sum(f['size'] for f in p['files']);p['plan_sha256']=fingerprint(p)
    return validate(p)


def load(directory):
    return validate(read_json(Path(directory)/'source-plan.json'))


def plan(model, role, out, revision=None, fetch_metadata=False, *, metadata_backend=None):
    # Validate the request before network or worker creation.
    make_plan(model, role, revision)
    fetched=None;work={'metadata_jobs':0,'inference_calls':0,'weight_download_jobs':0,'secrets_read':0}
    with staging(out) as tmp:
        if fetch_metadata:
            from .model_process import run_worker
            payload={'operation':'metadata','model':model,'revision':revision or metadata(model)['revision']}
            if metadata_backend:
                work['metadata_fixture_calls']=1;fetched=metadata_backend(payload)
            else:
                fetched,obs=run_worker(payload,tmp,timeout=60);work['metadata_jobs']=obs['workers_started'];work['observation']=obs
        if fetch_metadata:check(isinstance(fetched,dict),'invalid_remote_metadata')
        p=make_plan(model,role,revision,fetched)
        write_json(tmp/'source-plan.json',p);write_json(tmp/'planning.json',work)
    return dict(p,work=work)
