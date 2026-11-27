"""Offline Drive link/config parsing. No SDK, key, or remote access."""
from pathlib import Path
import re
from urllib.parse import urlsplit,parse_qsl
from ..llm.config import read_json,fields,string,ValidationError
from ..storage import RagError,require

SCOPE='https://www.googleapis.com/auth/drive.readonly'
REPO=Path(__file__).resolve().parents[2]
WORKSPACE=REPO.parent if REPO.name in ('hr_rag_dev','hr_rag_plan','hr_rag_main') else REPO


def credential_path(path):
    require(isinstance(path,str) and path.strip() and not any(ord(c)<32 for c in path),'invalid_credential_path','auth')
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and not p.is_relative_to(WORKSPACE),'credential_must_be_outside_repository','auth')
    return p


def link(url):
    try:
        string(url,'url');p=urlsplit(url)
        require(p.scheme=='https' and p.netloc in ('drive.google.com','docs.google.com') and not p.fragment and '#' not in url,'unsupported_link','config')
        values={}
        for key,value in parse_qsl(p.query,keep_blank_values=True,strict_parsing=True):values.setdefault(key,[]).append(value)
        require(all(len(values.get(k,[]))<=1 for k in ('id','resourcekey')),'duplicate_link_parameter','config')
        file_id=None
        if p.netloc=='drive.google.com':
            m=re.fullmatch(r'/file/d/([A-Za-z0-9_-]{1,200})(?:/view)?/?',p.path)
            if m:file_id=m[1];require('id' not in values,'ambiguous_id','config')
            elif p.path=='/open':file_id=values.get('id',[None])[0]
        else:
            m=re.fullmatch(r'/document/d/([A-Za-z0-9_-]{1,200})(?:/edit)?/?',p.path)
            if m:file_id=m[1];require('id' not in values,'ambiguous_id','config')
        require(isinstance(file_id,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,200}',file_id),'unsupported_link','config')
        key=values.get('resourcekey',[None])[0]
        require(key is None or re.fullmatch(r'[A-Za-z0-9_-]{1,200}',key),'invalid_resource_key','config')
        return file_id,key
    except (ValidationError,ValueError):raise RagError('invalid_drive_link','config') from None


def config(path):
    try:
        c=read_json(path);fields(c,{'schema_version','connector','url','auth'},set(),'drive_config')
        require(type(c['schema_version']) is int and c['schema_version']==1 and c['connector']=='google_drive','invalid_drive_config','config')
        file_id,key=link(c['url']);a=c['auth'];require(isinstance(a,dict),'invalid_auth','config')
        if a.get('mode')=='access_token_env':
            fields(a,{'mode','env'},set(),'auth')
            require(isinstance(a['env'],str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',a['env']),'invalid_env_name','config')
        elif a.get('mode')=='oauth_file':
            fields(a,{'mode','credentials_file'},set(),'auth');credential_path(a['credentials_file'])
        else:raise RagError('unsupported_auth','config')
        return {'file_id':file_id,'resource_key':key,'auth':a}
    except ValidationError:raise RagError('invalid_drive_config','config') from None


def preview(path):
    c=config(path)
    return {'status':'preview','connector':'google_drive','execution_kind':'preview','auth_mode':c['auth']['mode'],
            'scope':SCOPE,'scope_warning':'Read access to accessible Drive files, not limited to the selected file.',
            'supported':['PDF','UTF-8 TXT/MD','Google Docs PDF export'],'remote_access_verified':False,'requests':0,
            'notice':'No credentials, SDK, OAuth or HTTP used. Folder/shared-drive/shortcut/other apps are unsupported.'}
