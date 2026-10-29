"""Local UI-only fixture: zero model dispatches, production assets unchanged."""
import sys,json,time,html,copy
from pathlib import Path
root=Path(__file__).resolve().parents[4];stage=root/'1. Naive RAG/variants/langchain';ev=root/'docs/verification/p012';sys.path.insert(0,str(stage/'scripts'))
from serve_compare import LearningServer,Handler,error_result
sample=json.loads((root/'docs/verification/p011/browser-q03.json').read_text())['results'][0]['result']
def fake(*,implementation,**kw):
 time.sleep(4)
 if kw['question']=='fixture-error' or (kw['question']=='fixture-pair-error' and implementation=='langchain'):
  r=error_result('[UI fixture] timeout','timeout')
 else:
  r=copy.deepcopy(sample);r['answer']='[UI fixture, no model call] '+r['answer'];r['trace']['generation_calls']=0;r['trace']['generation']['request_dispatched']=False
 r['trace']['comparison']={'implementation':implementation,'run_id':'ui-fixture'};r['trace']['fixture']=True
 with (ev/'fixture-ledger.jsonl').open('a') as f:f.write(json.dumps({'question':kw['question'],'implementation':implementation,'model_dispatches':0,'status':r['status']})+'\n')
 return r
original_get=Handler.do_GET
pages={'/narrow-learning':(390,'index.html'),'/narrow-experiment':(390,'implementation.html'),'/desktop-learning':(1200,'index.html'),'/desktop-experiment':(1200,'implementation.html')}
def fixture_get(self):
 if self.path in pages:
  if not self.local_request():return
  width,name=pages[self.path];raw=('<!doctype html><html><body><p>UI fixture: '+str(width)+'px, no model calls</p><iframe title="'+str(width)+'px test" width="'+str(width)+'" height="2400" srcdoc="'+html.escape((stage/'web_compare'/name).read_text(),quote=True)+'"></iframe></body></html>').encode()
  self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 else:original_get(self)
Handler.do_GET=fixture_get
with LearningServer(8002,fake) as s:
 print('UI fixture at8002; no model calls',flush=True);s.serve_forever()
