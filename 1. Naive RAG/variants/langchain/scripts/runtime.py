#!/usr/bin/env python3
"""Start/status/stop only this project's explicitly recorded Ollama process."""
import argparse
import json
import os
import signal
import subprocess
import sys
import time

from runtime_common import RUNTIME, BINARY, ENDPOINT, VERSION, LocalAPI, env, port_open
from evaluate_retrieval import write_atomic

PID_FILE = RUNTIME / 'ollama-process.json'


def identity(pid):
    if type(pid) is not int or pid <= 1:
        return None
    birth = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart='], capture_output=True, text=True)
    command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
    if birth.returncode or command.returncode:
        return None
    return {'birth': birth.stdout.strip(), 'command': command.stdout.strip()}


def listener_owned(pid):
    r = subprocess.run(['/usr/sbin/lsof', '-nP', '-a', '-p', str(pid), '-iTCP:11434', '-sTCP:LISTEN'],
                       capture_output=True, text=True)
    return r.returncode == 0 and '127.0.0.1:11434' in r.stdout


def record():
    return json.loads(PID_FILE.read_text()) if PID_FILE.exists() else None


def owns(row):
    if not row or row.get('binary') != str(BINARY) or row.get('endpoint') != ENDPOINT:
        return False
    return (row.get('identity') == identity(row.get('pid'))
            and row['identity'] is not None and row['identity']['command'] == str(BINARY) + ' serve')


def status():
    row = record()
    if row and owns(row):
        if not listener_owned(row['pid']):
            raise ValueError('recorded process does not own the expected loopback listener')
        version = LocalAPI(timeout=2).call('/api/version').get('version')
        if version != VERSION:
            raise ValueError('owned listener runtime version mismatch')
        return {'state': 'running', 'owned': True, 'pid': row['pid'], 'endpoint': ENDPOINT, 'version': version}
    if row and identity(row.get('pid')):
        raise ValueError('PID identity changed; refusing to operate on another process')
    return {'state': 'external' if port_open() else 'stopped', 'owned': False, 'endpoint': ENDPOINT}


def start(timeout=30):
    current = status()
    if current['state'] == 'running':
        return current
    if current['state'] == 'external':
        raise ValueError('loopback port already has an unowned service; no changes made')
    if not BINARY.is_file():
        raise ValueError('run setup_runtime.py to install the verified binary first')
    RUNTIME.mkdir(exist_ok=True)
    with (RUNTIME / 'ollama.log').open('ab') as log:
        child = subprocess.Popen([str(BINARY), 'serve'], env=env(), cwd=BINARY.parent,
                                 stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise ValueError('Ollama exited with code {}; inspect .runtime/ollama.log locally'.format(child.returncode))
            ident = identity(child.pid)
            if ident and ident['command'] == str(BINARY) + ' serve' and listener_owned(child.pid):
                try:
                    version = LocalAPI(timeout=2).call('/api/version').get('version')
                except OSError:
                    # A bound listener can precede GPU discovery / HTTP readiness.
                    time.sleep(.1)
                    continue
                if version != VERSION:
                    raise ValueError('unexpected runtime version')
                write_atomic(PID_FILE, {'pid': child.pid, 'identity': ident, 'binary': str(BINARY), 'endpoint': ENDPOINT})
                return status()
            time.sleep(.1)
        raise ValueError('Ollama readiness timeout; inspect .runtime/ollama.log locally')
    except BaseException:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
        raise


def stop(timeout=15):
    row = record()
    if row is None:
        return status()
    if identity(row.get('pid')) is None:
        PID_FILE.unlink()
        return status()
    if not owns(row) or not listener_owned(row['pid']):
        raise ValueError('process/listener ownership cannot be verified; refusing to stop')
    os.kill(row['pid'], signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if identity(row['pid']) is None:
            PID_FILE.unlink()
            return status()
        time.sleep(.1)
    raise ValueError('owned Ollama did not stop within deadline')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['start', 'status', 'stop'])
    args = p.parse_args(argv)
    try:
        print(json.dumps(globals()[args.command](), ensure_ascii=False))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print('error: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
