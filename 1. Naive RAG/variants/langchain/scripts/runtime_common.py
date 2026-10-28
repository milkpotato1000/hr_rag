"""Shared, dependency-free local runtime boundary. No remote endpoints."""
import hashlib
import importlib.metadata
import platform
import json
import math
import os
from pathlib import Path, PurePosixPath
import socket
import tarfile
from urllib import request, parse

import evaluate_retrieval as evaluation

STAGE = Path(__file__).resolve().parents[1]
RUNTIME = STAGE / '.runtime'
BINARY = RUNTIME / 'ollama/ollama'
LOCK = STAGE / 'runtime-lock.json'
ENDPOINT = 'http://127.0.0.1:11434'
VERSION = '0.40.8'
MODEL = 'bge-m3:567m'
ARCHIVE_URL = 'https://github.com/ollama/ollama/releases/download/v0.40.8/ollama-darwin.tgz'
ARCHIVE_SHA = '29fce20c736f62aa8885b1e83552c5fd8dcc63edc5ffc1b47f2de591a06cde44'


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def env():
    result = os.environ.copy()
    result.update(OLLAMA_HOST='127.0.0.1:11434', OLLAMA_MODELS=str(RUNTIME / 'models'),
                  OLLAMA_NO_CLOUD='1', OLLAMA_MAX_LOADED_MODELS='1',
                  UV_CACHE_DIR=str(RUNTIME / 'uv-cache'), UV_PYTHON_INSTALL_DIR=str(RUNTIME / 'python'),
                  UV_PYTHON_BIN_DIR=str(RUNTIME / 'bin'), UV_NO_MODIFY_PATH='1', UV_PYTHON_PREFERENCE='only-managed')
    return result


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LocalAPI:
    def __init__(self, endpoint=ENDPOINT, timeout=120):
        parsed = parse.urlsplit(endpoint)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', '::1')
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError('only numeric HTTP loopback endpoints are allowed')
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be positive and finite')
        self.endpoint, self.timeout = endpoint, timeout
        self.opener = request.build_opener(request.ProxyHandler({}), NoRedirect())

    def call(self, route, body=None):
        raw = json.dumps(body, allow_nan=False).encode() if body is not None else None
        req = request.Request(self.endpoint + route, data=raw, headers={'Content-Type': 'application/json'})
        with self.opener.open(req, timeout=self.timeout) as response:
            value = json.loads(response.read().decode('utf-8'), object_pairs_hook=evaluation.unique_object,
                               parse_constant=evaluation.reject_constant)
        if not isinstance(value, dict) or value.get('error'):
            raise ValueError('invalid Ollama response or server error')
        return value

    def model(self):
        rows = self.call('/api/tags').get('models')
        if not isinstance(rows, list):
            raise ValueError('invalid model list')
        found = [m for m in rows if isinstance(m, dict) and m.get('name') == MODEL]
        if len(found) != 1:
            raise ValueError('expected local model is missing or duplicated: ' + MODEL)
        digest = found[0].get('digest')
        value = digest.removeprefix('sha256:') if isinstance(digest, str) else ''
        if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('model digest is not a full SHA-256')
        return found[0]

    def check(self, lock):
        if self.call('/api/version').get('version') != lock['ollama']['version']:
            raise ValueError('Ollama runtime differs from lock')
        if self.model()['digest'] != lock['model']['digest']:
            raise ValueError('model digest changed; review lock and rebuild index')

    def embed(self, texts, dimension):
        if not isinstance(texts, list) or not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError('embedding inputs must be nonempty text strings')
        result = self.call('/api/embed', {'model': MODEL, 'input': texts, 'truncate': False})
        if result.get('model') != MODEL:
            raise ValueError('embedding response model mismatch')
        vectors = result.get('embeddings')
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise ValueError('embedding response count mismatch')
        for vector in vectors:
            validate_vector(vector, dimension)
        return vectors


def validate_vector(vector, dimension):
    if type(dimension) is not int or dimension <= 0 or not isinstance(vector, list) or len(vector) != dimension:
        raise ValueError('invalid vector dimension')
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in vector):
        raise ValueError('vector values must be finite numbers')
    if math.hypot(*vector) == 0:
        raise ValueError('zero vector is not allowed')


def load_lock(path=LOCK):
    value = json.loads(Path(path).read_text())
    if (value['ollama']['version'] != VERSION or value['ollama']['archive_sha256'] != ARCHIVE_SHA
            or value['model']['name'] != MODEL or value['model']['dimension'] != 1024
            or value['qdrant_client_version'] != '1.19.1'):
        raise ValueError('runtime lock differs from P003 contract')
    if platform.python_version() != value['python_version']:
        raise ValueError('use the locked Python patch in .venv')
    dependencies = STAGE / 'requirements.lock'
    if sha256(dependencies) != value['dependencies_sha256']:
        raise ValueError('dependency lock hash mismatch')
    for line in dependencies.read_text().splitlines():
        if line.strip() and not line.startswith('#'):
            package, version = line.split('==')
            if importlib.metadata.version(package) != version:
                raise ValueError('installed dependency differs from lock: ' + package)
    return value


def port_open():
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex(('127.0.0.1', 11434)) == 0


def safe_extract(archive, destination):
    destination = Path(destination).resolve()
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                raise ValueError('unsafe archive entry: ' + member.name)
            target = destination / member.name
            if member.issym() or member.islnk():
                link = (target.parent if member.issym() else destination) / member.linkname
                if not link.resolve().is_relative_to(destination):
                    raise ValueError('archive link escapes destination')
            if not target.resolve().is_relative_to(destination):
                raise ValueError('archive path escapes destination')
        # All official links are checked to stay inside this new, owned tree.
        source.extractall(destination)
