"""Offline contract tests. Network guard admits only the owned fake HTTP server."""
import contextlib
import copy
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from rag_package.llm import validate_config, validate_messages, preview, invoke, ValidationError
from rag_package.llm.config import strict_json, read_json, INPUT_LIMIT
from rag_package.llm.transport import http_transport, TransportError, RESPONSE_LIMIT
from rag_package.llm.__main__ import main, atomic_result

ROOT=Path(__file__).resolve().parents[2]
KEY='synthetic-P025-secret-never-a-user-key'
DIGEST='a'*64
MESSAGES=[{'role':'system','content':'정확히 답하세요.'},{'role':'user','content':'휴가 조건?'}]


def config(provider='ollama', response_mode='text'):
    local=provider=='ollama'
    p={'mode':'local' if local else 'api','provider':provider,'model':'fixture-model',
       'base_url':'http://127.0.0.1:1' if local else 'https://example.invalid/v1',
       'max_output_tokens':64,'timeout_seconds':1,'response_mode':response_mode,
       'identity':{'expected_digest':DIGEST,'hf_id':'fixture/model','conversion':'synthetic'} if local else
       {'requested_model':'fixture-model','revision_pinned':False,'revision':None}}
    if not local:p['api_key_env']='P025_FAKE_KEY'
    return {'schema_version':1,'profiles':{'one':p},'roles':{'generation':'one','evaluation':'one'}}


def envelope(provider='ollama', content='정상 답변', finish=None):
    if provider=='ollama':return {'model':'fixture-model','message':{'role':'assistant','content':content},'done':True,'done_reason':finish or 'stop','prompt_eval_count':7,'eval_count':3,'total_duration':2500000}
    if provider=='openai_chat':return {'model':'fixture-model-revision','choices':[{'message':{'role':'assistant','content':content},'finish_reason':finish or 'stop'}],'usage':{'prompt_tokens':7,'completion_tokens':3}}
    return {'type':'message','role':'assistant','model':'fixture-model-revision','content':[{'type':'text','text':content}],'stop_reason':finish or 'end_turn','usage':{'input_tokens':7,'output_tokens':3}}


