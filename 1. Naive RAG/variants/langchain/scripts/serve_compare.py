#!/usr/bin/env python3
"""Loopback-only learning UI; one shared P004 pipeline, serialized index access."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading

from generation import load_generation_lock, strict_json, CITATION_MODE, RESPONSE_CONTRACT
from rag import INDEX, validate_input, PROMPTS
from comparison import ask, DEFAULT_IMPLEMENTATION
import time
import uuid
from runtime_common import STAGE, sha256
import runtime

WEB = STAGE / 'web_compare'


def error_result(message, kind='input'):
    return {'status': 'error', 'answer': message, 'citations': [], 'reason': kind,
            'trace': {'error': {'kind': kind, 'message': message}}}


class LearningServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port=8001, ask_fn=ask):
        super().__init__(('127.0.0.1', port), Handler)
        self.ask_fn = ask_fn
        self.pipeline_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def send(self, code, payload, content_type='application/json; charset=utf-8'):
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode() if isinstance(payload, dict) else payload
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Closing a browser does not cancel another user's process.

    def local_request(self):
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        origin = self.headers.get('Origin')
        if self.headers.get('Host') not in hosts or origin and origin not in {'http://' + host for host in hosts}:
            self.send(403, error_result('같은 로컬 화면에서 요청하세요.'))
            return False
        return True

    def do_GET(self):
        if not self.local_request():
            return
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/experiments/implementation': ('implementation.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if self.path in assets:
            filename, mime = assets[self.path]
            self.send(200, (WEB / filename).read_bytes(), mime)
        elif self.path == '/guide':
            self.send(200, (STAGE / 'LEARNING_GUIDE.md').read_bytes(), 'text/plain; charset=utf-8')
        elif self.path == '/api/decision':
            path = STAGE / 'adoption-decision.json'
            self.send(200, json.loads(path.read_text()) if path.is_file() else {'decision': 'PENDING', 'selected_implementation': 'direct'})
        elif self.path == '/api/status':
            try:
                lock = load_generation_lock()
                self.send(200, {'runtime': runtime.status(), 'model': lock['model']['name'],
                    'digest': lock['model']['digest'], 'options': lock['request']['options'],
                    'prompt_version': 'system-v3', 'prompt_sha256': sha256(PROMPTS / 'system-v3.txt'),
                    'citation_mode': CITATION_MODE, 'response_contract': RESPONSE_CONTRACT,
                    'index_files_present': (INDEX / 'index-manifest.json').is_file(),
                    'note': 'lock/파일 상태이며 실제 질의 시 모델·색인 정합성을 다시 검사합니다.'})
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                self.send(500, error_result(str(exc), 'execution'))
        else:
            self.send(404, error_result('경로를 찾을 수 없습니다.'))

    def do_POST(self):
        if not self.local_request():
            return
        if self.path not in ('/api/ask', '/api/compare'):
            self.send(404, error_result('경로를 찾을 수 없습니다.'))
            return
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Content-Type은 application/json이어야 합니다.')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 65536:
                raise ValueError('요청은 1~65536바이트 JSON이어야 합니다.')
            self.connection.settimeout(10)
            data = strict_json(self.rfile.read(size).decode('utf-8'))
            if not isinstance(data, dict) or set(data) - {'question', 'retriever', 'top_k', 'max_context_chars', 'implementation'}:
                raise ValueError('질문과 지원하는 설정만 전달하세요.')
            args = {'question': data.get('question'), 'retriever': data.get('retriever', 'dense'),
                    'top_k': data.get('top_k', 5), 'max_context_chars': data.get('max_context_chars', 8000)}
            implementation = data.get('implementation', DEFAULT_IMPLEMENTATION)
            if implementation not in ('direct', 'langchain'):
                raise ValueError('implementation must be direct or langchain')
            validate_input(**args, timeout_seconds=120)
            if len(args['question']) > 4000 or args['top_k'] > 100 or args['max_context_chars'] > 24000:
                raise ValueError('질문4000자, top-k100, 문맥24000자 이내로 입력하세요.')
        except (ValueError, UnicodeError, OSError) as exc:
            self.send(400, error_result(str(exc)))
            return
        try:
            with self.server.pipeline_lock:
                if self.path == '/api/compare':
                    results = []
                    pair_id = str(uuid.uuid4())
                    for order, impl in enumerate(('direct', 'langchain'), 1):
                        started = time.perf_counter()
                        try:
                            row = self.server.ask_fn(**args, implementation=impl)
                        except Exception:
                            row = error_result('서버 실행 오류입니다.', 'execution')
                        results.append({'implementation': impl, 'order': order,
                            'wall_ms': (time.perf_counter()-started)*1000, 'result': row})
                    self.send(200, {'pair_id': pair_id, 'mode': 'manual_single_pair_not_benchmark',
                        'settings': args, 'results': results})
                    return
                result = self.server.ask_fn(**args, implementation=implementation)
            code = 200 if result['status'] != 'error' else {
                'input': 400, 'provider': 502, 'timeout': 504}.get(result.get('reason'), 500)
            self.send(code, result)
        except Exception:
            # Do not expose internals or label programming errors as missing evidence.
            self.send(500, error_result('서버 실행 오류입니다. 서버 로그를 확인하세요.', 'execution'))
            import traceback
            traceback.print_exc(file=sys.stderr)

    def log_message(self, fmt, *args):
        # Base HTTP log has method/path/status, never question bodies or prompts.
        super().log_message(fmt, *args)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=8001)
    args = p.parse_args()
    if not 1 <= args.port <= 65535:
        p.error('port must be 1..65535')
    try:
        with LearningServer(args.port) as server:
            print(f'Naive RAG: http://127.0.0.1:{args.port} — Ctrl+C로 UI 종료; Ollama는 runtime.py stop', flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        print('\nUI stopped. 다른 프로세스는 종료하지 않았습니다.', flush=True)
    except OSError as exc:
        print('error: '+str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
