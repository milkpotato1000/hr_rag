#!/usr/bin/env python3
"""Install only the P003 local, verified runtime and locked dependencies/model."""
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from runtime_common import (STAGE, RUNTIME, BINARY, LOCK, VERSION, MODEL, ARCHIVE_URL, ARCHIVE_SHA,
                            LocalAPI, env, sha256, safe_extract)
from evaluate_retrieval import write_atomic
import runtime


def command(args):
    subprocess.run(args, cwd=STAGE, env=env(), check=True, timeout=900)


def setup():
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('P003 runtime is pinned for macOS arm64')
    RUNTIME.mkdir(exist_ok=True)
    previous = json.loads(LOCK.read_text()) if LOCK.exists() else None
    archive = RUNTIME / 'ollama-darwin.tgz'
    if not archive.exists():
        partial = RUNTIME / 'ollama-darwin.tgz.part'
        command(['curl', '--fail', '--location', '--retry', '2', '--connect-timeout', '15', '--max-time', '600',
                 '--output', str(partial), ARCHIVE_URL])
        if sha256(partial) != ARCHIVE_SHA:
            raise ValueError('official archive SHA-256 mismatch')
        partial.rename(archive)
    if sha256(archive) != ARCHIVE_SHA:
        raise ValueError('existing archive SHA-256 mismatch')
    if not BINARY.exists():
        with tempfile.TemporaryDirectory(prefix='extract-', dir=RUNTIME) as scratch:
            extracted = Path(scratch) / 'ollama'
            safe_extract(archive, extracted)
            if not (extracted / 'ollama').is_file():
                raise ValueError('archive lacks expected binary')
            extracted.rename(BINARY.parent)
    binary_sha = sha256(BINARY)
    if previous and binary_sha != previous['ollama']['binary_sha256']:
        raise ValueError('installed Ollama binary differs from lock')

    patch = previous['python_version'] if previous else '3.12'
    command(['uv', 'python', 'install', patch, '--no-bin'])
    python = STAGE / '.venv/bin/python'
    if not python.exists():
        command(['uv', 'venv', '--python', patch, str(STAGE / '.venv')])
    dependencies = STAGE / 'requirements.lock'
    if previous and (not dependencies.exists() or sha256(dependencies) != previous['dependencies_sha256']):
        raise ValueError('dependency file changed; refusing to alter the locked environment')
    if dependencies.exists():
        command(['uv', 'pip', 'sync', '--python', str(python), str(dependencies)])
    else:
        command(['uv', 'pip', 'install', '--python', str(python), 'qdrant-client==1.19.1'])
    frozen = subprocess.run(['uv', 'pip', 'freeze', '--python', str(python)], cwd=STAGE, env=env(),
                            capture_output=True, text=True, check=True).stdout
    if not dependencies.exists():
        dependencies.write_text(frozen)
    if dependencies.read_text() != frozen:
        raise ValueError('installed dependencies differ from requirements.lock')
    info = subprocess.run([str(python), '-c', 'import sys,platform,importlib.metadata,json;print(json.dumps({"python":platform.python_version(),"qdrant":importlib.metadata.version("qdrant-client"),"binary":sys.base_prefix}))'],
                          capture_output=True, text=True, check=True)
    info = json.loads(info.stdout)
    if not info['python'].startswith('3.12.') or info['qdrant'] != '1.19.1' or not Path(info['binary']).is_relative_to(RUNTIME / 'python'):
        raise ValueError('Python/Qdrant environment is not the isolated contracted installation')
    if previous and previous['python_version'] != info['python']:
        raise ValueError('Python patch differs from runtime lock')
    runtime.start()
    api = LocalAPI(timeout=600)
    try:
        metadata = api.model()
    except ValueError:
        command([str(BINARY), 'pull', MODEL])
        metadata = api.model()
    if previous and metadata['digest'] != previous['model']['digest']:
        raise ValueError('model digest changed; refusing lock overwrite; review and rebuild index')
    show = api.call('/api/show', {'model': MODEL})
    details = show.get('details', {})
    model_info = show.get('model_info', {})
    dimension = model_info.get('bert.embedding_length')
    if dimension != 1024 or details.get('quantization_level') != 'F16' or details.get('family') != 'bert':
        raise ValueError('actual model differs from selected BGE-M3 F16/1024 contract')
    if 'MIT' not in show.get('license', ''):
        raise ValueError('expected model license not returned')
    api.embed(['가상 HR 규정 실행 확인'], dimension)
    value = {'schema_version': 1, 'python_version': info['python'], 'qdrant_client_version': info['qdrant'],
             'dependencies_sha256': sha256(dependencies),
             'ollama': {'version': VERSION, 'url': ARCHIVE_URL, 'archive_sha256': ARCHIVE_SHA,
                        'binary_sha256': binary_sha, 'license': 'MIT',
                        'license_url': 'https://github.com/ollama/ollama/blob/v0.40.8/LICENSE'},
             'model': {'name': MODEL, 'digest': metadata['digest'], 'dimension': dimension,
                       'quantization': details['quantization_level'], 'details': details, 'model_info': model_info,
                       'license': 'MIT', 'license_text_sha256': __import__('hashlib').sha256(show['license'].encode()).hexdigest(),
                       'source_url': 'https://ollama.com/library/bge-m3:567m',
                       'base_model': 'https://huggingface.co/BAAI/bge-m3'}}
    if previous and value != previous:
        raise ValueError('runtime metadata differs from existing lock; explicit review required')
    if not previous:
        write_atomic(LOCK, value)
    print(json.dumps({'status': 'ready', 'python': info['python'], 'ollama': VERSION,
                      'model': MODEL, 'digest': metadata['digest'], 'dimension': dimension}))


if __name__ == '__main__':
    try:
        setup()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        sys.exit(2)
