"""Single Drive document download with optimistic version consistency."""
from datetime import datetime
import hashlib
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from .drive_config import config,preview
from .drive_http import drive_get
from ..drive_auth import acquire
from ..llm.config import strict_json,ValidationError,string
from ..storage import RagError,require,staging,new_output,write_json,digest
from ..documents import snapshot

FIELDS='id,name,mimeType,version,modifiedTime,trashed,capabilities(canDownload),size,md5Checksum,sha256Checksum,driveId'
DOC='application/vnd.google-apps.document'
MIMES={'application/pdf':'pdf','text/plain':'txt','text/markdown':'md',DOC:'pdf'}
META_LIMIT=256*1024


def metadata(raw,file_id,check_access=True):
    require(isinstance(raw,bytes) and 0<len(raw)<=META_LIMIT,'metadata_size_limit','metadata')
    try:
        m=strict_json(raw.decode(),'metadata')
        required={'id','name','mimeType','version','modifiedTime','trashed','capabilities'}
        require(isinstance(m,dict) and required<=m.keys() and not m.keys()-required-{'size','md5Checksum','sha256Checksum','driveId'},'invalid_metadata','metadata')
        require(m['id']==file_id,'metadata_id_mismatch','metadata');string(m['name'],'name')
        require(isinstance(m['version'],str) and re.fullmatch('[0-9]+',m['version']),'invalid_version','metadata')
        require(isinstance(m['modifiedTime'],str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})',m['modifiedTime']),'invalid_modified_time','metadata')
        require(datetime.fromisoformat(m['modifiedTime'].replace('Z','+00:00')).tzinfo is not None,'invalid_modified_time','metadata')
        require(type(m['trashed']) is bool,'invalid_metadata','metadata')
        if check_access:require(m['trashed'] is False,'trashed_file','metadata')
        require(isinstance(m['capabilities'],dict) and set(m['capabilities'])=={'canDownload'} and type(m['capabilities']['canDownload']) is bool,'invalid_metadata','metadata')
        if check_access:require(m['capabilities']['canDownload'] is True,'download_not_allowed','metadata')
        if check_access:require('driveId' not in m,'shared_drive_unsupported','metadata')
        require(isinstance(m['mimeType'],str),'invalid_metadata','metadata')
        if check_access:require(m['mimeType'] in MIMES,'unsupported_mime','metadata')
        if check_access and m['mimeType']!=DOC:
            require(isinstance(m.get('size'),str) and re.fullmatch('[0-9]+',m['size']),'invalid_size','metadata')
            require(0<int(m['size'])<=20*1024*1024,'body_size_limit','metadata')
        elif 'size' in m:require(isinstance(m['size'],str) and re.fullmatch('[0-9]+',m['size']),'invalid_size','metadata')
        for k,n in (('md5Checksum',32),('sha256Checksum',64)):
            if k in m:require(isinstance(m[k],str) and re.fullmatch('[0-9a-fA-F]{'+str(n)+'}',m[k]),'invalid_checksum','metadata')
        return m
    except (UnicodeError,ValidationError,ValueError) as e:
        if isinstance(e,RagError):raise
        raise RagError('invalid_metadata','metadata') from None


