"""Local, pinned single-logit CrossEncoder protocol (P020). No SDK import on replay."""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
from .embedding import LOCK, versions as installed_versions
from .storage import RagError, require, fingerprint, read_json

CATALOG = {
    'BAAI/bge-reranker-v2-m3': {'limit': 8192, 'license': 'Apache-2.0'},
    'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1': {'limit': 512, 'license': 'Apache-2.0'},
}
POLICY = {'scorer': 'raw-single-logit-v1', 'activation': 'identity', 'softmax': False,
          'prompt': '', 'truncation': False, 'special_tokens': True, 'korean_quality': 'unverified'}
DEFAULTS = {'device': 'cpu', 'dtype': 'float32', 'max_pair_tokens': 512, 'batch_size': 1, 'timeout_seconds': 120}


SDK_VERSIONS={'sentence-transformers':'6.3.0','torch':'2.15.0','transformers':'5.24.1','tokenizers':'0.23.3','safetensors':'0.8.0'}

def versions():
    actual=installed_versions()
    require(actual==SDK_VERSIONS,'reranker_sdk_mismatch','reranking')
    return actual


def strict(value, keys, code='invalid_rerank_input'):
    require(isinstance(value, dict) and set(value) == set(keys), code, 'reranking')


def integer(value, lo, hi, code='invalid_rerank_input'):
    require(type(value) is int and lo <= value <= hi, code, 'reranking')


def profile(value):
    require(isinstance(value, dict), 'invalid_reranker_profile', 'reranking')
    p = dict(DEFAULTS, **value)
    strict(p, {'schema_version', 'model_id', 'revision', 'local_path', 'file_manifest'} | set(DEFAULTS), 'invalid_reranker_profile')
    require(type(p['schema_version']) is int and p['schema_version'] == 1, 'invalid_reranker_profile', 'reranking')
    require(isinstance(p['model_id'], str) and p['model_id'] in CATALOG, 'unsupported_reranker', 'reranking')
    require(isinstance(p['revision'], str) and re.fullmatch('[0-9a-f]{40}', p['revision']), 'invalid_revision', 'reranking')
    require(isinstance(p['local_path'], str) and p['local_path'], 'invalid_model_path', 'reranking')
    require(p['device'] in ('cpu', 'mps') and p['dtype'] == 'float32', 'unsupported_runtime', 'reranking')
    for key, limit in [('max_pair_tokens', CATALOG[p['model_id']]['limit']), ('batch_size', 8), ('timeout_seconds', 300)]:
        integer(p[key], 1, limit, 'invalid_reranker_profile')
    require(isinstance(p['file_manifest'], dict) and len(p['file_manifest']) <= 100, 'invalid_file_manifest', 'reranking')
    for name, h in p['file_manifest'].items():
        require(isinstance(name, str) and name and '\\' not in name, 'invalid_file_manifest', 'reranking')
        path = PurePosixPath(name)
        require(str(path) == name and not path.is_absolute() and '..' not in path.parts and isinstance(h, str) and re.fullmatch('[0-9a-f]{64}', h), 'invalid_file_manifest', 'reranking')
    return p


def configured(p):
    return p['revision'] != '0'*40 and bool(p['file_manifest']) and not p['local_path'].startswith('EXAMPLE_')


def read_profile(path):
    p = profile(read_json(path))
    if not Path(p['local_path']).is_absolute() and not p['local_path'].startswith('EXAMPLE_'):
        p['local_path'] = str(Path(path).absolute().parent / p['local_path'])
    return p


def identity(p):
    return {k: p[k] for k in ('model_id', 'revision', 'file_manifest', 'device', 'dtype', 'max_pair_tokens')} | {'pair_policy': POLICY}


