#!/usr/bin/env python3
"""Add and verify the P004 generation model without changing the embedding lock."""
import json
import subprocess
import sys
from runtime_common import BINARY, VERSION, LocalAPI, env, load_lock
from generation import MODEL, LOCK, OPTIONS, SCHEMA, metadata, Generator, strict_json, normalized_model
from evaluate_retrieval import write_atomic
import runtime


def setup():
    load_lock()
    runtime.start()
    api = LocalAPI(timeout=120)
    previous = strict_json(LOCK.read_text()) if LOCK.exists() else None
    tags = api.call('/api/tags').get('models')
    if not isinstance(tags, list):
        raise ValueError('invalid model list')
    if not any(isinstance(row, dict) and row.get('name') == MODEL for row in tags):
        subprocess.run([str(BINARY), 'pull', MODEL], env=env(), check=True, timeout=1200,
                       stdout=sys.stderr, stderr=sys.stderr)
    model = metadata(api)
    value = {'schema_version': 1, 'ollama_version': VERSION, 'model': model,
             'request': {'stream': False, 'think': False, 'options': OPTIONS, 'format': SCHEMA}}
    if previous and ({**previous, 'model': normalized_model(previous['model'])} !=
                     {**value, 'model': normalized_model(value['model'])}):
        raise ValueError('generation metadata changed; refusing lock overwrite')
    generator = Generator(api=api, lock=value)
    raw, observations = generator.generate([
        {'role': 'system', 'content': 'Return only JSON matching the schema. Do not think or explain.'},
        {'role': 'user', 'content': 'Return status abstained, answer API 확인, citations empty.'}])
    response = strict_json(raw)
    if response != {'status': 'abstained', 'answer': 'API 확인', 'citations': []}:
        raise ValueError('real non-thinking schema API smoke differs from expected response')
    if not previous:
        write_atomic(LOCK, value)
    print(json.dumps({'status': 'ready', 'model': model, 'request': value['request'],
                      'actual_probe': response, 'observations': observations}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        setup()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        sys.exit(2)
