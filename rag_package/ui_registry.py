"""Explicit workspace registry. Browser-facing values contain opaque IDs only."""
import copy,json,os,re,tempfile,threading,uuid
from pathlib import Path
from .storage import RagError,require,digest,fingerprint,read_json,verify
from .llm.config import fields,strict_json,validate_config,ValidationError
from .llm.core import configuration_required
from .documents import load_snapshot,safe_id
from .connectors.drive_config import validate_memory

ID=re.compile(r'[0-9a-f]{32}')
def uid():return uuid.uuid4().hex
def check_id(value):require(isinstance(value,str) and ID.fullmatch(value),'invalid_id','input');return value

def contained(root,path):
    p=Path(path);p=p if p.is_absolute() else root/p
    require(not any(x.is_symlink() for x in [p,*p.parents]),'symlink_denied','registry')
    require(p.resolve().is_relative_to(root),'outside_workspace','registry')
    return p.resolve()

def bounded(path,limit=1024*1024):
    try:
        with path.open('rb') as f:data=f.read(limit+1)
    except OSError:raise RagError('unreadable_registered_file','registry') from None
    require(len(data)<=limit,'file_limit','registry');return data

def decode(data):
    try:return strict_json(data.decode('utf-8'),'ui')
    except (UnicodeError,ValidationError):raise RagError('invalid_json','input') from None

def exact(value,required,optional=()):
    try:fields(value,set(required),set(optional),'ui')
    except ValidationError:raise RagError('invalid_fields','input') from None

def atomic_json(path,value):
    path=Path(path);tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:
            tmp=Path(f.name);json.dump(value,f,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,path);tmp=None
        fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if tmp is not None:tmp.unlink(missing_ok=True)

