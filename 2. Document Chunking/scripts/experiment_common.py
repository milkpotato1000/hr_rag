"""Immutable inputs, process-wide work lock and typed failures for P007."""
import contextlib,fcntl,json,os,threading,uuid
from pathlib import Path
from time import time
from document_common import STAGE,read_json,write_json,file_hash,fingerprint,unique_object,reject_constant,atomic_directory
from source_io import load_documents

EXP=STAGE/'experiments/p007'
RUNTIME=STAGE/'.runtime'
ARTIFACTS=STAGE/'artifacts'
ALGORITHM='chunk-experiment-v1'
TEXT_VERSION='canonical-slice-only-v1'
class ExperimentError(ValueError):
    def __init__(self,kind,message):self.kind=kind;super().__init__(message)
def need(value,kind,message):
    if not value:raise ExperimentError(kind,message)
def strict(text):return json.loads(text,object_pairs_hook=unique_object,parse_constant=reject_constant)
def save_state(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name('.'+path.name+'-'+uuid.uuid4().hex)
    try:
        with temp.open('x',encoding='utf-8') as f:
            f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()
def new_id(prefix):return prefix+'-'+uuid.uuid4().hex
_mutex=threading.Lock();_local=threading.local()
@contextlib.contextmanager
def work_lock():
    if getattr(_local,'depth',0):
        _local.depth+=1
        try:yield
        finally:_local.depth-=1
        return
    need(_mutex.acquire(blocking=False),'busy','Another model/index job is running')
    RUNTIME.mkdir(exist_ok=True);f=(RUNTIME/'work.lock').open('a+')
    try:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ExperimentError('busy','Another CLI/server owns model/index work')
        _local.depth=1
        yield
    finally:
        _local.depth=0;f.close();_mutex.release()
def spec():return read_json(EXP/'spec.json')
def config(value):
    configs=spec()['configs'];found=[x for x in configs if x['id']==(value if isinstance(value,str) else value.get('id'))]
    need(len(found)==1 and (isinstance(value,str) or value==found[0]),'invalid_config','Choose an exact supported experiment configuration')
    return dict(found[0])
def source(documents=None):
    cfg=spec()['corpus'];root=STAGE/'data/source-v4'
    need(file_hash(root/'handoff-manifest.json')==cfg['input_manifest_sha256'],'stale','Frozen corpus manifest changed')
    need(file_hash(root/'section-map.json')==cfg['section_map_sha256'],'stale','Section map changed')
    path=Path(documents) if documents else root/'extracted/manifest.json'
    need(path.resolve()==(root/'extracted/manifest.json').resolve(),'invalid_input','Only the registered frozen corpus is supported')
    manifest,docs=load_documents(path)
    need(len(docs)==1 and docs[0][0]['document_id']==cfg['expected_document_id'],'stale','Wrong document set')
    row,text=docs[0];need(row['canonical_sha256']==cfg['canonical_sha256'] and len(text)==cfg['canonical_chars'],'stale','Canonical input differs')
    sections=read_json(root/'section-map.json')
    for n in sections['nodes']:
        for key in ['heading','extent','body']:
            v=n[key];need(text[v['start']:v['end']]==v['quote'],'stale','Section span mismatch')
    return row,text,sections

def code_hash(names):return fingerprint({name:file_hash(STAGE/'scripts'/name) for name in names})
def load_run(path):
    p=Path(path);m=read_json(p/'manifest.json');need(m['status']=='complete','incomplete','Run is not complete')
    for name,digest in m['outputs'].items():need(file_hash(p/name)==digest,'stale','Run output changed: '+name)
    return m
