"""Offline installation inspection and manifest-verified sample initialization."""
import ctypes
import importlib.metadata
from importlib.resources import files
import json
from pathlib import Path
import sys
from ._version import __version__
from .storage import staging,require,digest,RagError
from .llm.config import ValidationError
from .llm.core import configuration_required


def init(out):
    root=files('rag_package').joinpath('resources')
    manifest=json.loads(root.joinpath('manifest.json').read_text(encoding='utf-8'))
    with staging(out) as target:
        for entry in manifest['files']:
            name=entry['path'];p=Path(name)
            require(not p.is_absolute() and '..' not in p.parts and '\\' not in name,'invalid_resource','init')
            data=root.joinpath('sample',*p.parts).read_bytes()
            require(digest(data)==entry['sha256'],'resource_hash_mismatch','init')
            dest=target/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        (target/'resource-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'status':'complete','execution_kind':'offline','files':len(manifest['files']),'network_requests':0,'secrets_read':0}


def storage_supported():
    try:
        libc=ctypes.CDLL(None)
        return (sys.platform=='darwin' and hasattr(libc,'renamex_np')) or (sys.platform.startswith('linux') and hasattr(libc,'renameat2'))
    except (OSError,AttributeError):return False


def dependency(name,required):
    try:version=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:version=None
    return {'name':name,'installed_version':version,'required_version':required,'status':'missing' if version is None else 'available' if version==required else 'version_mismatch'}


def doctor(config_path=None, *, llm_config=None, embedding_config=None, reranker_config=None, chunk_config=None):
    pdf=dependency('pypdf','6.21.2');pdf.pop('name')
    drive=[dependency('google-auth-oauthlib','1.5.0'),dependency('google-auth','2.63.1')]
    drive_dependency_state='version_mismatch' if any(d['status']=='version_mismatch' for d in drive) else 'missing' if any(d['status']=='missing' for d in drive) else 'available'
    cfg={'status':'not_supplied','reasons':[]}
    if config_path is not None:
        try:
            from .retrieval import config
            _,llm=config(config_path)
            if any(configuration_required(llm['profiles'][llm['roles'][role]]) for role in llm['roles']):
                cfg={'status':'example_requires_configuration','reasons':['Set your model identity and validation_status before execute. Preview remains available.']}
            else:cfg['status']='valid'
        except (RagError,ValidationError,OSError,ValueError):cfg={'status':'invalid','reasons':['invalid_config']}
    role_checks={}
    if llm_config is not None:
        try:
            from .llm.config import read_json,validate_config
            llm=validate_config(read_json(llm_config))
            role_checks['llm']={'status':'valid','roles':{role:('example_requires_configuration' if configuration_required(llm['profiles'][name]) else 'configured_unverified') for role,name in llm['roles'].items()}}
            if any(v=='example_requires_configuration' for v in role_checks['llm']['roles'].values()):role_checks['llm']['status']='example_requires_configuration'
        except (RagError,ValidationError,OSError,ValueError):role_checks['llm']={'status':'invalid'}
    for name,path in [('embedding',embedding_config),('reranker',reranker_config),('chunk',chunk_config)]:
        if path is None:continue
        try:
            if name=='chunk':
                from .chunk_policy import read_config
                chunk,model=read_config(path);state='valid'
                if chunk['method']=='semantic':
                    from .embedding import configured
                    state='configured_unverified' if configured(model) else 'example_requires_configuration'
                elif chunk['method']=='llm':
                    state='example_requires_configuration' if any(configuration_required(model['profiles'][n]) for n in model['roles'].values()) else 'configured_unverified'
            else:
                from . import embedding,reranker
                module=embedding if name=='embedding' else reranker
                profile=module.read_profile(path)
                state='configured_unverified' if module.configured(profile) else 'example_requires_configuration'
            role_checks[name]={'status':state}
        except (RagError,ValidationError,OSError,ValueError):role_checks[name]={'status':'invalid'}
    states=[cfg['status']]+[x['status'] for x in role_checks.values()]
    supported=sys.version_info>=(3,10);storage=storage_supported()
    status='unsupported' if not supported or not storage else 'error' if 'invalid' in states else 'needs_configuration' if 'example_requires_configuration' in states else 'ready_for_offline'
    result={'schema_version':1,'package':{'name':'milkpotato-rag-lab','version':__version__},'python':{'version':sys.version.split()[0],'supported':supported},'platform':{'name':sys.platform,'storage_supported':storage},'optional_dependencies':{'pdf':pdf,'drive':{'packages':[{k:v for k,v in d.items() if k!='status'} for d in drive],'status':drive_dependency_state}},'config':cfg,'live_checks':'not_checked','network_requests':0,'secrets_read':0,'status':status}
    from .reranker import SDK_VERSIONS
    result['role_configs']=role_checks
    result['optional_dependencies']['retrieval']=[dependency(k,v) for k,v in SDK_VERSIONS.items()]
    result['optional_dependencies']['preparation']=dependency('huggingface-hub','2.5.0')
    result['inference_calls']=0
    return result,3 if status=='needs_configuration' else 2 if status in ('unsupported','error') else 0
