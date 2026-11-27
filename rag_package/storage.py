"""Content identities and exclusive staged directory publication."""
import contextlib
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from .llm.config import strict_json, ValidationError

class RagError(ValueError):
    def __init__(self, code, stage):
        self.code,self.stage=code,stage
        super().__init__(code+': '+stage)

def require(condition,code,stage):
    if not condition:raise RagError(code,stage)

def digest(data):return hashlib.sha256(data).hexdigest()
def fingerprint(value):return digest(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def write_json(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def read_json(path):
    try:
        with Path(path).open('rb') as f:data=f.read(32*1024*1024+1)
        require(len(data)<=32*1024*1024,'artifact_too_large','load')
        return strict_json(data.decode('utf-8'),'artifact')
    except (OSError,UnicodeError,ValidationError):raise RagError('invalid_artifact','load') from None

def safe_path(root,name):
    require(isinstance(name,str) and name and '\\' not in name,'unsafe_artifact_path','load')
    p=Path(name)
    require(not p.is_absolute() and all(x not in ('.','..') for x in p.parts),'unsafe_artifact_path','load')
    root=Path(root).resolve();target=root/p
    require(target.resolve().is_relative_to(root),'unsafe_artifact_path','load')
    return target

def new_output(out):
    out=Path(out)
    require(not out.exists() and not out.is_symlink(),'output_exists','publish')
    return out


def exclusive_rename(source,target):
    # os.rename replaces an existing empty directory. Use the OS exclusive primitive.
    libc=ctypes.CDLL(None,use_errno=True)
    if sys.platform=='darwin':
        fn=libc.renamex_np;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint];fn.restype=ctypes.c_int
        rc=fn(os.fsencode(source),os.fsencode(target),4)  # RENAME_EXCL
    elif sys.platform.startswith('linux') and hasattr(libc,'renameat2'):
        fn=libc.renameat2;fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];fn.restype=ctypes.c_int
        rc=fn(-100,os.fsencode(source),-100,os.fsencode(target),1)  # RENAME_NOREPLACE
    else:raise RagError('exclusive_publish_unsupported','publish')
    if rc:
        raise RagError('output_exists' if ctypes.get_errno() in (errno.EEXIST,errno.ENOTEMPTY) else 'publication_failed','publish')

@contextlib.contextmanager
def staging(out):
    out=new_output(out);out.parent.mkdir(parents=True,exist_ok=True)
    tmp=Path(tempfile.mkdtemp(prefix='.'+out.name+'-',dir=out.parent))
    try:
        yield tmp
        exclusive_rename(tmp,out)
    finally:
        if tmp.exists():shutil.rmtree(tmp)


def seal(root,identity,elapsed_ms=0):
    files={str(p.relative_to(root)):digest(p.read_bytes()) for p in sorted(Path(root).rglob('*')) if p.is_file() and p!=Path(root)/'manifest.json'}
    identity=dict(identity,files=files)
    manifest={'identity':identity,'fingerprint':fingerprint(identity),'elapsed_ms':elapsed_ms}
    write_json(Path(root)/'manifest.json',manifest)
    return manifest


def verify(root,kind):
    root=Path(root);m=read_json(root/'manifest.json')
    require(isinstance(m,dict) and isinstance(m.get('identity'),dict),'invalid_manifest','load')
    i=m['identity']
    require(m.get('fingerprint')==fingerprint(i) and i.get('kind')==kind and i.get('schema_version')==1,'stale_manifest','load')
    require(isinstance(i.get('files'),dict),'invalid_manifest','load')
    for name,h in i['files'].items():
        path=safe_path(root,name)
        try:actual=digest(path.read_bytes())
        except OSError:raise RagError('missing_artifact','load') from None
        require(actual==h,'stale_file_hash','load')
    return m
