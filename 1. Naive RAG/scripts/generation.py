"""Locked local generation boundary. No retrieval or evaluation labels."""
import hashlib
import json
from pathlib import Path
from runtime_common import STAGE, VERSION, LocalAPI
import evaluate_retrieval as evaluation

MODEL = 'qwen3:4b'
LOCK = STAGE / 'generation-lock.json'
OPTIONS = {'temperature': 0, 'seed': 42, 'num_ctx': 8192, 'num_predict': 1024}
SCHEMA = {'type': 'object', 'additionalProperties': False,
          'required': ['status', 'answer', 'citations'],
          'properties': {'status': {'type': 'string', 'enum': ['answered', 'abstained']},
                         'answer': {'type': 'string', 'minLength': 1},
                         'citations': {'type': 'array', 'items': {
                             'type': 'object', 'additionalProperties': False,
                             'required': ['chunk_id', 'quote'], 'properties': {
                                 'chunk_id': {'type': 'string', 'minLength': 1},
                                 'quote': {'type': 'string', 'minLength': 1}}}}}}


def digest_text(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def strict_json(raw):
    return json.loads(raw, object_pairs_hook=evaluation.unique_object,
                      parse_constant=evaluation.reject_constant)


def metadata(api):
    rows = api.call('/api/tags').get('models')
    if not isinstance(rows, list):
        raise ValueError('invalid model list')
    matches = [row for row in rows if isinstance(row, dict) and row.get('name') == MODEL]
    if len(matches) != 1:
        raise ValueError('expected exactly one generation model: ' + MODEL)
    digest = matches[0].get('digest')
    value = digest.removeprefix('sha256:') if isinstance(digest, str) else ''
    if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('invalid full generation digest')
    show = api.call('/api/show', {'model': MODEL})
    details = show.get('details', {})
    if details.get('family') != 'qwen3' or details.get('quantization_level') != 'Q4_K_M' or details.get('parameter_size') != '4.0B':
        raise ValueError('generation model differs from Qwen3 4B Q4_K_M contract')
    if not isinstance(show.get('template'), str) or not show['template'].strip():
        raise ValueError('missing model template')
    license_text = show.get('license', '')
    if 'Apache License' not in license_text or 'Version 2.0' not in license_text:
        raise ValueError('expected Apache 2.0 license')
    return {'name': MODEL, 'digest': digest, 'details': details,
            'template': show['template'], 'parameters': show.get('parameters', ''),
            'model_info': show.get('model_info', {}), 'capabilities': show.get('capabilities', []),
            'license': 'Apache-2.0', 'license_text_sha256': digest_text(license_text),
            'source_url': 'https://ollama.com/library/qwen3:4b'}


def load_generation_lock(path=LOCK):
    lock = strict_json(Path(path).read_text())
    if (lock['ollama_version'] != VERSION or lock['model']['name'] != MODEL
            or lock['model']['details']['quantization_level'] != 'Q4_K_M'
            or lock['request'] != {'stream': False, 'think': False, 'options': OPTIONS, 'format': SCHEMA}):
        raise ValueError('generation lock differs from P004 contract')
    return lock


class Generator:
    def __init__(self, timeout=120, api=None, lock=None):
        self.api = api or LocalAPI(timeout=timeout)
        self.lock = lock if lock is not None else load_generation_lock()

    def check(self):
        if self.api.call('/api/version').get('version') != self.lock['ollama_version']:
            raise ValueError('generation runtime differs from lock')
        if metadata(self.api) != self.lock['model']:
            raise ValueError('generation model metadata/digest differs from lock')

    def generate(self, messages):
        self.check()
        result = self.api.call('/api/chat', {'model': MODEL, 'messages': messages,
                                           **self.lock['request']})
        message = result.get('message')
        if (result.get('model') != MODEL or result.get('done') is not True
                or not isinstance(message, dict) or message.get('role') != 'assistant'
                or not isinstance(message.get('content'), str)):
            raise ValueError('invalid chat response envelope')
        # Never retain hidden thinking, even if a provider violates think=false.
        if message.get('thinking'):
            raise ValueError('provider returned thinking despite think=false')
        content = message['content']
        if '<think>' in content or '</think>' in content:
            raise ValueError('provider returned thinking in content despite think=false')
        self.check()
        return content, {key: result[key] for key in (
            'done_reason', 'total_duration', 'load_duration', 'prompt_eval_count',
            'prompt_eval_duration', 'eval_count', 'eval_duration') if key in result}
