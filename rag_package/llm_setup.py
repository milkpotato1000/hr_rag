"""Offline LLM config creation, optional read-only Ollama identity inspection."""
import os
from pathlib import Path
from importlib.resources import files
import json
import shlex
import re
import tempfile
import time
from .llm.config import fields, validate_config, read_json, string, url, ValidationError
from .llm.transport import http_transport, TransportError
from .storage import RagError, require, exclusive_rename, new_output, staging, write_json
from .ui_registry import atomic_json


def configure(spec_path,out,inspect_local=False,*,transport=None):
    return _configure(read_json(spec_path),out,inspect_local,transport=transport)


def _configure(spec,out,inspect_local,*,transport=None,choose_local=False):
    fields(spec,{'schema_version','profiles','roles'},set(),'spec')
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
                    quant=show.get('details',{}).get('quantization_level') if isinstance(show.get('details'),dict) else None
                    if isinstance(quant,str) and quant.strip():cache[key]['quantization']=quant
                except (TransportError,RagError) as e:
                    err=RagError(e.code,'llm_configure');err.requests=calls;err.request_stages=['local_identity_inspection'];raise err from None
            p['identity']['expected_digest']=cache[key]['digest'];p['identity']['validation_status']='user_configured_unverified'
            observed=cache[key]
            origin='user_asserted'
            example=handbook_profile()
            is_example=all(p['identity'].get(k)==v for k,v in example['origin'].items())
            if choose_local and observed['digest']==HANDBOOK_DIGEST:
                p['identity'].update(example['origin'])
                p.update({k:example[k] for k in ('think','temperature','seed','max_output_tokens','num_ctx','timeout_seconds')})
                origin='historical_digest_match'
            elif choose_local:
                origin='unknown'
                p['identity']['quantization']=observed.get('quantization','unknown')
            elif is_example:
                require(observed['digest']==HANDBOOK_DIGEST,'handbook_digest_mismatch','llm_configure')
                origin='historical_digest_match'
            observations.append({'profile':name,'server_identity':'observed','digest':observed['digest'],
                                 'origin':origin,'quantization_observed':observed.get('quantization'),
                                 'model_info':observed['model_info'],'quality':'unverified'})
    validate_config(cfg)
    fd,tmp=tempfile.mkstemp(prefix='.'+out.name+'-',dir=out.parent);os.close(fd)
    try:atomic_json(Path(tmp),cfg);exclusive_rename(tmp,out)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()
    from .llm.core import configuration_required
    return {'status':'needs_configuration' if any(configuration_required(p) for p in cfg['profiles'].values()) else 'configured_unverified',
            'schema_version':2,'roles':cfg['roles'],'inspection':observations,'http_requests':calls,'retry_count':0,'secrets_read':0,'generation_requests':0,'evaluation_requests':0,'chunking_requests':0,'quality':'unverified'}


HANDBOOK_DIGEST='359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7'
LOCAL_ENDPOINT='http://127.0.0.1:11434'


def sample(name):
    return json.loads(files('rag_package').joinpath('resources','sample',name).read_text(encoding='utf-8'))


def handbook_profile():
    return sample('handbook-qwen-spec.json')['profiles']['local']


def local_models(endpoint=LOCAL_ENDPOINT, *, transport=None):
    base=url(endpoint,'local')
    try:
        tags=(transport or http_transport)('GET',base+'/api/tags',{},None,5)
    except TransportError as exc:
        err=RagError(exc.code,'local_models');err.requests=1
        raise err from None
    require(isinstance(tags,dict) and isinstance(tags.get('models'),list),'invalid_local_identity','llm_configure')
    models=[]
    for entry in tags['models']:
        require(isinstance(entry,dict),'invalid_local_identity','llm_configure')
        models.append({'model':string(entry.get('name') or entry.get('model'),'model'),'digest':entry.get('digest')})
    return {'models':models,'http_requests':1,'generation_requests':0}


def setup_generation(provider,model,out,*,endpoint=None,key_env=None,inspect_local=False,transport=None):
    """Publish a profile and a matching BM25 search config as a single directory."""
    local=provider=='ollama'
    require(provider in ('ollama','openai_chat','anthropic_messages'),'unsupported_provider','llm_configure')
    require(not (local and key_env is not None) and not (not local and inspect_local),
            'incompatible_provider_option','llm_configure')
    if local:
        spec=sample('llm-spec-local.json')
        profile=spec['profiles']['local']
        profile['origin']=dict(hf_id='unknown',source_revision=None,conversion='unknown',quantization='unknown')
        profile['base_url']=LOCAL_ENDPOINT if endpoint is None else endpoint
    else:
        spec=sample('llm-spec-api.json')
        profile=spec['profiles']['api']
        profile['provider']=provider
        default_endpoint='https://api.openai.com/v1' if provider=='openai_chat' else 'https://api.anthropic.com/v1'
        profile['base_url']=default_endpoint if endpoint is None else endpoint
        profile['api_key_env']=key_env if key_env is not None else ('OPENAI_API_KEY' if provider=='openai_chat' else 'ANTHROPIC_API_KEY')
    profile['model']=model
    out=Path(out)
    with staging(out) as stage:
        result=_configure(spec,stage/'model.json',inspect_local,transport=transport,choose_local=local)
        search=sample('fixed.json')
        search['llm_config']='model.json'
        write_json(stage/'search.json',search)
    result.update(provider=provider,model=model,endpoint=profile['base_url'],profile=str(out/'model.json'),
                  search_config=str(out/'search.json'),commands={
        'pipeline_preview':shlex.join(['rag-lab','pipeline','--sources','handbook-sources.json','--chunk-config','chunk-fixed.json',
                                     '--search-config',str(out/'search.json'),'--question','생일 특별휴가를 신청하면 누구의 승인을 받아야 하나요?',
                                     '--out',str(out.parent/(out.name+'-preview'))]),
        'serve':shlex.join(['rag-lab','serve','--workspace','.','--sources','handbook-sources.json',
                           '--chunk-config','chunk-fixed.json','--llm-config',str(out/'model.json')])})
    return result
