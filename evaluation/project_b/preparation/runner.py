"""Serial loopback-only runner with durable reservations and no automatic timeout retry."""
import fcntl
import json
import socket
import subprocess
import threading
import time
from urllib import request, error
from core import read, write, digest, preflight, validate_output, MODEL, DIGEST
from prepare import verify_frozen, active_cases


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def http(route, body=None, timeout=10):
    raw = json.dumps(body, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode() if body is not None else None
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    req = request.Request('http://127.0.0.1:11434/api/' + route, data=raw, headers={'Content-Type': 'application/json'})
    with opener.open(req, timeout=timeout) as r:
        value = json.loads(r.read())
    if not isinstance(value, dict) or value.get('error'):
        raise ValueError('provider response error')
    return value


class Ledger:
    def __init__(self, out, frozen):
        self.out = out; self.path = out / 'ledger.json'; self.frozen = frozen
        if not self.path.exists():
            write(self.path, dict(frozen_sha256=frozen, calls=[], pending=None, unresolved=False, seconds=0))

    def state(self):
        s = read(self.path)
        if s['frozen_sha256'] != self.frozen or [c['id'] for c in s['calls']] != list(range(1, len(s['calls']) + 1)):
            raise ValueError('ledger identity or duplicate sequence mismatch')
        if any(digest(read(self.out / c['artifact'])) != c['artifact_sha256'] for c in s['calls']):
            raise ValueError('ledger call artifact changed')
        return s

    def reserve(self, case_id, body, repeat):
        s = self.state()
        if s['pending'] or s['unresolved']:
            raise ValueError('Previous request unresolved; no automatic next call')
        if len(s['calls']) >= 34 or s['seconds'] >= 2700:
            raise ValueError('cumulative request/wall budget exhausted')
        for prefix, cap in [('smoke-',12),('repeat-',6),('gt',16)]:
            if case_id.startswith(prefix) and sum(c['case_id'].startswith(prefix) for c in s['calls'])>=cap:
                raise ValueError('category request budget exhausted: '+prefix)
        prior = [c for c in s['calls'] if c['case_id'] == case_id and c['payload_sha256'] == digest(body)]
        if len(prior) >= (1 if repeat else 2):
            raise ValueError('per-payload retry limit')
        event = dict(id=len(s['calls']) + 1, case_id=case_id, payload_sha256=digest(body),
                     started_at=time.time(), status='reserved')
        s['pending'] = event; write(self.path, s)
        return event, min(120, 2700 - s['seconds'])

    def finish(self, event, result, unresolved=False):
        s = self.state()
        if s['pending'] != event:
            raise ValueError('reservation changed')
        artifact = 'calls/%03d.json' % event['id']
        write(self.out / artifact, result, immutable=True)
        s['calls'].append(dict(event, status=result['status'], seconds=result['seconds'],
                               artifact=artifact, artifact_sha256=digest(result)))
        s['seconds'] += result['seconds']; s['pending'] = None; s['unresolved'] = unresolved
        write(self.path, s)


def semantic(case, value):
    if 'expected_label' in case:
        return value['label'] == case['expected_label']
    if 'expected_equivalent' in case:
        return value['equivalent'] == case['expected_equivalent']
    if 'expected_quotes' in case:
        return [c['quote'] for c in value['claims']] == case['expected_quotes']
    if 'required_fragments' in case:
        return all(s in value['answer'] for s in case['required_fragments'])
    return None  # Reference draft semantics are reviewed against source by Codex, then human.


def verify_runtime(lock):
    if http('version')['version'] != '0.40.8':
        raise ValueError('runtime changed')
    tags = {m['name']: m['digest'] for m in http('tags')['models']}
    if tags.get(MODEL) != DIGEST:
        raise ValueError('model tag changed')
    if http('ps')['models']:
        raise ValueError('Other model activity/loading present; no eviction or restart')
    show = http('show', {'model': MODEL})
    # Ollama serializes parameter-map keys in non-deterministic order. Compare
    # the full multiset of key/value lines; preserve duplicate stop entries.
    params = lambda text: sorted(tuple(line.split(None, 1)) for line in text.splitlines() if line.strip())
    if show['template'] != lock['template'] or show.get('system') or params(show['parameters']) != params(lock['parameters']):
        raise ValueError('model template/parameters changed')
    for k, v in lock['tokenizer'].items():
        if show['model_info'].get(k) != v:
            raise ValueError('tokenizer changed: ' + k)


def sample_memory(stop, samples):
    while not stop.is_set():
        try:
            text = subprocess.check_output(['ps', '-axo', 'pid=,rss=,comm='], text=True)
            rows = [line.split(None, 2) for line in text.splitlines() if 'ollama' in line.lower()]
            samples.append(dict(at=time.time(), ollama_process_rss_bytes=sum(int(r[1])*1024 for r in rows),
                                process_count=len(rows)))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        stop.wait(1)


def invoke(out, ledger, case, case_id, repeat=False):
    verify_frozen(out)
    lock = read(out / 'model-lock.json'); body = case['payload']
    if not any(c['id']==case['id'] and c['payload']==body for c in active_cases(out)):
        raise ValueError('payload not in active frozen cases')
    bound = preflight(body, lock); verify_runtime(lock)
    event, timeout = ledger.reserve(case_id, body, repeat)
    result = dict(case_id=case_id, original_case_id=case['id'], payload=body, input_bound=bound,
                  status='failed', semantic_match=None)
    started = time.monotonic(); stop = threading.Event(); samples = []
    monitor = threading.Thread(target=sample_memory, args=(stop, samples), daemon=True); monitor.start()
    unresolved = False
    try:
        response = http('chat', body, timeout)
        result['raw_response'] = response
        if response.get('model') != MODEL or response.get('done') is not True or response.get('done_reason') != 'stop':
            raise ValueError('partial or unexpected model output')
        if response['message'].get('thinking'):
            raise ValueError('unexpected thinking output despite think=false')
        content = response['message']['content']
        def unique(items):
            value = {}
            for k,v in items:
                if k in value: raise ValueError('duplicate output key')
                value[k]=v
            return value
        value = json.loads(content, object_pairs_hook=unique)
        result['resolved'] = validate_output(case, value)
        result.update(status='valid', parsed=value, semantic_match=semantic(case, value))
    except Exception as exc:
        result['error'] = str(exc)
        unresolved = isinstance(exc, (TimeoutError, socket.timeout, error.URLError)) and not isinstance(exc, error.HTTPError)
    finally:
        stop.set(); monitor.join(timeout=2)
        result.update(seconds=time.monotonic()-started, memory_samples=samples,
                      memory_scope='1-second sampled sum of Ollama process RSS, including server/runner; not true peak, GPU allocation, or system memory',
                      max_sampled_rss_bytes=max([s['ollama_process_rss_bytes'] for s in samples] or [0]))
        ledger.finish(event, result, unresolved)
    print(case_id, result['status'], 'semantic:', result['semantic_match'], 'seconds:', round(result['seconds'], 2), flush=True)
    if unresolved:
        raise ValueError('Timeout/transport state unresolved; next invocation blocked')
    return result


def run(out):
    frozen = verify_frozen(out)
    with (out / '.runner.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger = Ledger(out, frozen['sha256'])
        s = ledger.state()
        if s['pending'] or s['unresolved']:
            raise ValueError('Unresolved prior invocation requires review')
        cases = active_cases(out)
        for case in cases[:6]:
            prior = [c for c in ledger.state()['calls'] if c['case_id'] == case['id'] and c['payload_sha256']==case['payload_sha256']]
            while not any(c['status'] == 'valid' for c in prior) and len(prior) < 2:
                invoke(out, ledger, case, case['id'])
                prior = [c for c in ledger.state()['calls'] if c['case_id'] == case['id'] and c['payload_sha256']==case['payload_sha256']]
        successes = {c['case_id']: read(out / c['artifact']) for c in ledger.state()['calls'] if c['status'] == 'valid'}
        if any(case['id'] not in successes for case in cases[:6]):
            raise ValueError('Smoke schema/provenance compatibility incomplete; no ground-truth calls')
        for case in cases[:6]:
            rid = 'repeat-' + case['id']
            if not any(c['case_id'] == rid for c in ledger.state()['calls']):
                invoke(out, ledger, case, rid, repeat=True)
        for case in cases[6:]:
            prior = [c for c in ledger.state()['calls'] if c['case_id'] == case['id'] and c['payload_sha256']==case['payload_sha256']]
            while not any(c['status'] == 'valid' for c in prior) and len(prior) < 2:
                invoke(out, ledger, case, case['id'])
                prior = [c for c in ledger.state()['calls'] if c['case_id'] == case['id'] and c['payload_sha256']==case['payload_sha256']]
        state = ledger.state(); comparisons = []
        for case in cases[:6]:
            originals = [read(out / c['artifact']) for c in state['calls'] if c['case_id'] == case['id'] and c['status'] == 'valid']
            repeated = [read(out / c['artifact']) for c in state['calls'] if c['case_id'] == 'repeat-' + case['id']]
            first, repeat = originals[0], repeated[0]
            comparisons.append(dict(case_id=case['id'], same_payload=digest(first['payload'])==digest(repeat['payload']),
                                    same_output=first.get('parsed')==repeat.get('parsed'),
                                    first_semantic=first['semantic_match'], repeat_semantic=repeat['semantic_match'],
                                    repeat_status=repeat['status']))
        write(out / 'repeat-results.json', comparisons, immutable=True)