def pull(config_path,out,*,execute=False,transport=None,auth_backend=None,env_resolver=None):
    if not execute:return preview(config_path)
    c=config(config_path);new_output(out);started=time.monotonic();stages=[];requests=0;auth_info=None
    kind='test_fixture' if transport is not None or auth_backend is not None or env_resolver is not None else 'live'
    stage='auth'
    try:
        with staging(out) as tmp:
            token,auth_info=acquire(c['auth'],backend=auth_backend,env_resolver=env_resolver)
            deadline=time.monotonic()+60;send=transport or drive_get
            base='https://www.googleapis.com/drive/v3/files/'+c['file_id']
            headers={'Authorization':'Bearer '+token}
            if c['resource_key'] is not None:headers['X-Goog-Drive-Resource-Keys']=c['file_id']+'/'+c['resource_key']
            def request(name,url,limit):
                nonlocal requests,stage
                stage=name;require(requests<3,'request_limit','download')
                requests+=1;entry={'stage':name,'dispatch_attempted':True,'status':'attempted'};stages.append(entry)
                try:
                    body=send(url,headers,limit,deadline)
                    require(isinstance(body,bytes) and 0<len(body)<=limit,'body_size_limit',name)
                    entry['status']='received';return body
                except Exception as exc:
                    entry['status']='failed'
                    if isinstance(exc,RagError):raise
                    raise RagError('transport_error',name) from None
            meta_url=base+'?'+urlencode({'fields':FIELDS})
            before=metadata(request('metadata_before',meta_url,META_LIMIT),c['file_id'])
            exported=before['mimeType']==DOC;limit=10_000_000 if exported else 20*1024*1024
            url=base+'/export?'+urlencode({'mimeType':'application/pdf'}) if exported else base+'?alt=media'
            data=request('download',url,limit);stage='checksum'
            checks={'sha256':'unavailable','md5':'unavailable'}
            if not exported:
                require(len(data)==int(before['size']),'size_mismatch','checksum')
                for name,key,func in [('sha256','sha256Checksum',hashlib.sha256),('md5','md5Checksum',hashlib.md5)]:
                    if key in before:require(func(data).hexdigest()==before[key].lower(),'checksum_mismatch','checksum');checks[name]='verified'
            else:checks={'sha256':'export_bytes_only','md5':'not_applicable'}
            after=metadata(request('metadata_after',meta_url,META_LIMIT),c['file_id'],check_access=False)
            stage='consistency';require(before==after,'source_changed','consistency')
            fmt=MIMES[before['mimeType']]
            if before['mimeType']=='text/plain' and before['name'].lower().endswith('.md'):fmt='md'
            ident='drive-'+digest(c['file_id'].encode())
            origin={'provider':'google_drive','file_id':c['file_id'],'remote_version':before['version'],'modified_time':before['modifiedTime'],
                    'mime_type':before['mimeType'],'export_mime':'application/pdf' if exported else None,'downloaded_sha256':digest(data),
                    'consistency':'metadata_before_after','execution_kind':kind}
            stage='snapshot';download=tmp/('download.'+fmt);download.write_bytes(data)
            source={'schema_version':1,'documents':[{'document_id':ident,'title':before['name'],'path':download.name,'format':fmt,'synthetic':kind=='test_fixture'}]}
            write_json(tmp/'sources.json',source)
            sm=snapshot(tmp/'sources.json',tmp/'snapshot',origins={ident:origin})
            download.unlink();(tmp/'sources.json').unlink();stage='receipt'
            receipt={'schema_version':1,'status':sm['identity']['status'],'execution_kind':kind,'snapshot_fingerprint':sm['fingerprint'],
                     'before':before,'after':after,'downloaded_sha256':digest(data),'downloaded_bytes':len(data),'checksum_verification':checks,
                     'origin':origin,'requests':requests,'stages':stages,'auth':auth_info,'elapsed_ms':round((time.monotonic()-started)*1000,3),
                     'limitations':['Optimistic metadata consistency, not atomic revision download.','Google Docs export hash identifies exported bytes, not unique native document content.'],
                     'snapshot_reasons':[d['reason'] for d in sm['identity']['documents'] if d['reason']]}
            write_json(tmp/'receipt.json',receipt);stage='publish'
        return receipt
    except Exception as e:
        safe=e if isinstance(e,RagError) else RagError('output_write_failed' if isinstance(e,(OSError,UnicodeError)) else 'connector_error',stage)
        safe.dispatch_attempted=requests>0;safe.requests=requests;safe.request_stages=stages
        safe.auth_refresh_attempted=getattr(e,'auth_refresh_attempted',False)
        # Never chain SDK, HTTP body, credentials or filename errors.
        raise safe from None
