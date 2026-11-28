"""Strict, offline configuration and message validation."""
import ipaddress
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit, unquote

INPUT_LIMIT = 2 * 1024 * 1024

class ValidationError(ValueError):
    def __init__(self, field, code='invalid_input'):
        self.field, self.code = field, code
        super().__init__(code + ': ' + field)


def strict_json(text, field='json'):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    def constant(_):
        raise ValueError()
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
        def finite(v):
            if isinstance(v, float) and not math.isfinite(v):
                raise ValueError()
            if isinstance(v, dict):
                for x in v.values(): finite(x)
            elif isinstance(v, list):
                for x in v: finite(x)
        finite(value)
        return value
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise ValidationError(field, 'invalid_json') from None


def read_json(path):
    try:
        with Path(path).open('rb') as f:
            raw = f.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            raise ValidationError('input_file', 'input_too_large')
        return strict_json(raw.decode('utf-8'), 'input_file')
    except (OSError, UnicodeError):
        raise ValidationError('input_file', 'unreadable_input') from None


def fields(value, required, optional, field):
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValidationError(field)


def string(value, field):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValidationError(field)
    return value


def number(value, lo, hi, field, integer=False):
    if type(value) not in ((int,) if integer else (int, float)) or not lo <= value <= hi or (type(value) is float and not math.isfinite(value)):
        raise ValidationError(field)


def url(value, mode):
    string(value, 'profile.base_url')
    try:
        p = urlsplit(value)
        decoded = value
        for _ in range(4):
            new = unquote(decoded)
            if new == decoded: break
            decoded = new
        if '%' in decoded or any(ord(c) <= 32 or ord(c) == 127 for c in decoded) or '\\' in decoded:
            raise ValueError()
        if p.username is not None or p.password is not None or p.query or p.fragment or '?' in value or '#' in value:
            raise ValueError()
        if not p.hostname or p.port == 0 or any(x in ('.','..') for x in urlsplit(decoded).path.split('/')):
            raise ValueError()
        if mode == 'local':
            if p.scheme != 'http' or not ipaddress.ip_address(p.hostname).is_loopback:
                raise ValueError()
        elif p.scheme != 'https':
            raise ValueError()
        return value.rstrip('/')
    except ValueError:
        raise ValidationError('profile.base_url') from None


def validate_config(config):
    fields(config, {'schema_version','profiles','roles'}, set(), 'config')
    if type(config['schema_version']) is not int or config['schema_version'] not in (1,2):
        raise ValidationError('schema_version')
    profiles = config['profiles']
    if not isinstance(profiles, dict) or not profiles:
        raise ValidationError('profiles')
    for name, p in profiles.items():
        string(name, 'profile_name')
        fields(p, {'mode','provider','model','base_url','max_output_tokens','timeout_seconds','response_mode','identity'},
               {'api_key_env','temperature','num_ctx','seed','think'}, 'profile')
        provider = p['provider']
        if 'think' in p and (provider != 'ollama' or type(p['think']) is not bool):
            raise ValidationError('profile.think')
        if provider not in ('ollama','openai_chat','anthropic_messages') or p['mode'] != ('local' if provider == 'ollama' else 'api'):
            raise ValidationError('profile.provider_or_mode')
        string(p['model'], 'profile.model')
        url(p['base_url'], p['mode'])
        number(p['max_output_tokens'], 1, 32768, 'profile.max_output_tokens', True)
        number(p['timeout_seconds'], 1, 600, 'profile.timeout_seconds')
        if p['response_mode'] not in ('text','json_object'):
            raise ValidationError('profile.response_mode')
        if p.get('temperature') is not None:
            number(p['temperature'], 0, 2, 'profile.temperature')
        ident = p['identity']
        if provider == 'ollama':
            if 'api_key_env' in p: raise ValidationError('profile.api_key_env')
            if 'num_ctx' in p: number(p['num_ctx'], 512, 131072, 'profile.num_ctx', True)
            if 'seed' in p: number(p['seed'], 0, 2**31-1, 'profile.seed', True)
            fields(ident, {'expected_digest','hf_id','conversion'}, {'source_revision','quantization','license_url','validation_status'}, 'identity')
            if not isinstance(ident['expected_digest'], str) or not re.fullmatch('[0-9a-f]{64}', ident['expected_digest']):
                raise ValidationError('identity.expected_digest')
            for k in ('hf_id','conversion'): string(ident[k], 'identity.'+k)
        else:
            if 'seed' in p or 'num_ctx' in p: raise ValidationError('profile.local_only_options')
            if not isinstance(p.get('api_key_env'), str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', p['api_key_env']):
                raise ValidationError('profile.api_key_env')
            fields(ident, {'requested_model','revision_pinned','revision'}, {'validation_status'}, 'identity')
            if ident['requested_model'] != p['model'] or type(ident['revision_pinned']) is not bool:
                raise ValidationError('identity.model_or_revision_pinned')
            if ident['revision_pinned'] and ident['revision'] in (None, 'unknown'):
                raise ValidationError('identity.revision')
        for k,v in ident.items():
            if k == 'revision_pinned': continue
            if v is None and k in ('source_revision','revision'): continue
            string(v, 'identity.'+k)
    roles={'generation','evaluation'} | ({'chunking'} if config['schema_version']==2 else set())
    fields(config['roles'], roles, set(), 'roles')
    for role in roles:
        name = config['roles'][role]
        if not isinstance(name,str) or name not in profiles:
            raise ValidationError('roles.'+role)
    return config


def validate_messages(messages):
    if not isinstance(messages,list) or not messages:
        raise ValidationError('messages')
    next_role = 'user'
    for i,m in enumerate(messages):
        fields(m, {'role','content'}, set(), 'messages.item')
        if not isinstance(m['content'], str) or not m['content'].strip():
            raise ValidationError('messages.content')
        if i == 0 and m['role'] == 'system': continue
        if m['role'] != next_role:
            raise ValidationError('messages.role_order')
        next_role = 'assistant' if next_role == 'user' else 'user'
    if messages[-1]['role'] != 'user':
        raise ValidationError('messages.last_role')
    return messages
