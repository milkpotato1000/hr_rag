"""Execute both printed commands from the independently installed package."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import threading
import urllib.request

here=Path(__file__).resolve().parent
def read(p):
    return json.loads(p.read_text())
base=Path(read(here/'installation.json')['base'])
ws=base/'practice'
env={'PATH':str(base/'env/bin')+':/usr/bin:/bin','LANG':'en_US.UTF-8','PYTHONUNBUFFERED':'1',
     'PYTHONDONTWRITEBYTECODE':'1','PIP_NO_INDEX':'1'}
site=Path('env/lib/python3.12/site-packages')
previous=Path(read(here.parent/'p032-s7/installation.json')['base'])
for name in ('pypdf','pypdf-6.21.2.dist-info'):
    shutil.copytree(previous/site/name,base/site/name)
def run(*args,cwd=ws):
    p=subprocess.run(['rag-lab',*args],cwd=cwd,env=env,capture_output=True,text=True,check=True,timeout=30)
    return json.loads(p.stdout)
run('init','--out','practice',cwd=base)
requests=[]
known=read(here.parent/'p032-s13/inputs.json')['digest']
class Metadata(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,data):
        wire=json.dumps(data).encode()
        self.send_response(200);self.end_headers();self.wfile.write(wire)
    def do_GET(self):
        requests.append(self.path)
        assert self.path=='/api/tags'
        self.reply({'models':[{'name':'qwen3:4b','digest':self.server.digest}]})
    def do_POST(self):
        requests.append(self.path)
        assert self.path=='/api/show'
        assert json.loads(self.rfile.read(int(self.headers['Content-Length'])))=={'model':'qwen3:4b'}
        self.reply({'model_info':{},'details':{'quantization_level':'Q4_K_M' if self.server.digest==known else 'Q8_0'}})

server=HTTPServer(('127.0.0.1',0),Metadata)
thread=threading.Thread(target=server.serve_forever);thread.start()
endpoint='http://127.0.0.1:'+str(server.server_port)
results=[]
try:
    server.digest=known
    assert run('local-models','--endpoint',endpoint)['models'][0]['model']=='qwen3:4b'
    for folder,provider,model in [('local','ollama','qwen3:4b'),('api','openai_chat','lab-api-model'),('claude','anthropic_messages','lab-claude-model')]:
        options=['--inspect-local','--endpoint',endpoint] if folder=='local' else ['--key-env','LAB_API_KEY']
        setup=run('generation-setup','--provider',provider,'--model',model,'--out',folder,*options)
        args=shlex.split(setup['commands']['pipeline_preview'])
        result=run(*args[1:])
        assert result['plan']['generation']['model']==model and result['generation_requests']==0
        assert run('pipeline-replay','--run',args[-1])==result
        serve_args=shlex.split(setup['commands']['serve'])+['--port','0']
        ui=subprocess.Popen(serve_args,cwd=ws,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            origin=json.loads(ui.stdout.readline())['url']
            boot=json.load(urllib.request.urlopen(origin+'/api/bootstrap',timeout=5))['data']
            assert any(c['model']==model and c['provider']==provider for c in boot['configs'])
            assert not boot['allow_model_execution']
        finally:
            ui.terminate();ui.wait(timeout=5)
        results.append(dict(provider=provider,model=model,destination=result['plan']['generation']['destination'],
                            source=result['plan']['source_fingerprint'],question=result['question'],
                            generation_requests=0,ui_profile_registered=True,secrets_read=setup['secrets_read']))
    assert len({r['source'] for r in results})==len({r['question'] for r in results})==1
    server.digest='4'*64
    changed=run('generation-setup','--provider','ollama','--model','qwen3:4b','--endpoint',endpoint,'--inspect-local','--out','changed')
    profile=read(ws/'changed/model.json')['profiles']['local']
    assert profile['identity']['hf_id']=='unknown' and 'think' not in profile
    assert run('llm-configure','--spec','llm-spec-mixed.json','--out','old.json')['http_requests']==0
    assert requests==['/api/tags','/api/tags','/api/show','/api/tags','/api/show']
finally:
    server.shutdown();server.server_close();thread.join()
(here/'verified.json').write_text(json.dumps(dict(mode_previews=results,local_metadata_fixture=requests,
                        alternate_digest=profile['identity'],real_model_requests=0,paid_requests=0),indent=2,ensure_ascii=False)+'\n')
print('Installed setup / printed CLI / UI registration / model-free replay PASS')
