"""Acquire only the reviewed P019 model into Ollama's cache; never restart it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from urllib.request import build_opener, ProxyHandler, Request

MODEL = 'qwen3:8b'
MANIFEST = '500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41'
LAYER = 'a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f'
REGISTRY = 'https://registry.ollama.ai/v2/library/qwen3/'
LIMIT = 6 * 1024**3


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--server-cache', type=Path, required=True,
                        help='Read from the running server OLLAMA_MODELS; never assume the home default')
    args = parser.parse_args()
    out = args.evidence
    out.mkdir(parents=True, exist_ok=True)
    record_path = out / 'download.json'
    record = json.loads(record_path.read_text()) if record_path.exists() else dict(
        bytes_downloaded=0, seconds=0, attempts=[], completed=False)
    opener = build_opener(ProxyHandler({}))
    def http(url, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        with opener.open(Request(url, data=body, headers={'Content-Type': 'application/json'}), timeout=30) as r:
            return r.read()
    def api(route, payload=None):
        return json.loads(http('http://127.0.0.1:11434/api/' + route, payload))
    assert not api('ps')['models'], 'Other model is loaded; no automatic eviction'
    before = api('tags')
    raw = http(REGISTRY + 'manifests/8b')
    assert sha(raw) == MANIFEST, 'Official tag changed'
    manifest = json.loads(raw)
    layers = [manifest['config']] + manifest['layers']
    model = [x for x in layers if x['mediaType'] == 'application/vnd.ollama.image.model']
    assert len(model) == 1 and model[0]['digest'] == 'sha256:' + LAYER and model[0]['size'] == 5225374496
    assert sum(x['size'] for x in layers) < LIMIT
    cache = Path.home() / '.ollama/models'
    server_cache = args.server_cache.resolve()
    assert server_cache.is_dir(), 'Existing running-server cache must be identified first'
    assert shutil.disk_usage(cache.parent).free >= 12 * 1024**3
    assert record['seconds'] < 1800 and record['bytes_downloaded'] < LIMIT
    started = time.monotonic()
    attempt = dict(status='started', bytes=0)
    record['attempts'].append(attempt)
    def save():
        temp = record_path.with_suffix('.tmp')
        temp.write_text(json.dumps(record, indent=2) + '\n')
        os.replace(temp, record_path)
    save()
    try:
        for layer in layers:
            digest = layer['digest'].split(':')[1]
            dest = cache / 'blobs' / ('sha256-' + digest)
            if dest.exists():
                assert dest.stat().st_size == layer['size'] and file_sha(dest) == digest, 'Existing cache mismatch'
                continue
            assert record['bytes_downloaded'] + layer['size'] <= LIMIT
            dest.parent.mkdir(parents=True, exist_ok=True)
            partial = dest.with_name(dest.name + '.p019-partial')
            assert not partial.exists(), 'Interrupted download requires review; no silent restart'
            h = hashlib.sha256(); received = 0
            with opener.open(REGISTRY + 'blobs/sha256:' + digest, timeout=30) as response, partial.open('xb') as f:
                while True:
                    assert record['seconds'] + time.monotonic() - started < 1800, 'Download time budget'
                    block = response.read(min(4 * 1024**2, layer['size'] - received + 1))
                    if not block:
                        break
                    received += len(block)
                    record['bytes_downloaded'] += len(block); attempt['bytes'] += len(block)
                    save()
                    assert received <= layer['size'] and record['bytes_downloaded'] <= LIMIT, 'Download byte budget'
                    f.write(block); h.update(block)
            assert received == layer['size'] and h.hexdigest() == digest, 'Layer content mismatch'
            os.replace(partial, dest)
            print('Verified layer', digest, received, flush=True)
        # Reuse verified external cache bytes. Symlinks do not copy weights into
        # the repository when the existing server uses an ignored runtime folder.
        for layer in layers:
            name = layer['digest'].replace(':', '-')
            existing = server_cache / 'blobs' / name
            source = cache / 'blobs' / name
            if existing.exists():
                assert existing.stat().st_size == layer['size'] and file_sha(existing) == layer['digest'].split(':')[1]
            else:
                assert not existing.is_symlink(), 'Broken pre-existing cache link'
                existing.parent.mkdir(parents=True, exist_ok=True)
                existing.symlink_to(source)
        target = server_cache / 'manifests/registry.ollama.ai/library/qwen3/8b'
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == raw, 'Existing tag differs'
        else:
            target.write_bytes(raw)
        after = api('tags')
        old = {x['name']: x['digest'] for x in before['models']}
        new = {x['name']: x['digest'] for x in after['models']}
        assert all(new.get(k) == v for k, v in old.items()) and new[MODEL] == MANIFEST
        show = api('show', {'model': MODEL, 'verbose': True})
        (out / 'model-show.json').write_text(json.dumps(show, ensure_ascii=False, indent=2) + '\n')
        (out / 'runtime-after-download.json').write_text(json.dumps(after, indent=2) + '\n')
        info = show['model_info']
        assert info['tokenizer.ggml.model'] == 'gpt2' and info['tokenizer.ggml.pre'] == 'qwen2'
        assert info['tokenizer.ggml.add_bos_token'] is False and not show.get('system')
        assert show['details']['quantization_level'] == 'Q4_K_M'
        template = show['template']
        assert '.Messages' in template and '.Content' in template
        lock = dict(model=MODEL, digest=MANIFEST, model_layer=LAYER,
                    layer_hashes={x['mediaType']: x['digest'] for x in layers},
                    template=template, template_sha256=sha(template.encode()),
                    parameters=show['parameters'], parameters_sha256=sha(show['parameters'].encode()),
                    license_sha256=sha(show['license'].encode()), license='Apache-2.0',
                    tokenizer={k: v for k, v in info.items() if k.startswith('tokenizer.') and not isinstance(v, list)},
                    model_info_sha256=sha(json.dumps(info, sort_keys=True).encode()),
                    model_context=info.get('qwen3.context_length'), runtime_context=8192,
                    tokenizer_verified=True, single_user_template_review_required=True)
        (out / 'model-lock.json').write_text(json.dumps(lock, ensure_ascii=False, indent=2) + '\n')
        attempt['status'] = 'complete'; record['completed'] = True
    except Exception as exc:
        attempt.update(status='failed', error=str(exc))
        raise
    finally:
        record['seconds'] += time.monotonic() - started
        save()


if __name__ == '__main__':
    main()
