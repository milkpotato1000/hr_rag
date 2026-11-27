"""Provider routing and normalized results; no work occurs on import."""
import copy
import hashlib
import json
import os
import re
import time
from .config import validate_config, validate_messages, strict_json, ValidationError, string
from .transport import http_transport, TransportError

JSON_INSTRUCTION = 'Return only one valid JSON object, without Markdown fences or other text.'


def hash_json(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False).encode('utf-8')).hexdigest()


def preview(config, role, messages):
    validate_config(config)
    validate_messages(messages)
    if role not in ('generation','evaluation'): raise ValidationError('role')
    p = config['profiles'][config['roles'][role]]
    actual = copy.deepcopy(messages)
    if p['response_mode'] == 'json_object':
        if actual[0]['role'] == 'system':
            actual[0]['content'] += '\n\n' + JSON_INSTRUCTION
        else:
            actual.insert(0, {'role':'system','content':JSON_INSTRUCTION})
    provider = p['provider']
    body = {'model':p['model'], 'messages':copy.deepcopy(actual), 'stream':False}
    if provider == 'ollama':
        endpoint = '/api/chat'
        body.update(think=False, keep_alive=0, options={'num_predict':p['max_output_tokens']})
        for k in ('temperature','num_ctx','seed'):
            if p.get(k) is not None: body['options'][k] = p[k]
        if p['response_mode'] == 'json_object': body['format'] = 'json'
    else:
        if p.get('temperature') is not None: body['temperature'] = p['temperature']
        if provider == 'openai_chat':
            endpoint = '/chat/completions'
            body['max_completion_tokens'] = p['max_output_tokens']
            if p['response_mode'] == 'json_object': body['response_format'] = {'type':'json_object'}
        else:
            endpoint = '/messages'
            body['max_tokens'] = p['max_output_tokens']
            if actual[0]['role'] == 'system':
                body['system'] = body['messages'].pop(0)['content']
    target = p['base_url'].rstrip('/') + endpoint
    return {'schema_version':1,'provider':provider,'role':role,'method':'POST','url':target,'body':body,
            'original_messages_hash':hash_json(messages),'actual_messages_hash':hash_json(actual),
            'request_fingerprint':hash_json({'provider':provider,'url':target,'body':body,'identity':p['identity']}),
            'notice':'Preview includes prompt text. Review private document content before sharing. No keys read; no HTTP sent.'}


def result_base(p, role, request):
    return {'schema_version':1,'status':'error','content':None,'parsed_json':None,
            'provider':p['provider'],'requested_model':p['model'],'response_model':None,'role':role,
            'identity_verification':{'status':'not_checked','before':False,'after':False},
            'finish_reason':None,'usage':{'input_tokens':None,'output_tokens':None,'provider_duration_ms':None},
            'cost':None,'cost_status':'unmeasured','elapsed_ms':0,
            'request_fingerprint':request['request_fingerprint'],'actual_messages_hash':request['actual_messages_hash'],
            'error':None,'dispatch_attempted':False,'outcome_unknown':False}


def count(value):
    return value if type(value) is int and value >= 0 else None


def contains_thinking(value):
    if isinstance(value, str):
        return bool(re.search(r'</?think\b',value,re.IGNORECASE))
    if isinstance(value, list): return any(contains_thinking(x) for x in value)
    if isinstance(value, dict): return any(contains_thinking(k) or contains_thinking(v) for k,v in value.items())
    return False


