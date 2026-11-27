"""Explicit OAuth helper. SDK imports and secrets are confined to execute paths."""
import json
import logging
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import tempfile
from .connectors.drive_config import credential_path,SCOPE
from .storage import RagError,require
from .llm.config import strict_json

TOKEN_URI='https://oauth2.googleapis.com/token'
AUTH_URIS=('https://accounts.google.com/o/oauth2/auth','https://accounts.google.com/o/oauth2/v2/auth')


def protected_path(path,create=False):
    p=credential_path(str(path))
    for part in [p,*p.parents]:require(not part.is_symlink(),'credential_symlink','auth')
    if create and not p.parent.exists():p.parent.mkdir(mode=0o700,parents=True)
    require(p.parent.is_dir() and stat.S_IMODE(p.parent.stat().st_mode)==0o700,'unsafe_credential_directory','auth')
    if p.exists():require(p.is_file() and stat.S_IMODE(p.stat().st_mode)==0o600,'unsafe_credential_permissions','auth')
    return p


def read_secret(path):
    p=protected_path(path)
    try:
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as f:raw=f.read(256*1024+1)
        require(len(raw)<=256*1024,'credential_too_large','auth')
        value=strict_json(raw.decode(),'credential')
        require(isinstance(value,dict),'invalid_credentials','auth');return value
    except (OSError,UnicodeError,ValueError):raise RagError('invalid_credentials','auth') from None


def save_secret(path,value,replace=False):
    p=protected_path(path,create=True);require(replace or not p.exists(),'credential_exists','auth')
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=p.parent,delete=False) as f:
            tmp=f.name;os.fchmod(f.fileno(),0o600);json.dump(value,f);f.flush();os.fsync(f.fileno())
        protected_path(p)
        if replace:os.replace(tmp,p);tmp=None
        else:os.link(tmp,p)
    except (OSError,UnicodeError):raise RagError('credential_write_failed','auth') from None
    finally:
        if tmp is not None:Path(tmp).unlink(missing_ok=True)


def token_text(value):
    require(isinstance(value,str) and value.strip() and value.isascii() and not any(ord(c)<=32 or ord(c)==127 for c in value),'invalid_access_token','auth')
    return value


def validate_user_info(info):
    require(isinstance(info,dict) and info.get('token_uri')==TOKEN_URI,'invalid_token_endpoint','auth')
    require(info.get('scopes')==[SCOPE],'invalid_scope','auth')
    require(info.get('type','authorized_user')=='authorized_user' and info.get('universe_domain','googleapis.com')=='googleapis.com','invalid_credentials','auth')
    for k in ('client_id','client_secret','refresh_token'):
        require(isinstance(info.get(k),str) and info[k].strip(),'invalid_credentials','auth')


def sdk():
    try:
        import importlib.metadata
        require(importlib.metadata.version('google-auth-oauthlib')=='1.5.0' and importlib.metadata.version('google-auth')=='2.63.1','oauth_sdk_version_mismatch','auth')
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        import requests
        return InstalledAppFlow,Credentials,Request,requests
    except ImportError:raise RagError('oauth_sdk_missing','auth') from None


def restrict_session(session):
    session.trust_env=False;session.verify=True
    original=session.send;calls={'count':0}
    def send(request,**kwargs):
        require(request.url==TOKEN_URI and request.method=='POST','oauth_endpoint_denied','auth')
        require(calls['count']==0,'oauth_request_limit','auth');calls['count']+=1
        kwargs.update(allow_redirects=False,verify=True,timeout=30,proxies={})
        response=original(request,**kwargs)
        require(not 300<=response.status_code<400,'oauth_redirect_denied','auth')
        return response
    session.send=send
    return calls


@contextmanager
def quiet_sdk():
    previous=logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:yield
    finally:logging.disable(previous)

class SDKBackend:
    def login(self,client):
        Flow,_,_,_=sdk()
        # Suppress SDK secret processing and authorization URLs in logs/stdout.
        with quiet_sdk():
            flow=Flow.from_client_config(client,scopes=[SCOPE],autogenerate_code_verifier=True)
            restrict_session(flow.oauth2session)
            creds=flow.run_local_server(host='127.0.0.1',bind_addr='127.0.0.1',port=0,timeout_seconds=300,
                                   open_browser=True,authorization_prompt_message=None)
        return creds
    def load(self,info):
        _,Credentials,_,_=sdk()
        with quiet_sdk():return Credentials.from_authorized_user_info(info,scopes=[SCOPE])
    def refresh(self,creds):
        _,_,Request,requests=sdk();session=requests.Session();calls=restrict_session(session)
        try:
            with quiet_sdk():creds.refresh(Request(session=session))
        finally:session.close()
        return calls['count']


def login(client_secret_file,credentials_file,*,execute=False,backend=None):
    credential_path(str(credentials_file));credential_path(str(client_secret_file))
    if not execute:return {'status':'preview','scope':SCOPE,'auth_requests':0,'notice':'Explicit execute opens Desktop OAuth browser login; readonly scope is broader than one file.'}
    target=protected_path(credentials_file,create=True);require(not target.exists(),'credential_exists','auth')
    try:
        client=read_secret(client_secret_file)
        require(set(client)=={'installed'} and isinstance(client['installed'],dict),'desktop_client_required','auth')
        c=client['installed'];require(c.get('auth_uri') in AUTH_URIS and c.get('token_uri')==TOKEN_URI,'invalid_oauth_endpoint','auth')
        for k in ('client_id','client_secret'):require(isinstance(c.get(k),str) and c[k].strip(),'invalid_client','auth')
        creds=(backend or SDKBackend()).login(client)
        info=strict_json(creds.to_json(),'credentials')
        validate_user_info(info);save_secret(target,info)
        return {'status':'complete','execution_kind':'test_fixture' if backend is not None else 'live','scope':SCOPE,'credentials_saved':True}
    except RagError:raise
    except Exception:raise RagError('auth_error','auth') from None


def acquire(auth,*,env_resolver=None,backend=None):
    if auth['mode']=='access_token_env':
        try:token=(env_resolver or os.environ.get)(auth['env'])
        except Exception:raise RagError('auth_error','auth') from None
        require(token is not None and token!='','missing_access_token','auth')
        return token_text(token),{'mode':'access_token_env','refresh_requests':0}
    refresh_attempted=False
    try:
        path=auth['credentials_file'];info=read_secret(path);validate_user_info(info)
        impl=backend or SDKBackend();creds=impl.load(info);count=0
        require(creds.has_scopes([SCOPE]),'invalid_scope','auth')
        if not creds.valid:
            refresh_attempted=True
            count=impl.refresh(creds);require(type(count) is int and 0<=count<=1,'oauth_request_limit','auth')
            require(creds.valid,'auth_error','auth')
            updated=strict_json(creds.to_json(),'credentials');validate_user_info(updated)
            save_secret(path,updated,replace=True)
        return token_text(creds.token),{'mode':'oauth_file','refresh_requests':count}
    except Exception as e:
        error=e if isinstance(e,RagError) else RagError('auth_error','auth')
        error.auth_refresh_attempted=refresh_attempted
        raise error from None
