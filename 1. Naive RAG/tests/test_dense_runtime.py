"""Offline/local-loopback fault tests. Known vectors are NOT live model evidence."""
import contextlib
import copy
import io
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest import mock

STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE / 'scripts'))
import runtime_common as common
import runtime
try:
    import dense_retrieval as dense
    import run_dense_baseline as baseline
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.server.requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        self.reply()

    def do_GET(self):
        self.reply()

    def reply(self):
        status, body, delay = self.server.reply
        time.sleep(delay)
        self.send_response(status)
        if status == 302:
            self.send_header('Location', 'https://example.com/forbidden')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class HTTPBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.requests = []
        self.server.reply = (200, b'{}', 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.api = common.LocalAPI('http://127.0.0.1:' + str(self.server.server_port), timeout=.2)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def set_reply(self, body, status=200, delay=0):
        self.server.reply = (status, json.dumps(body).encode() if not isinstance(body, bytes) else body, delay)

    def test_embed_exact_request_and_count(self):
        self.set_reply({'model': common.MODEL, 'embeddings': [[1., 0.], [0., 1.]]})
        self.assertEqual(self.api.embed(['가상 규정', '질문'], 2), [[1., 0.], [0., 1.]])
        self.assertEqual(self.server.requests, [{'model': common.MODEL, 'input': ['가상 규정', '질문'], 'truncate': False}])

    def test_bad_count_dimension_values_zero_and_model(self):
        variants = [[], [[1, 0], [0, 1]], [[1]], [[0, 0]], [[True, 1]], [[float('nan'), 1]],
                    [[float('inf'), 1]], [['1', 0]], [None]]
        for vectors in variants:
            with self.subTest(vectors=vectors):
                self.set_reply({'model': common.MODEL, 'embeddings': vectors})
                with self.assertRaises(ValueError):
                    self.api.embed(['규정'], 2)
        self.set_reply({'model': 'wrong', 'embeddings': [[1, 0]]})
        with self.assertRaises(ValueError):
            self.api.embed(['규정'], 2)

    def test_http_error_json_error_redirect_timeout_and_no_fallback(self):
        for body, status in [(b'{bad', 200), ([], 200), ({'error': 'fail'}, 200), ({}, 500), ({}, 302), (b'{"x":1,"x":2}', 200)]:
            with self.subTest(body=body, status=status):
                self.set_reply(body, status)
                with self.assertRaises((OSError, ValueError)):
                    self.api.embed(['규정'], 2)
        self.set_reply({}, delay=.1)
        api = common.LocalAPI(self.api.endpoint, timeout=.01)
        started = time.monotonic()
        with self.assertRaises(OSError):
            api.embed(['규정'], 2)
        self.assertLess(time.monotonic() - started, .5)

    def test_tags_missing_duplicate_malformed_digest(self):
        for models in [[], [{ 'name': common.MODEL, 'digest': 'short'}],
                       [{'name': common.MODEL, 'digest': 'f' * 64}] * 2]:
            self.set_reply({'models': models})
            with self.assertRaises(ValueError):
                self.api.model()
        self.set_reply({'models': [{'name': common.MODEL, 'digest': 'f' * 64}]})
        self.assertEqual(self.api.model()['digest'], 'f' * 64)

    def test_loopback_only_endpoint_and_timeout_validation(self):
        for endpoint in ['https://127.0.0.1', 'http://localhost:11434', 'http://0.0.0.0:11434',
                         'http://example.com', 'http://u:p@127.0.0.1', 'http://127.0.0.1/path']:
            with self.assertRaises(ValueError):
                common.LocalAPI(endpoint)
        for timeout in [0, -1, True, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                common.LocalAPI(timeout=timeout)


class RuntimeSafetyTests(unittest.TestCase):
    def test_archive_traversal_link_device_rejected(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            for name, link, kind in [('../escape', '', 'file'), ('/escape', '', 'file'),
                                      ('link', '../../escape', 'link'), ('device', '', 'device')]:
                archive = root / 'input.tar'
                with tarfile.open(archive, 'w') as tar:
                    member = tarfile.TarInfo(name)
                    if kind == 'link':
                        member.type, member.linkname = tarfile.SYMTYPE, link
                    elif kind == 'device':
                        member.type = tarfile.CHRTYPE
                    tar.addfile(member)
                with self.assertRaises(ValueError):
                    common.safe_extract(archive, root / 'extract')
            self.assertFalse((root / 'escape').exists())

    def test_external_service_never_started_or_stopped(self):
        with mock.patch.object(runtime, 'status', return_value={'state': 'external'}), mock.patch.object(runtime.subprocess, 'Popen') as start:
            with self.assertRaises(ValueError):
                runtime.start()
            start.assert_not_called()
        row = {'pid': 42, 'binary': str(common.BINARY), 'endpoint': common.ENDPOINT,
               'identity': {'birth': 'old', 'command': str(common.BINARY) + ' serve'}}
        with mock.patch.object(runtime, 'record', return_value=row), mock.patch.object(runtime, 'identity', return_value={'birth': 'new', 'command': 'unrelated'}), mock.patch.object(runtime.os, 'kill') as kill:
            with self.assertRaises(ValueError):
                runtime.stop()
            kill.assert_not_called()

    def test_start_retries_transient_readiness_timeout(self):
        ident = {'birth': 'test', 'command': str(common.BINARY) + ' serve'}
        child = mock.Mock(pid=4242)
        child.poll.return_value = None
        api = mock.Mock()
        api.call.side_effect = [TimeoutError('not ready yet'), {'version': common.VERSION}]
        with tempfile.TemporaryDirectory() as scratch, mock.patch.object(runtime, 'RUNTIME', Path(scratch)), mock.patch.object(runtime, 'BINARY', common.BINARY), mock.patch.object(Path, 'is_file', return_value=True), mock.patch.object(runtime, 'status', side_effect=[{'state': 'stopped'}, {'state': 'running'}]), mock.patch.object(runtime.subprocess, 'Popen', return_value=child), mock.patch.object(runtime, 'identity', return_value=ident), mock.patch.object(runtime, 'listener_owned', return_value=True), mock.patch.object(runtime, 'LocalAPI', return_value=api), mock.patch.object(runtime, 'write_atomic') as saved, mock.patch.object(runtime.time, 'sleep'):
            self.assertEqual(runtime.start()['state'], 'running')
            self.assertEqual(api.call.call_count, 2)
            saved.assert_called_once()
            child.terminate.assert_not_called()

    def test_model_digest_and_runtime_mismatch_rejected(self):
        api = common.LocalAPI()
        lock = {'ollama': {'version': common.VERSION}, 'model': {'digest': 'a' * 64}}
        with mock.patch.object(api, 'call', return_value={'version': 'wrong'}):
            with self.assertRaises(ValueError):
                api.check(lock)
        with mock.patch.object(api, 'call', return_value={'version': common.VERSION}), mock.patch.object(api, 'model', return_value={'digest': 'b' * 64}):
            with self.assertRaises(ValueError):
                api.check(lock)


@unittest.skipUnless(HAS_QDRANT, 'run with the isolated .venv Python for Qdrant tests')
class PersistentCosineTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.path = self.root / 'index'
        self.chunks = {cid: dict(chunk_id=cid, document_id='fixture', version='1', title='가상 ' + cid,
                                  text='알려진 벡터 검증', source='synthetic://fixture/' + cid, synthetic=True)
                       for cid in ['a', 'b', 'c']}
        self.vectors = [[1., 0.], [0., 1.], [1., 1.]]
        self.lock = {'qdrant_client_version': '1.19.1', 'ollama': {'version': common.VERSION},
                     'model': {'name': common.MODEL, 'digest': 'fixture-only-not-live', 'dimension': 2}}

    def create(self):
        return dense.create_index(self.chunks, 'fixture-hash', self.vectors, self.lock, self.path)

    def test_independent_cosine_reopen_and_uuid_payload(self):
        self.create()
        with dense.DenseIndex(self.path, self.chunks, 'fixture-hash', self.lock) as index:
            rows = index.search([1., 0.], 20)
            self.assertEqual([r['chunk_id'] for r in rows], ['a', 'c', 'b'])
            for actual, expected in zip(rows, [1., 1 / math.sqrt(2), 0.]):
                self.assertLessEqual(abs(actual['score'] - expected), 1e-6)
        code = 'import sys,json;sys.path.insert(0,sys.argv[1]);import dense_retrieval as d;from pathlib import Path;v=json.loads(Path(sys.argv[3]).read_text());\nwith d.DenseIndex(Path(sys.argv[2]),v["chunks"],"fixture-hash",v["lock"]) as i: print(json.dumps(i.search([1.,0.],20)))'
        fixture = self.root / 'fixture.json'
        fixture.write_text(json.dumps({'chunks': self.chunks, 'lock': self.lock}))
        r = subprocess.run([sys.executable, '-c', code, str(STAGE / 'scripts'), str(self.path), str(fixture)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([r['chunk_id'] for r in json.loads(r.stdout)], ['a', 'c', 'b'])

    def test_zero_negative_cosine_and_exact_tie_are_retained(self):
        self.chunks['d'] = dict(self.chunks['a'], chunk_id='d', source='synthetic://fixture/d')
        self.chunks['e'] = dict(self.chunks['a'], chunk_id='e', source='synthetic://fixture/e')
        self.vectors += [[-1., 0.], [1., 0.]]
        self.create()
        with dense.DenseIndex(self.path, self.chunks, 'fixture-hash', self.lock) as index:
            rows = index.search([1., 0.], 20)
            self.assertEqual([r['chunk_id'] for r in rows], ['a', 'e', 'c', 'b', 'd'])
            self.assertEqual(rows[-1]['score'], -1.)
            self.assertEqual(rows[-2]['score'], 0.)
            hits = index.client.query_points(dense.COLLECTION, query=[1., 0.], limit=5, with_payload=True).points
            with mock.patch.object(index.client, 'query_points', return_value=SimpleNamespace(points=list(reversed(hits)))):
                reordered = index.search([1., 0.], 20)
                self.assertEqual([r['chunk_id'] for r in reordered], ['a', 'e', 'c', 'b', 'd'])
                for actual, expected in zip(reordered, [1., 1., 1 / math.sqrt(2), 0., -1.]):
                    self.assertLessEqual(abs(actual['score'] - expected), 1e-6)
            with mock.patch.object(index.client, 'query_points', return_value=SimpleNamespace(points=[hits[0]] * 5)):
                with self.assertRaises(ValueError):
                    index.search([1., 0.], 20)

    def test_stale_manifest_changes_rejected_before_open(self):
        self.create()
        path = self.path / 'index-manifest.json'
        original = json.loads(path.read_text())
        for key in ['corpus_sha256', 'model_digest', 'dimension', 'text_version', 'distance', 'point_count', 'qdrant_client_version']:
            altered = dict(original, **{key: 'changed'})
            path.write_text(json.dumps(altered))
            with self.subTest(key=key), mock.patch.object(dense, 'QdrantClient') as client:
                with self.assertRaisesRegex(ValueError, 'stale'):
                    dense.DenseIndex(self.path, self.chunks, 'fixture-hash', self.lock)
                client.assert_not_called()
        path.write_text(json.dumps(original))
        with self.assertRaisesRegex(ValueError, 'stale'):
            dense.DenseIndex(self.path, self.chunks, 'new-corpus-hash', self.lock)

    def test_unknown_payload_and_duplicate_chunk_mapping_rejected(self):
        from qdrant_client import QdrantClient
        self.create()
        for payload in [dict(self.chunks['b'], chunk_id='unknown'), self.chunks['a'], dict(self.chunks['b'], relevance={'a': 3})]:
            client = QdrantClient(path=str(self.path / 'store'))
            client.overwrite_payload(dense.COLLECTION, payload=payload, points=[dense.point_id('b')])
            client.close()
            with self.assertRaises(ValueError):
                dense.DenseIndex(self.path, self.chunks, 'fixture-hash', self.lock)

    def test_invalid_vectors_no_new_index(self):
        for vector in [[0., 0.], [1.], [True, 1.], [float('nan'), 1.], [float('inf'), 1.]]:
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                dense.create_index(self.chunks, 'fixture-hash', [vector] + self.vectors[1:], self.lock, self.path)
            self.assertFalse(self.path.exists())
        self.assertFalse(list(self.root.glob('.dense-index-*')))

    def test_existing_index_and_index_failures_preserve_user_data(self):
        self.path.mkdir()
        (self.path / 'user.txt').write_bytes(b'keep')
        with self.assertRaises(ValueError):
            self.create()
        self.assertEqual((self.path / 'user.txt').read_bytes(), b'keep')
        (self.path / 'user.txt').unlink(); self.path.rmdir()
        for patcher in [mock.patch.object(dense, 'write_json', side_effect=OSError('injected write')),
                        mock.patch.object(dense, 'publish_index', side_effect=OSError('injected publish')),
                        mock.patch.object(dense.shutil, 'copytree', side_effect=OSError('injected tree copy'))]:
            with patcher, self.assertRaises(OSError):
                self.create()
            self.assertFalse(self.path.exists())
            self.assertFalse(list(self.root.glob('.dense-index-*')))
        with self.assertRaises(ValueError):
            dense.create_index(self.chunks, 'fixture-hash', self.vectors, self.lock, self.path,
                               before_publish=lambda: (_ for _ in ()).throw(ValueError('digest changed')))
        self.assertFalse(self.path.exists())

    def test_output_failures_and_labels_do_not_enter_embeddings(self):
        # Test-only provider with known vectors; never substituted by the live CLI.
        rows = list(self.chunks.values())
        chunk_file, query_file = self.root / 'chunks.jsonl', self.root / 'queries.jsonl'
        chunk_file.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        query_file.write_text(json.dumps(dict(query_id='q', question='질문 원문', answerability='answerable', relevance={'a': 3})) + '\n')
        from evaluate_retrieval import read_jsonl
        _, h = read_jsonl(chunk_file)
        dense.create_index(self.chunks, h, self.vectors, self.lock, self.path)
        output = self.root / 'output'
        api = mock.Mock()
        api.embed.return_value = [[1., 0.]]
        options = ['--chunks', str(chunk_file), '--queries', str(query_file), '--index-dir', str(self.path), '--output-dir', str(output)]
        with mock.patch.object(baseline, 'load_lock', return_value=self.lock), mock.patch.object(baseline, 'LocalAPI', return_value=api):
            self.assertEqual(baseline.main(options), 0)
            original = (output / 'rankings.jsonl').read_bytes()
            api.embed.assert_called_with(['질문 원문'], 2)
            query_file.write_text(json.dumps(dict(query_id='q', question='질문 원문', answerability='unanswerable', relevance={})) + '\n')
            new = self.root / 'changed'
            self.assertEqual(baseline.main(options[:-1] + [str(new)]), 0)
            self.assertEqual(original, (new / 'rankings.jsonl').read_bytes())
            for patcher in [mock.patch.object(api, 'embed', side_effect=TimeoutError('injected timeout')),
                            mock.patch.object(baseline.evaluation, 'evaluate', side_effect=ValueError('injected evaluation')),
                            mock.patch.object(baseline, 'write_json', side_effect=OSError('injected write')),
                            mock.patch.object(baseline, 'publish_directory', side_effect=OSError('injected publish'))]:
                stderr = io.StringIO(); failed = self.root / 'failed'
                with patcher, contextlib.redirect_stderr(stderr):
                    self.assertEqual(baseline.main(options[:-1] + [str(failed)]), 2)
                self.assertIn('injected', stderr.getvalue())
                self.assertFalse(failed.exists())
                self.assertFalse(list(self.root.glob('.dense-run-*')))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertNotEqual(baseline.main(options), 0)  # existing successful result preserved
            self.assertEqual(original, (output / 'rankings.jsonl').read_bytes())


if __name__ == '__main__':
    unittest.main()