def normalize(p, raw, result):
    def invalid():
        result.update(status='invalid_response', content=None, parsed_json=None, response_model=None,
                      error={'code':'invalid_envelope','field':'response'})
        return result
    if not isinstance(raw, dict): return invalid()
    model = raw.get('model')
    try: string(model, 'response.model')
    except ValidationError: return invalid()
    if p['provider']=='ollama' and model != p['model']: return invalid()
    provider = p['provider']
    result['response_model'] = model
    refusal = tools = False
    unexpected_thinking = False
    if provider == 'ollama':
        m = raw.get('message')
        if raw.get('done') is not True or not isinstance(m,dict) or m.get('role') != 'assistant': return invalid()
        content, finish = m.get('content'), raw.get('done_reason')
        tools = bool(m.get('tool_calls'))
        unexpected_thinking = bool(m.get('thinking'))
        result['usage'].update(input_tokens=count(raw.get('prompt_eval_count')),output_tokens=count(raw.get('eval_count')))
        duration=count(raw.get('total_duration'))
        if duration is not None: result['usage']['provider_duration_ms'] = duration / 1_000_000
    elif provider == 'openai_chat':
        choices = raw.get('choices')
        if not isinstance(choices,list) or len(choices)!=1 or not isinstance(choices[0],dict): return invalid()
        m = choices[0].get('message')
        if not isinstance(m,dict) or m.get('role')!='assistant': return invalid()
        content, finish = m.get('content'), choices[0].get('finish_reason')
        refusal = bool(m.get('refusal'))
        tools = bool(m.get('tool_calls')) or bool(m.get('function_call'))
        usage=raw.get('usage')
        if isinstance(usage,dict): result['usage'].update(input_tokens=count(usage.get('prompt_tokens')),output_tokens=count(usage.get('completion_tokens')))
    else:
        if raw.get('role') != 'assistant' or raw.get('type') != 'message' or not isinstance(raw.get('content'),list): return invalid()
        parts=[]
        for block in raw['content']:
            if not isinstance(block,dict): return invalid()
            kind=block.get('type')
            if kind == 'text':
                if not isinstance(block.get('text'),str): return invalid()
                parts.append(block['text'])
            elif kind in ('thinking','redacted_thinking'): continue
            elif kind == 'refusal': refusal=True
            else: tools=True
        content, finish = ''.join(parts), raw.get('stop_reason')
        usage=raw.get('usage')
        if isinstance(usage,dict): result['usage'].update(input_tokens=count(usage.get('input_tokens')),output_tokens=count(usage.get('output_tokens')))
    if unexpected_thinking or contains_thinking(content):
        result.update(status='unsupported_response',error={'code':'unexpected_thinking','field':'response'})
        return result
    # Only recognized enum values are retained; raw error/unknown block contents never escape.
    known=('stop','end_turn','stop_sequence','length','max_tokens','refusal','content_filter','tool_calls','tool_use','function_call')
    result['finish_reason'] = finish if isinstance(finish,str) and finish in known else None
    if refusal or finish in ('refusal','content_filter'):
        result['status']='refused'
    elif tools or finish in ('tool_calls','tool_use','function_call'):
        result['status']='unsupported_response'
    elif finish in ('length','max_tokens'):
        result['status']='truncated'
    elif finish not in (('end_turn','stop_sequence') if provider=='anthropic_messages' else ('stop',)):
        result['status']='unsupported_response'
    elif not isinstance(content,str) or not content.strip():
        return invalid()
    else:
        result['status']='complete'
        if p['response_mode']=='json_object':
            try:
                parsed=strict_json(content,'response.content')
                if not isinstance(parsed,dict): raise ValidationError('response.content')
                if contains_thinking(parsed):
                    result.update(status='unsupported_response',error={'code':'unexpected_thinking','field':'response'})
                    return result
                result['parsed_json']=parsed
            except ValidationError:
                result.update(status='invalid_response',error={'code':'invalid_json_object','field':'response.content'})
                return result
        result['content']=content
    return result


def verify_digest(p, send):
    data=send('GET',p['base_url'].rstrip('/')+'/api/tags',{'Accept':'application/json'},None,p['timeout_seconds'])
    if not isinstance(data,dict) or not isinstance(data.get('models'),list):
        raise TransportError('invalid_model_inventory')
    matches=[m for m in data['models'] if isinstance(m,dict) and (m.get('name')==p['model'] or m.get('model')==p['model'])]
    if len(matches)!=1 or matches[0].get('digest')!=p['identity']['expected_digest']:
        raise TransportError('model_identity_mismatch')


def configuration_required(profile):
    return profile['identity'].get('validation_status')=='example_requires_configuration' or profile['model'].startswith('EXAMPLE_')


def invoke(config, role, messages, *, transport=None, key_resolver=None):
    request=preview(config,role,messages)
    p=config['profiles'][config['roles'][role]]
    result=result_base(p,role,request)
    if configuration_required(p):
        result['error']={'code':'configuration_required','phase':'preflight'}
        return result
    send=transport if transport is not None else http_transport
    resolver=key_resolver if key_resolver is not None else os.environ.get
    start=time.monotonic()
    phase='preflight'
    try:
        headers={'Content-Type':'application/json','Accept':'application/json'}
        if p['mode']=='api':
            key=resolver(p['api_key_env'])
            if not isinstance(key,str) or not key.strip(): raise TransportError('missing_api_key')
            if not key.isascii() or any(ord(c)<=32 or ord(c)==127 for c in key): raise TransportError('invalid_api_key')
            headers['Authorization']='Bearer '+key
            if p['provider']=='anthropic_messages': headers['anthropic-version']='2026-10-21'
            result['identity_verification']['status']='api_requested_identity_only'
        else:
            verify_digest(p,send)
            result['identity_verification'].update(status='preflight_verified',before=True)
        phase='dispatch'
        result['dispatch_attempted']=True
        raw=send('POST',request['url'],headers,request['body'],p['timeout_seconds'])
        phase='postflight'
        if p['provider']=='ollama':
            verify_digest(p,send)
            result['identity_verification'].update(status='verified',after=True)
        normalize(p,raw,result)
    except TransportError as e:
        allowed_codes = {'response_too_large','invalid_response_json','redirect_denied','http_401','http_403','http_429','http_5xx','http_error','timeout','connection_error','invalid_model_inventory','model_identity_mismatch','missing_api_key','invalid_api_key'}
        safe_code = e.code if e.code in allowed_codes else 'transport_error'
        result.update(status='invalid_response' if safe_code=='invalid_response_json' else 'error',content=None,parsed_json=None,error={'code':safe_code,'phase':phase},
                      outcome_unknown=bool(phase=='dispatch' and e.outcome_unknown))
        if phase=='postflight': result['identity_verification']['status']='postflight_failed'
    except Exception:
        # Injected transports/resolvers may contain secrets in exceptions too.
        result.update(status='error',content=None,parsed_json=None,error={'code':'internal_error','phase':phase},
                      outcome_unknown=phase=='dispatch')
    result['elapsed_ms']=round((time.monotonic()-start)*1000,3)
    return result
