"""Exercise the installed CLI against a temporary loopback-only TLS fixture."""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import tempfile
from threading import Thread

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def save(name, value):
    (HERE/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def verify():
    base = Path(read(HERE/'installation.json')['base'])
    ws = Path(tempfile.mkdtemp(dir=base))/'practice'
    cli = base/'env/bin/rag-lab'
    site = Path('env/lib/python3.12/site-packages')
    previous = Path(read(HERE.parent/'p032-s7/installation.json')['base'])
    for name in ('pypdf', 'pypdf-6.21.2.dist-info'):
        if not (base/site/name).exists():
            shutil.copytree(previous/site/name, base/site/name)
    s11 = HERE.parent/'p032-s11'
    setup = read(s11/'setup.json')
    local = Path(setup['practice'])/'.rag-runs/ui/artifacts'/read(s11/'review.json')['job']/'result'
    historical = read(local/'answer/result.json')
    question, quote = setup['question'], setup['quote']
    system = historical['messages'][0]['content']+'\n\nReturn only one valid JSON object, without Markdown fences or other text.'
    user = historical['messages'][1]
    allowed = secrets.token_hex(32)
    denied = secrets.token_hex(32)
    key_name = 'RAG_S29_FIXTURE_TOKEN'
    journal = []
    reports = {}
    env = dict(PATH='/usr/bin:/bin', LANG='en_US.UTF-8', PYTHONDONTWRITEBYTECODE='1')

    def command(*args, key=None, fail=False):
        proc = subprocess.run([cli,*args], cwd=ws if ws.exists() else base, capture_output=True,
                              env=env if key is None else {**env,key_name:key}, text=True, timeout=45)
        assert proc.returncode == int(fail), (args,proc.returncode,proc.stdout[-800:],proc.stderr[-300:])
        return json.loads(proc.stdout)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            openai = self.path == '/v1/chat/completions'
            provider = 'openai_chat' if openai else 'anthropic_messages'
            assert self.path in ('/v1/chat/completions','/v1/messages')
            assert data['model'] == 'fixture-'+provider and data['stream'] is False
            if openai:
                assert data['messages'] == [{'role':'system','content':system}, user]
                assert data['response_format']=={'type':'json_object'} and data['max_completion_tokens']>0
            else:
                assert data['system']==system and data['messages']==[user] and data['max_tokens']>0
                assert self.headers['anthropic-version']=='2026-10-21'
            payload = json.loads(data['messages'][-1]['content'])
            assert payload['question']==question and len(payload['contexts'])==5
            cited = next(c for c in payload['contexts'] if quote in c['text'])
            auth = self.headers.get('Authorization')
            assert auth in ('Bearer '+allowed,'Bearer '+denied)
            ok = auth == 'Bearer '+allowed
            journal.append(dict(provider=provider,status=200 if ok else 401,request_model=data['model'],
                                route=self.path,roles_verified=True,authorization_scheme_verified=True,
                                contexts=[c['chunk_id'] for c in payload['contexts']]))
            answer = json.dumps(dict(status='answered',answer='팀장',citations=[dict(chunk_id=cited['chunk_id'])]))
            if not ok:
                response = {'error':'fixture_denied'}
            elif openai:
                response = dict(model=data['model'],choices=[dict(finish_reason='stop',message=dict(
                    role='assistant',content=answer))],usage=dict(prompt_tokens=111,completion_tokens=12))
            else:
                response = dict(type='message',role='assistant',model=data['model'],stop_reason='end_turn',
                                content=[dict(type='text',text=answer)],usage=dict(input_tokens=108,output_tokens=13))
            wire = json.dumps(response).encode()
            self.send_response(200 if ok else 401)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(wire)

    command('init','--out',str(ws))
    with tempfile.TemporaryDirectory() as temp, HTTPServer(('127.0.0.1',0), Handler) as server:
        cert, key = Path(temp)/'cert.pem', Path(temp)/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                        '-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1',
                        '-keyout',key,'-out',cert],check=True,capture_output=True)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert,key)
        server.socket=tls.wrap_socket(server.socket,server_side=True)
        env['SSL_CERT_FILE']=str(cert)
        thread=Thread(target=server.serve_forever)
        thread.start()
        try:
            endpoint=f'https://127.0.0.1:{server.server_port}/v1'
            for provider in ('openai_chat','anthropic_messages'):
                initial=len(journal)
                command('generation-setup','--provider',provider,'--model','fixture-'+provider,
                        '--key-env',key_name,'--endpoint',endpoint,'--out',provider)
                args=['pipeline','--sources','handbook-sources.json','--chunk-config','chunk-fixed.json',
                      '--search-config',provider+'/search.json','--question',question]
                preview=command(*args,'--out',provider+'-preview')
                assert preview['plan']['generation']['destination']==endpoint
                assert preview['status']=='preview' and len(journal)==initial
                rows={}
                for label,token,code,delta in [('success',allowed,None,1),('missing',None,'missing_api_key',0),
                                               ('denied',denied,'http_401',1)]:
                    count=len(journal)
                    folder=provider+'-'+label
                    report=command(*args,'--execute','--out',folder,key=token,fail=bool(code))
                    assert command('pipeline-replay','--run',folder,fail=bool(code))==report
                    assert len(journal)-count==delta
                    detail=read(ws/folder/'answer/result.json')
                    response=detail['provider_result']
                    assert detail['contexts']==historical['contexts'] and detail['generation_requests']==delta
                    rows[label]=dict(posts=delta,replay_posts=0,status=report['status'],error=response['error'],
                                     dispatch_attempted=detail['dispatch_attempted'])
                    if code:
                        assert response['error']['code']==code and report['status']=='failed' and report['answer'] is None
                    else:
                        assert report['status']=='answered' and report['answer']==historical['answer']==detail['answer']
                        citation=detail['answer']['citations'][0]
                        page=next(p for p in citation['pages'] if p['page']==1)
                        start=citation['start']+citation['quote'].index(quote)
                        assert page['canonical_start']<=start and start+len(quote)<=page['canonical_end']
                        usage=response['usage']
                        assert (usage['input_tokens'],usage['output_tokens'])==((111,12) if provider=='openai_chat' else (108,13))
                        rows[label].update(answer=report['answer'],usage=usage,quote_page=1)
                reports[provider]=rows
            comparisons={}
            for label,left,right in [('api_pair','openai_chat-success','anthropic_messages-success'),
                                     ('saved_local','openai_chat-success',str(local))]:
                pair=command('pipeline-compare','--runs',left,right)
                assert pair['same_source'] and pair['same_question']
                assert all(r['contexts']==historical['contexts'] and r['answer']==historical['answer'] for r in pair['runs'])
                comparisons[label]=dict(changed=pair['changed'],same_contexts=True,answers=[r['answer']['answer'] for r in pair['runs']])
            assert len(journal)==4
        finally:
            server.shutdown()
            thread.join()
    assert not cert.exists() and not key.exists()
    for f in ws.rglob('*'):
        if f.is_file():
            raw=f.read_bytes()
            assert allowed.encode() not in raw and denied.encode() not in raw and b'PRIVATE KEY-----' not in raw
    save('verified.json',dict(kind='local_https_fixture',question=question,quote=quote,providers=reports,
                              wire_observations=journal,comparisons=comparisons,paid_requests=0,
                              historical_local_model_requests=0,temporary_key_removed=True))
    print('Installed HTTPS fixture, citations, comparisons and authenticated failure paths PASS')


if __name__=='__main__':
    verify()
