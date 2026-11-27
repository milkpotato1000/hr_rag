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


def doctor(config_path=None):
    pdf=dependency('pypdf','6.21.2');pdf.pop('name')
    drive=[dependency('google-auth-oauthlib','1.5.0'),dependency('google-auth','2.63.1')]
    state='version_mismatch' if any(d['status']=='version_mismatch' for d in drive) else 'missing' if any(d['status']=='missing' for d in drive) else 'available'
    cfg={'status':'not_supplied','reasons':[]}
    if config_path is not None:
        try:
            from .retrieval import config
            _,llm=config(config_path)
            if any(configuration_required(llm['profiles'][llm['roles'][role]]) for role in ('generation','evaluation')):
                cfg={'status':'example_requires_configuration','reasons':['Set your model identity and validation_status before execute. Preview remains available.']}
            else:cfg['status']='valid'
        except (RagError,ValidationError,OSError,ValueError):cfg={'status':'invalid','reasons':['invalid_config']}
    supported=sys.version_info>=(3,10);storage=storage_supported()
    status='unsupported' if not supported or not storage else 'error' if cfg['status']=='invalid' else 'needs_configuration' if cfg['status']=='example_requires_configuration' else 'ready_for_offline'
    result={'schema_version':1,'package':{'name':'milkpotato-rag-lab','version':__version__},'python':{'version':sys.version.split()[0],'supported':supported},'platform':{'name':sys.platform,'storage_supported':storage},'optional_dependencies':{'pdf':pdf,'drive':{'packages':[{k:v for k,v in d.items() if k!='status'} for d in drive],'status':state}},'config':cfg,'live_checks':'not_checked','network_requests':0,'secrets_read':0,'status':status}
    return result,3 if status=='needs_configuration' else 2 if status in ('unsupported','error') else 0