def check_files(p):
    require(configured(p), 'reranker_configuration_required', 'reranking')
    root = Path(p['local_path']).absolute()
    require(root.is_dir() and all(not x.is_symlink() for x in (root, *root.parents)), 'unsafe_model_path', 'reranking')
    actual = []; total = 0
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'unsafe_model_path', 'reranking')
        if path.is_dir(): continue
        require(path.is_file(), 'unsafe_model_file', 'reranking')
        actual.append(path.relative_to(root).as_posix()); total += path.stat().st_size
        require(len(actual) <= 100 and total <= 4*1024**3, 'model_file_limit', 'reranking')
    require(set(actual) == set(p['file_manifest']), 'model_manifest_mismatch', 'reranking')
    require('config.json' in actual and any(x.endswith('.safetensors') for x in actual), 'model_structure_required', 'reranking')
    # Accept a plain Transformers classifier export only; never load arbitrary ST modules.
    require('modules.json' not in actual and not any(Path(x).suffix.lower() in ('.bin','.pt','.pth','.pkl','.pickle','.py','.so','.dylib') for x in actual), 'unsafe_model_file', 'reranking')
    for name, expected in p['file_manifest'].items():
        h = hashlib.sha256()
        with (root/name).open('rb') as f:
            for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
        require(h.hexdigest() == expected, 'model_file_hash_mismatch', 'reranking')
    cfg = read_json(root/'config.json')
    require(cfg.get('architectures') == ['XLMRobertaForSequenceClassification'] and cfg.get('model_type') == 'xlm-roberta' and not cfg.get('auto_map'), 'unsupported_classifier', 'reranking')
    labels = cfg.get('num_labels', len(cfg.get('id2label', {})))
    require(type(labels) is int and labels == 1, 'classifier_head_mismatch', 'reranking')
    for name in actual:
        if name.endswith('.json'):
            v = read_json(root/name)
            require(not isinstance(v, dict) or not v.get('auto_map'), 'custom_code_forbidden', 'reranking')
    return root


def validate_scores(response, ids):
    require(isinstance(response, dict) and isinstance(response.get('scores'), list), 'invalid_scores', 'reranking')
    rows = response['scores']
    require(len(rows) == len(ids), 'score_count', 'reranking')
    for row in rows:
        strict(row, {'chunk_id', 'score'}, 'invalid_scores')
        require(isinstance(row['chunk_id'], str) and type(row['score']) in (int, float) and math.isfinite(row['score']), 'invalid_scores', 'reranking')
    require([r['chunk_id'] for r in rows] == ids and len(set(ids)) == len(ids), 'score_id_mapping', 'reranking')
    return rows


def score(p, question, rows, *, backend=None):
    p = profile(p); ids = [r['chunk_id'] for r in rows]
    payload = {'profile': p, 'query': question, 'passages': [r['text'] for r in rows], 'ids': ids}
    started = time.monotonic()
    work = {'requested_pairs': len(rows), 'attempted_pairs': 0, 'pairs': 0, 'queries': 0,
            'workers': 0, 'fixture_calls': 0, 'worker_exited': None, 'retry_count': 0,
            'execution_kind': 'test_fixture' if backend else 'local_hf', 'load_ms': None, 'score_ms': None,
            'peak_rss_bytes': None, 'rss_method': 'unavailable', 'sdk_versions': None,
            'pair_tokens': None, 'applied_limit': None, 'preprocessing_hash': None,
            'benchmark': 'cold owned worker; not warm latency'}
    try:
        with LOCK:
            if backend is not None:
                work.update(fixture_calls=1, attempted_pairs=len(rows), queries=1, pairs=None)
                response = backend(payload)
            else:
                check_files(p); versions()
                from .owned_worker import invoke
                monitor={};work['monitor']=monitor
                def on_started():work.update(workers=1,attempted_pairs=len(rows),queries=1,worker_exited=False,pairs=None)
                try:
                    stdout,_,returncode=invoke('rag_package.reranker_worker',payload,p['timeout_seconds'],observation=monitor,on_started=on_started,stage='reranking',timeout_code='reranker_timeout')
                finally:work['worker_exited']=monitor.get('worker_exited')
                require(returncode==0,'reranker_worker_failed','reranking')
                try: response = json.loads(stdout)
                except ValueError: raise RagError('reranker_worker_failed', 'reranking') from None
            require(isinstance(response, dict), 'invalid_scores', 'reranking')
            if 'weight_validation' in response: work['weight_validation'] = response['weight_validation']
            if response.get('error'):
                if response['error'] in ('pair_too_long','model_pair_limit','classifier_head_mismatch'): work['pairs'] = 0
                err = RagError(response['error'], 'reranking'); err.offending_ids = response.get('offending_ids', []); raise err
            scores = validate_scores(response, ids)
            work.update({k: response.get(k) for k in ('load_ms','score_ms','peak_rss_bytes','sdk_versions','pair_tokens','applied_limit','preprocessing_hash')})
            work['rss_method'] = response.get('rss_method','unavailable'); work['pairs'] = len(rows)
    except (KeyboardInterrupt,SystemExit) as e:
        work['elapsed_ms']=(time.monotonic()-started)*1000;e.work=work;raise
    except (RagError,OSError,UnicodeError) as e:
        err = e if isinstance(e,RagError) else RagError('reranker_io_failed','reranking')
        work['elapsed_ms'] = (time.monotonic()-started)*1000
        err.work = work; err.dispatch_attempted = bool(work['workers'] or work['fixture_calls']); raise err from None
    work['elapsed_ms'] = (time.monotonic()-started)*1000
    return scores, work
