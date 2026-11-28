"""Offline LLM config creation, optional read-only Ollama identity inspection."""
import os
from pathlib import Path
import re
import tempfile
import time
from .llm.config import fields, validate_config, read_json, string, number, ValidationError
from .llm.transport import http_transport, TransportError
from .storage import RagError, require, exclusive_rename, new_output
from .ui_registry import atomic_json


def configure(spec_path,out,inspect_local=False,*,transport=None):
    spec=read_json(spec_path);fields(spec,{'schema_version','profiles','roles'},set(),'spec')
    if type(spec['schema_version']) is not int or spec['schema_version']!=1:raise ValidationError('schema_version')
    profiles=spec['profiles']
    if not isinstance(profiles,dict) or not 1<=len(profiles)<=4:raise ValidationError('profiles')
    cfg={'schema_version':2,'profiles':{},'roles':spec['roles']}
    required={'provider','base_url','model','max_output_tokens','timeout_seconds','response_mode'}
    for name,p in profiles.items():
        if not isinstance(p,dict):raise ValidationError('profile')
        local=p.get('provider')=='ollama'
        fields(p,required|({'origin'} if local else {'api_key_env','revision_pinned','revision'}),{'temperature','num_ctx','seed','think'} if local else {'temperature'},'profile')
        q={k:v for k,v in p.items() if k not in ('origin','revision_pinned','revision')}
        q['mode']='local' if local else 'api'
        if local:
            fields(p['origin'],{'hf_id','source_revision','conversion','quantization'},set(),'origin')
            for k,v in p['origin'].items():
                if v is None and k=='source_revision':continue
                string(v,'origin.'+k)
            q['identity']=dict(p['origin'],expected_digest='0'*64,validation_status='example_requires_configuration')
        else:q['identity']={'requested_model':p['model'],'revision_pinned':p['revision_pinned'],'revision':p['revision'],'validation_status':'user_configured_unverified'}
        cfg['profiles'][name]=q
    validate_config(cfg);out=new_output(Path(out).absolute());out.parent.mkdir(parents=True,exist_ok=True)
    observations=[];cache={};calls=0;started=time.monotonic();send=transport or http_transport
    if inspect_local:
        for name,p in cfg['profiles'].items():
            if p['provider']!='ollama':continue
            key=(p['base_url'].rstrip('/'),p['model'])
            if key not in cache:
                require(time.monotonic()-started<60,'local_inspection_timeout','llm_configure')
                try:
                    calls+=1;tags=send('GET',key[0]+'/api/tags',{},None,min(5,60-(time.monotonic()-started)))
                    require(isinstance(tags,dict) and isinstance(tags.get('models'),list),'invalid_local_identity','llm_configure')
                    matches=[m for m in tags['models'] if isinstance(m,dict) and (m.get('name')==key[1] or m.get('model')==key[1])]
                    require(len(matches)==1 and isinstance(matches[0].get('digest'),str) and re.fullmatch('[a-f0-9]{64}',matches[0]['digest']),'local_model_not_identified','llm_configure')
                    require(time.monotonic()-started<60,'local_inspection_timeout','llm_configure')
                    calls+=1;show=send('POST',key[0]+'/api/show',{'Content-Type':'application/json'},{'model':key[1]},min(5,60-(time.monotonic()-started)))
                    require(isinstance(show,dict) and isinstance(show.get('model_info'),dict),'invalid_local_identity','llm_configure')
                    info=show['model_info'];selected={k:info[k] for k in ('general.architecture','general.parameter_count','general.file_type') if k in info and isinstance(info[k],(str,int)) and not isinstance(info[k],bool)}
                    cache[key]={'digest':matches[0]['digest'],'model_info':selected}
                except (TransportError,RagError) as e:
                    err=RagError(e.code,'llm_configure');err.requests=calls;err.request_stages=['local_identity_inspection'];raise err from None
            p['identity']['expected_digest']=cache[key]['digest'];p['identity']['validation_status']='user_configured_unverified'
            observations.append({'profile':name,'server_identity':'observed','origin':'user_asserted','model_info':cache[key]['model_info'],'quality':'unverified'})
    validate_config(cfg)
    fd,tmp=tempfile.mkstemp(prefix='.'+out.name+'-',dir=out.parent);os.close(fd)
    try:atomic_json(Path(tmp),cfg);exclusive_rename(tmp,out)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()
    from .llm.core import configuration_required
    return {'status':'needs_configuration' if any(configuration_required(p) for p in cfg['profiles'].values()) else 'configured_unverified',
            'schema_version':2,'roles':cfg['roles'],'inspection':observations,'http_requests':calls,'retry_count':0,'secrets_read':0,'generation_requests':0,'evaluation_requests':0,'chunking_requests':0,'quality':'unverified'}
