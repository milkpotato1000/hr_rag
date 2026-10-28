"""Offline UI fault harness. Responses are explicitly marked fixtures."""
import sys,time,json,copy,html
from pathlib import Path
root=Path(__file__).resolve().parents[4];stage=root/'1. Naive RAG/variants/langchain';sys.path.insert(0,str(stage/'scripts'))
from serve_compare import LearningServer,error_result,Handler
import rag
from generation import load_generation_lock,request_for_ids
class Fixture:
 lock=load_generation_lock()
 def generate(self,messages,ids,*,on_send=None):
  on_send(request_for_ids(self.lock,ids))
  return json.dumps({'status':'answered','answer':'[브라우저 검증 fixture] 입사 후 3개월, 수습 제외, 연 1일입니다.','citations':[{'chunk_id':cid} for cid in ids[:3]]}),{}
def fake(*,implementation='direct',**kw):
 time.sleep(2)
 if kw['question']=='한쪽 오류' and implementation=='langchain':return error_result('[fixture] timeout','timeout')
 r=rag.ask(**{**kw,'retriever':'bm25'},generator=Fixture())
 r['trace']['comparison']={'implementation':implementation,'run_id':'fixture-only','langchain_core_version':'1.7.0'};return r
original_get=Handler.do_GET
def fixture_get(self):
 if self.path=='/narrow':
  if self.local_request():
   raw=('<html><body><h1>Offline fixture, 390px viewport</h1><iframe title="390px test" width="390" height="1000" srcdoc="'+html.escape((stage/'web_compare/index.html').read_text(),quote=True)+'"></iframe></body></html>').encode()
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 else:original_get(self)
Handler.do_GET=fixture_get
with LearningServer(8002,fake) as server:
 print('OFFLINE BROWSER FIXTURE http://127.0.0.1:8002',flush=True);server.serve_forever()