class Registry:
    def __init__(self,workspace,llm_configs,sources=None,drive_configs=(),embedding_configs=(),reranker_configs=(),qrels=(),facts=()):
        original=Path(workspace).absolute()
        require(original.is_dir() and not any(p.is_symlink() for p in [original,*original.parents]),'invalid_workspace','registry')
        self.workspace=original.resolve();self.root=contained(self.workspace,'.rag-runs/ui');self.root.mkdir(parents=True,exist_ok=True)
        for name in ('configs','inputs','jobs','artifacts'):
            contained(self.workspace,self.root/name).mkdir(exist_ok=True)
        self.lock=threading.RLock();self.path=self.root/'registry.json'
        contained(self.workspace,self.path)
        self.data=read_json(self.path) if self.path.exists() else {'schema_version':1,'configs':{},'artifacts':{}}
        require(self.data.get('schema_version')==1 and isinstance(self.data.get('configs'),dict) and isinstance(self.data.get('artifacts'),dict),'invalid_registry','registry')
        self.inputs={};self.drives={};self.embeddings={};self.sources_file=None
        self.rerankers={};self.labels={'qrels':{},'facts':{}}
        require(len(reranker_configs)<=4,'reranker_config_count','registry')
        from .reranker import read_profile as reranker_profile
        for path in reranker_configs:
            p=contained(self.workspace,path);raw=bounded(p);cfg=reranker_profile(p)
            self.rerankers[uid()]={'config':cfg,'path':p,'sha256':digest(raw)}
        for kind,paths in (('qrels',qrels),('facts',facts)):
            require(len(paths)<=8,'label_config_count','registry')
            for path in paths:
                p=contained(self.workspace,path);raw=bounded(p,16*1024*1024);decode(raw)
                self.labels[kind][uid()]={'path':self.relative(p),'sha256':digest(raw),'label':p.name}
        require(len(embedding_configs)<=4,'embedding_config_count','registry')
        from .embedding import read_profile
        for path in embedding_configs:
            p=contained(self.workspace,path);raw=bounded(p);cfg=read_profile(p)
            self.embeddings[uid()]={'config':cfg,'path':p,'sha256':digest(raw)}
        require(1<=len(llm_configs)<=8 and len(drive_configs)<=4,'config_count','registry')
        for path in llm_configs:self.register_llm(path)
        for path in drive_configs:
            p=contained(self.workspace,path);raw=bounded(p);c=decode(raw);validate_memory(c)
            self.drives[uid()]={'config':c,'path':p,'sha256':digest(raw)}
        if sources is not None:self.register_sources(sources)
    def save(self):atomic_json(self.path,self.data)
    def relative(self,p):return str(p.relative_to(self.workspace))
    def file(self,entry):
        p=contained(self.workspace,entry['path']);require(digest(bounded(p,20*1024*1024))==entry['sha256'],'stale_registered_file','registry');return p
    def register_llm(self,path):
        p=contained(self.workspace,path);raw=bounded(p);cfg=validate_config(decode(raw));h=digest(raw)
        with self.lock:
            for key,entry in self.data['configs'].items():
                if entry.get('original_path')==self.relative(p) and entry.get('original_sha256')==h:return key
            require(len(self.data['configs'])<8,'config_count','registry')
            key=uid();dest=self.root/'configs'/(key+'.json');atomic_json(dest,cfg)
            self.data['configs'][key]={'path':self.relative(dest),'sha256':digest(dest.read_bytes()),'original_path':self.relative(p),'original_sha256':h}
            self.save();return key
    def llm(self,key):
        check_id(key);entry=self.data['configs'].get(key);require(entry is not None,'unknown_config','registry')
        if 'original_path' in entry:
            p=contained(self.workspace,entry['original_path']);require(digest(bounded(p))==entry['original_sha256'],'stale_config','registry')
        return validate_config(decode(self.file(entry).read_bytes()))
    def config_summary(self,key):
        c=self.llm(key);p=c['profiles'][c['roles']['generation']]
        return {'id':key,'provider':p['provider'],'model':p['model'],'hf_id':p['identity'].get('hf_id'),'configuration_required':configuration_required(p),'max_output_tokens':p['max_output_tokens'],'temperature':p.get('temperature'),'num_ctx':p.get('num_ctx'),'identity':p['identity'],'validation_status':p['identity'].get('validation_status','unverified')}
    def clone_model(self,value):
        exact(value,('base_config_id','model','max_output_tokens','temperature'),('local_identity',))
        model=value['model'];require(isinstance(model,str) and 1<=len(model.strip())<=200 and not model.startswith('EXAMPLE_'),'configuration_required','config')
        with self.lock:
            require(len(self.data['configs'])<8,'config_count','registry')
            c=copy.deepcopy(self.llm(value['base_config_id']));name=c['roles']['generation'];p=copy.deepcopy(c['profiles'][name])
            p.update(model=model,max_output_tokens=value['max_output_tokens'],temperature=value['temperature'])
            if p['mode']=='local':
                i=value.get('local_identity');exact(i,('expected_digest','hf_id','source_revision','quantization'))
                require(isinstance(i['expected_digest'],str) and re.fullmatch('[0-9a-f]{64}',i['expected_digest']) and i['expected_digest']!='0'*64,'invalid_digest','config')
                require(isinstance(i['hf_id'],str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*',i['hf_id']),'invalid_hf_id','config')
                p['identity']=dict(i,conversion='user-configured/unverified',validation_status='user_configured_unverified')
            else:
                require('local_identity' not in value,'local_identity_not_allowed','config')
                p['identity']={'requested_model':model,'revision_pinned':False,'revision':None,'validation_status':'user_configured_unverified'}
            if name==c['roles']['evaluation']:
                name='generation-'+uid();c['roles']['generation']=name
            c['profiles'][name]=p;validate_config(c)
            key=uid();dest=self.root/'configs'/(key+'.json');atomic_json(dest,c)
            self.data['configs'][key]={'path':self.relative(dest),'sha256':digest(dest.read_bytes())};self.save()
            return self.config_summary(key)
    def register_sources(self,path):
        p=contained(self.workspace,path);raw=bounded(p);cfg=decode(raw);exact(cfg,('schema_version','documents'))
        require(type(cfg['schema_version']) is int and cfg['schema_version']==1 and isinstance(cfg['documents'],list) and 1<=len(cfg['documents'])<=20,'invalid_sources','registry')
        seen=set()
        for d in cfg['documents']:
            exact(d,('document_id','title','path','format','synthetic'))
            require(safe_id(d['document_id']) and d['document_id'] not in seen,'invalid_document_id','registry');seen.add(d['document_id'])
            require(d['format'] in ('pdf','txt','md') and type(d['synthetic']) is bool and isinstance(d['title'],str) and d['title'].strip(),'invalid_source','registry')
            source=contained(self.workspace,p.parent/d['path']);data=bounded(source,20*1024*1024)
            self.inputs[uid()]={**d,'path':self.relative(source),'sha256':digest(data)}
        self.sources_file={'path':self.relative(p),'sha256':digest(raw)}
    def input_summary(self):return [{'id':k,**{f:v[f] for f in ('title','format','synthetic')}} for k,v in self.inputs.items()]
    def upload(self,fmt,name,data):
        require(fmt in ('pdf','txt','md'),'unsupported_source','upload');require(0<len(data)<=20*1024*1024,'upload_size_limit','upload')
        if fmt!='pdf':
            try:text=data.decode('utf-8')
            except UnicodeError:raise RagError('invalid_utf8','upload') from None
            require(bool(text.strip()),'empty_upload','upload')
        require(isinstance(name,str) and len(name)<=200,'invalid_filename','upload')
        name=Path(name.replace('\\','/')).name;name=''.join(c for c in name if ord(c)>=32 and ord(c)!=127).strip() or '업로드 문서'
        with self.lock:
            require(len(self.inputs)<20,'input_count','upload')
            key=uid();p=self.root/'inputs'/(key+'.'+fmt)
            try:
                with p.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            except OSError:p.unlink(missing_ok=True);raise RagError('upload_write_failed','upload') from None
            self.inputs[key]={'path':self.relative(p),'sha256':digest(data),'document_id':'upload-'+key,'title':name,'format':fmt,'synthetic':False}
            return {'input_id':key,'title':name,'format':fmt,'status':'uploaded_not_parsed'}
    def freeze_inputs(self,ids):
        require(isinstance(ids,list) and 1<=len(ids)<=20 and all(isinstance(x,str) for x in ids) and len(set(ids))==len(ids),'invalid_inputs','input')
        if self.sources_file:self.file(self.sources_file)
        docs=[]
        for key in ids:
            check_id(key);entry=self.inputs.get(key);require(entry is not None,'unknown_input','registry')
            p=self.file(entry);docs.append(dict(entry,path=str(p)))
        return docs
    def drive(self,key,url):
        check_id(key);entry=self.drives.get(key);require(entry is not None,'unknown_drive_config','registry');require(digest(bounded(entry['path']))==entry['sha256'],'stale_config','registry')
        require(isinstance(url,str) and len(url)<=2048,'invalid_drive_link','input')
        c=copy.deepcopy(entry['config']);c['url']=url;validate_memory(c);return c
    def add_artifact(self,path,kind,**metadata):
        path=contained(self.workspace,path);m=verify(path,kind)
        key=uid();entry={'path':self.relative(path),'kind':kind,'fingerprint':m['fingerprint'],**metadata}
        with self.lock:self.data['artifacts'][key]=entry;self.save()
        return key
    def artifact(self,key):
        check_id(key);entry=self.data['artifacts'].get(key);require(entry is not None,'unknown_artifact','registry')
        p=contained(self.workspace,entry['path']);require(not any(x.is_symlink() for x in p.rglob('*')),'symlink_denied','registry');m=verify(p,entry['kind']);require(m['fingerprint']==entry['fingerprint'],'stale_artifact','registry')
        if entry['kind']=='snapshot':load_snapshot(p,ready=False)
        return p,entry,m
    def snapshot_for(self,key):
        p,e,m=self.artifact(key)
        if e['kind']=='snapshot':return p,key
        if e['kind'] in ('candidates','rerank','rerank-answer'):
            suffix={'candidates':'snapshot','rerank':'candidates/snapshot','rerank-answer':'rerank/candidates/snapshot'}[e['kind']]
            return p/suffix,key
        require('snapshot_id' in e,'artifact_has_no_source','registry')
        return self.snapshot_for(e['snapshot_id'])

    def embedding(self,key):
        check_id(key);entry=self.embeddings.get(key);require(entry is not None,'unknown_embedding','registry')
        require(digest(bounded(contained(self.workspace,entry['path'])))==entry['sha256'],'stale_embedding_config','registry')
        return copy.deepcopy(entry['config'])

    def reranker(self,key):
        check_id(key);entry=self.rerankers.get(key);require(entry is not None,'unknown_reranker','registry')
        require(digest(bounded(contained(self.workspace,entry['path'])))==entry['sha256'],'stale_reranker_config','registry')
        return copy.deepcopy(entry['config'])
    def label(self,kind,key):
        if key is None:return None
        check_id(key);entry=self.labels[kind].get(key);require(entry is not None,'unknown_labels','registry')
        return read_json(self.file(entry))