class Fake:
    def __init__(self, provider='ollama', response=None, digests=None, failure=None):
        self.provider=provider;self.response=response if response is not None else envelope(provider)
        self.digests=list(digests or [DIGEST,DIGEST]);self.failure=failure;self.calls=[]
    def __call__(self,method,url,headers,body,timeout):
        self.calls.append((method,url,headers,body,timeout))
        if method=='GET':return {'models':[{'name':'fixture-model','digest':self.digests.pop(0)}]}
        if self.failure:raise self.failure
        return self.response


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard=patch('socket.socket.connect',side_effect=AssertionError('external network forbidden'))
        cls.guard.start()
        cls.dns=patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden'))
        cls.dns.start()
    @classmethod
    def tearDownClass(cls):cls.dns.stop();cls.guard.stop()

    def test_routing_and_roles(self):
        for provider in ('ollama','openai_chat','anthropic_messages'):
            with self.subTest(provider=provider):
                c=config(provider);p=c['profiles']['one']; p['temperature']=None
                c['profiles']['two']=copy.deepcopy(p);c['profiles']['two']['max_output_tokens']=123
                c['roles']['evaluation']='two'
                f=Fake(provider);r=invoke(c,'evaluation',MESSAGES,transport=f,key_resolver=lambda _:KEY)
                self.assertEqual(r['status'],'complete');self.assertEqual(r['role'],'evaluation')
                call=[x for x in f.calls if x[0]=='POST'][0];body=call[3]
                self.assertFalse(body['stream']);self.assertNotIn('temperature',body)
                if provider=='ollama':
                    self.assertTrue(call[1].endswith('/api/chat'));self.assertEqual(body['options']['num_predict'],123)
                    self.assertIs(body['think'],False);self.assertEqual(body['keep_alive'],0)
                    self.assertNotIn('Authorization',call[2]);self.assertEqual(body['messages'],MESSAGES)
                    self.assertEqual(r['usage']['provider_duration_ms'],2.5)
                else:
                    self.assertEqual(call[2]['Authorization'],'Bearer '+KEY)
                    self.assertNotIn('options',body);self.assertNotIn('think',body);self.assertNotIn('seed',body)
                    if provider=='openai_chat':
                        self.assertEqual(body['max_completion_tokens'],123);self.assertEqual(body['messages'],MESSAGES);self.assertNotIn('n',body)
                        self.assertTrue(call[1].endswith('/chat/completions'))
                    else:
                        self.assertEqual(body['max_tokens'],123);self.assertEqual(body['system'],MESSAGES[0]['content'])
                        self.assertEqual(body['messages'],MESSAGES[1:]);self.assertEqual(call[2]['anthropic-version'],'2026-10-21')
                        self.assertNotIn('x-api-key',call[2]);self.assertTrue(call[1].endswith('/messages'))
                self.assertEqual(r['usage']['input_tokens'],7);self.assertEqual(r['usage']['output_tokens'],3)
                self.assertIsNone(r['cost'])

    def test_preview_no_keys_no_network_and_json_hash(self):
        for provider in ('ollama','openai_chat','anthropic_messages'):
            c=config(provider,'json_object');original=copy.deepcopy(MESSAGES)
            with patch('os.environ.get',side_effect=AssertionError('no env')):
                validate_config(c);v=preview(c,'generation',MESSAGES)
            self.assertEqual(MESSAGES,original);self.assertNotEqual(v['original_messages_hash'],v['actual_messages_hash'])
            self.assertNotIn('Authorization',json.dumps(v))
            r=invoke(c,'generation',MESSAGES,transport=Fake(provider,envelope(provider,'{"a":1}')),key_resolver=lambda _:KEY)
            self.assertEqual(r['parsed_json'],{'a':1});self.assertEqual(r['status'],'complete')
            if provider=='ollama':self.assertEqual(v['body']['format'],'json')
            elif provider=='openai_chat':self.assertEqual(v['body']['response_format'],{'type':'json_object'})
            else:self.assertNotIn('response_format',v['body'])

    def test_config_rejection(self):
        mutations=[('max_output_tokens',True),('max_output_tokens',0),('max_output_tokens',32769),('max_output_tokens',10**400),('timeout_seconds',float('nan')),('timeout_seconds',601),('num_ctx',511),('seed',True),('model',' '),('response_mode','schema'),('unexpected',KEY),('api_key_env','KEY')]
        for field,value in mutations:
            c=config();c['profiles']['one'][field]=value
            with self.subTest(field=field,value_type=type(value).__name__),self.assertRaises(ValidationError):validate_config(c)
        for provider in ('openai_chat','anthropic_messages'):
            for field,value in [('num_ctx',8192),('seed',42),('api_key_env','BAD\nKEY')]:
                c=config(provider);c['profiles']['one'][field]=value
                with self.assertRaises(ValidationError):validate_config(c)
        for mutate in (lambda c:c.update(example_only=True),lambda c:c.update(schema_version=True),lambda c:c['roles'].update(generation='missing'),lambda c:c['profiles']['one']['identity'].update(expected_digest='a'*63)):
            c=config();mutate(c)
            with self.assertRaises(ValidationError):validate_config(c)
        for file in ('local.json','api.json'):
            with self.assertRaises(ValidationError):validate_config(read_json(ROOT/'docs/learning/rag-package/examples'/file))

    def test_urls(self):
        for mode,urls in [('ollama',['http://localhost:1','http://192.168.0.1','https://127.0.0.1','http://127.0.0.1/a/../b','http://127.0.0.1/%252e%252e','http://u:'+KEY+'@127.0.0.1','http://127.0.0.1?x='+KEY,'http://127.0.0.1#x','http://127.0.0.1/\n','http://127.0.0.1:0','http://127.0.0.1/%0a']),('openai_chat',['http://example.invalid','https://a:b@example.invalid','https://example.invalid/../x','https://example.invalid?key='+KEY])]:
            for u in urls:
                c=config(mode);c['profiles']['one']['base_url']=u
                with self.subTest(url=u),self.assertRaises(ValidationError) as caught:validate_config(c)
                self.assertNotIn(KEY,str(caught.exception))
        c=config();c['profiles']['one']['base_url']='http://[::1]:1234';validate_config(c)

    def test_messages(self):
        for m in ([],[{'role':'system','content':'only'}],[{'role':'assistant','content':'x'}],[{'role':'user','content':[]}],[{'role':'tool','content':'x'}],[{'role':'user','content':'x','tool':1}],MESSAGES+[{'role':'user','content':'x'}],MESSAGES+[{'role':'assistant','content':'x'}]):
            with self.assertRaises(ValidationError):validate_messages(m)
        validate_messages(MESSAGES+[{'role':'assistant','content':'a'},{'role':'user','content':'b'}])

    def test_identity_gates(self):
        for digests,npost in ((['b'*64],0),([DIGEST,'b'*64],1)):
            f=Fake(digests=digests);r=invoke(config(),'generation',MESSAGES,transport=f)
            self.assertEqual(r['status'],'error');self.assertEqual(r['error']['code'],'model_identity_mismatch')
            self.assertEqual(sum(c[0]=='POST' for c in f.calls),npost);self.assertIsNone(r['content'])
        f=Fake();f.digests=['b'*64];r=invoke(config(),'generation',MESSAGES,transport=f)
        self.assertFalse(r['dispatch_attempted'])

    def test_missing_model_and_empty_envelopes(self):
        calls=[]
        def empty_inventory(method,*args):
            calls.append(method)
            return {'models':[]}
        r=invoke(config(),'generation',MESSAGES,transport=empty_inventory)
        self.assertEqual(calls,['GET']);self.assertFalse(r['dispatch_attempted'])
        self.assertEqual(r['error']['code'],'model_identity_mismatch')
        for raw in (None, [], {}, True):
            r=invoke(config('openai_chat'),'generation',MESSAGES,transport=lambda *args:raw,key_resolver=lambda _:KEY)
            self.assertEqual(r['status'],'invalid_response')

    def test_usage_missing_and_hidden_thinking(self):
        for provider in ('ollama','openai_chat','anthropic_messages'):
            raw=envelope(provider)
            for k in ('usage','prompt_eval_count','eval_count','total_duration'):raw.pop(k,None)
            if provider=='ollama':raw['message']['thinking']=KEY
            if provider=='anthropic_messages':raw['content'].insert(0,{'type':'thinking','thinking':KEY})
            r=invoke(config(provider),'generation',MESSAGES,transport=Fake(provider,raw),key_resolver=lambda _:KEY)
            self.assertEqual(r['status'],'unsupported_response' if provider=='ollama' else 'complete');self.assertIsNone(r['usage']['input_tokens']);self.assertNotIn(KEY,json.dumps(r))

    def test_inline_thinking_rejected_not_repaired(self):
        for provider in ('ollama','openai_chat','anthropic_messages'):
            for mode in ('text','json_object'):
                for content in ('<think>'+KEY+'</think>답변', '<think>'+KEY, '{"answer":"<think>'+KEY+'</think>"}'):
                    r=invoke(config(provider,mode),'generation',MESSAGES,transport=Fake(provider,envelope(provider,content)),key_resolver=lambda _:KEY)
                    self.assertEqual(r['status'],'unsupported_response')
                    self.assertIsNone(r['content']);self.assertIsNone(r['parsed_json']);self.assertNotIn(KEY,json.dumps(r))

    def test_non_success_finishes(self):
        for provider in ('ollama','openai_chat','anthropic_messages'):
            for finish,status in [('length','truncated'),('max_tokens','truncated'),('refusal','refused'),('content_filter','refused'),('tool_use','unsupported_response'),('tool_calls','unsupported_response'),(KEY,'unsupported_response')]:
                r=invoke(config(provider,'json_object'),'generation',MESSAGES,transport=Fake(provider,envelope(provider,KEY,finish)),key_resolver=lambda _:KEY)
                self.assertEqual(r['status'],status);self.assertIsNone(r['parsed_json']);self.assertIsNone(r['content']);self.assertNotIn(KEY,json.dumps(r))

    def test_envelope_and_json_errors(self):
        for provider in ('ollama','openai_chat','anthropic_messages'):
            for content in (None, [], {}, False, '', '   ', '[]', '{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}', '```json\n{}\n```',KEY):
                r=invoke(config(provider,'json_object'),'generation',MESSAGES,transport=Fake(provider,envelope(provider,content)),key_resolver=lambda _:KEY)
                self.assertEqual(r['status'],'invalid_response');self.assertIsNone(r['content']);self.assertNotIn(KEY,json.dumps(r))
            for field in ('model',):
                raw=envelope(provider);raw.pop(field)
                r=invoke(config(provider),'generation',MESSAGES,transport=Fake(provider,raw),key_resolver=lambda _:KEY)
                self.assertEqual(r['status'],'invalid_response')
        raw=envelope();raw['done']=False
        self.assertEqual(invoke(config(),'generation',MESSAGES,transport=Fake(response=raw))['status'],'invalid_response')
        raw=envelope('openai_chat');raw['choices']*=2
        self.assertEqual(invoke(config('openai_chat'),'generation',MESSAGES,transport=Fake('openai_chat',raw),key_resolver=lambda _:KEY)['status'],'invalid_response')
        raw=envelope('anthropic_messages');raw['content'].append({'type':'unknown','value':KEY})
        r=invoke(config('anthropic_messages'),'generation',MESSAGES,transport=Fake('anthropic_messages',raw),key_resolver=lambda _:KEY)
        self.assertEqual(r['status'],'unsupported_response');self.assertNotIn(KEY,json.dumps(r))

    def test_missing_key_and_errors_no_retry_or_leak(self):
        for key in (None,'',KEY+'\n'):
            f=Fake('openai_chat');r=invoke(config('openai_chat'),'generation',MESSAGES,transport=f,key_resolver=lambda _:key)
            self.assertEqual(len(f.calls),0);self.assertFalse(r['dispatch_attempted']);self.assertNotIn(KEY,json.dumps(r))
        for error in [TransportError(x,x=='timeout') for x in ('http_401','http_403','http_429','http_5xx','timeout','response_too_large','redirect_denied','connection_error')]+[RuntimeError(KEY),TransportError(KEY)]:
            f=Fake('openai_chat',failure=error)
            r=invoke(config('openai_chat'),'generation',MESSAGES,transport=f,key_resolver=lambda _:KEY)
            self.assertEqual(len(f.calls),1);self.assertEqual(r['status'],'error');self.assertNotIn(KEY,json.dumps(r))
            if getattr(error,'code',None)=='timeout':self.assertTrue(r['outcome_unknown'])

    def test_import_help_and_cli_failure_artifact(self):
        script="""import socket, os, sys
socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network'))
import rag_package.llm
from rag_package.llm.__main__ import main
main(['--help'])
"""
        p=subprocess.run([sys.executable,'-c',script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(p.returncode,0);self.assertIn('validate',p.stdout)
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);(d/'c').write_text(json.dumps(config('openai_chat')));(d/'m').write_text(json.dumps(MESSAGES))
            with patch.dict('os.environ',{'P025_FAKE_KEY':''}),contextlib.redirect_stdout(io.StringIO()) as out:
                code=main(['invoke','--config',str(d/'c'),'--role','generation','--messages',str(d/'m'),'--output',str(d/'result')])
            self.assertEqual(code,1);r=json.loads((d/'result').read_text())
            self.assertFalse(r['dispatch_attempted']);self.assertEqual(r['error']['code'],'missing_api_key')
            self.assertNotIn(KEY,out.getvalue())

    def test_escaped_thinking_in_json(self):
        raw='{"nested":["\\u003cthink>'+KEY+'"]}'
        for provider in ('ollama','openai_chat','anthropic_messages'):
            r=invoke(config(provider,'json_object'),'generation',MESSAGES,transport=Fake(provider,envelope(provider,raw)),key_resolver=lambda _:KEY)
            self.assertEqual(r['status'],'unsupported_response');self.assertIsNone(r['parsed_json']);self.assertNotIn(KEY,json.dumps(r))

    def test_additional_envelope_boundaries(self):
        for provider in ('ollama','openai_chat','anthropic_messages'):
            raw=envelope(provider)
            if provider=='ollama':raw['message']['role']='user'
            elif provider=='openai_chat':raw['choices'][0]['message']['role']='user'
            else:raw['role']='user'
            r=invoke(config(provider),'generation',MESSAGES,transport=Fake(provider,raw),key_resolver=lambda _:KEY)
            self.assertEqual(r['status'],'invalid_response')
        raw=envelope();raw['model']='different'
        self.assertEqual(invoke(config(),'generation',MESSAGES,transport=Fake(response=raw))['status'],'invalid_response')
        raw=envelope('openai_chat');raw['choices'][0]['message']['refusal']=KEY
        r=invoke(config('openai_chat'),'generation',MESSAGES,transport=Fake('openai_chat',raw),key_resolver=lambda _:KEY)
        self.assertEqual(r['status'],'refused');self.assertNotIn(KEY,json.dumps(r))
        raw=envelope('openai_chat');raw['choices'][0]['message']['tool_calls']=[{'secret':KEY}]
        r=invoke(config('openai_chat'),'generation',MESSAGES,transport=Fake('openai_chat',raw),key_resolver=lambda _:KEY)
        self.assertEqual(r['status'],'unsupported_response');self.assertNotIn(KEY,json.dumps(r))

    def test_cli_and_files(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);(d/'c.json').write_text(json.dumps(config('openai_chat')));(d/'m.json').write_text(json.dumps(MESSAGES))
            for cmd in ('validate','preview'):
                args=[cmd,'--config',str(d/'c.json')]
                if cmd=='preview':args+=['--role','generation','--messages',str(d/'m.json')]
                with patch('os.environ.get',side_effect=lambda name, default=None: (_ for _ in ()).throw(AssertionError('key access')) if name=='P025_FAKE_KEY' else default),contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(main(args),0)
                self.assertNotIn(KEY,out.getvalue())
            (d/'existing').write_text('preserve')
            with patch('rag_package.llm.__main__.invoke',side_effect=AssertionError('must not call')),contextlib.redirect_stdout(io.StringIO()):
                self.assertNotEqual(main(['invoke','--config',str(d/'c.json'),'--role','generation','--messages',str(d/'m.json'),'--output',str(d/'existing')]),0)
            self.assertEqual((d/'existing').read_text(),'preserve')
            atomic_result(d/'new',{'status':'complete'})
            with self.assertRaises(ValidationError):atomic_result(d/'new',{'bad':1})
            (d/'large').write_bytes(b' '* (INPUT_LIMIT+1))
            with self.assertRaises(ValidationError):read_json(d/'large')
            with contextlib.redirect_stdout(io.StringIO()) as out:self.assertEqual(main(['--secret-'+KEY]),2)
            self.assertNotIn(KEY,out.getvalue())

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.hits=[]
        hits=self.hits
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):self.respond()
            def do_POST(self):
                self.body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
                self.respond()
            def respond(self):
                hits.append((self.command,self.path,getattr(self,'body',None)))
                code=200;body=b'{}';extra={}
                if self.path.startswith('/status/'):
                    code=int(self.path.rsplit('/',1)[1]);body=KEY.encode()
                elif self.path=='/redirect':code=302;extra={'Location':'https://example.invalid/'+KEY}
                elif self.path=='/oversize':body=b' '* (RESPONSE_LIMIT+1)+KEY.encode()
                elif self.path=='/duplicate':body=b'{"x":1,"x":2}'
                elif self.path=='/invalid':body=KEY.encode()
                elif self.path=='/timeout':
                    import time
                    time.sleep(1.2)
                elif self.path=='/api/tags':body=json.dumps({'models':[{'name':'fixture-model','digest':DIGEST}]}).encode()
                elif self.path=='/api/chat':body=json.dumps(envelope()).encode()
                self.send_response(code)
                for k,v in extra.items():self.send_header(k,v)
                self.send_header('Content-Length',str(len(body)));self.end_headers()
                try:self.wfile.write(body)
                except (BrokenPipeError,ConnectionResetError):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        connect=socket.socket.connect
        port=self.server.server_port
        def guarded(sock,address):
            if address[0]!='127.0.0.1' or address[1]!=port:raise AssertionError('non-fixture network forbidden')
            return connect(sock,address)
        self.guard=patch('socket.socket.connect',new=guarded);self.guard.start()
        getaddrinfo=socket.getaddrinfo
        def guarded_dns(host, target_port, *args, **kwargs):
            if host!='127.0.0.1' or int(target_port)!=port:raise AssertionError('non-fixture DNS forbidden')
            return getaddrinfo(host,target_port,*args,**kwargs)
        self.dns=patch('socket.getaddrinfo',new=guarded_dns);self.dns.start()
    def tearDown(self):
        self.dns.stop();self.guard.stop();self.server.shutdown();self.server.server_close();self.thread.join()

    def test_real_transport_errors(self):
        for path,code in [('/status/401','http_401'),('/status/403','http_403'),('/status/429','http_429'),('/status/503','http_5xx'),('/redirect','redirect_denied'),('/oversize','response_too_large'),('/duplicate','invalid_response_json'),('/invalid','invalid_response_json'),('/timeout','timeout')]:
            n=len(self.hits)
            with self.subTest(path=path),self.assertRaises(TransportError) as caught:
                http_transport('GET',self.base+path,{'Authorization':'Bearer '+KEY},None,1)
            self.assertEqual(caught.exception.code,code);self.assertNotIn(KEY,str(caught.exception));self.assertEqual(len(self.hits),n+1)
        with patch('urllib.request.OpenerDirector.open',side_effect=__import__('urllib.error',fromlist=['URLError']).URLError(KEY)):
            with self.assertRaises(TransportError) as caught:http_transport('GET',self.base,{},None,1)
        self.assertEqual(caught.exception.code,'connection_error');self.assertNotIn(KEY,str(caught.exception))

    def test_http_invoke_cli_and_no_proxy(self):
        c=config();c['profiles']['one']['base_url']=self.base
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);(d/'c').write_text(json.dumps(c));(d/'m').write_text(json.dumps(MESSAGES))
            with patch.dict('os.environ',{'http_proxy':'http://example.invalid:9','HTTP_PROXY':'http://example.invalid:9'}),contextlib.redirect_stdout(io.StringIO()) as out:
                code=main(['invoke','--config',str(d/'c'),'--role','generation','--messages',str(d/'m'),'--output',str(d/'result')])
            self.assertEqual(code,0);r=json.loads((d/'result').read_text());self.assertEqual(r['status'],'complete')
            self.assertEqual([x[:2] for x in self.hits],[('GET','/api/tags'),('POST','/api/chat'),('GET','/api/tags')])
            self.assertEqual(r['identity_verification']['status'],'verified');self.assertNotIn(KEY,out.getvalue())
            self.assertEqual(self.hits[1][2]['messages'],MESSAGES)

if __name__=='__main__':unittest.main()
