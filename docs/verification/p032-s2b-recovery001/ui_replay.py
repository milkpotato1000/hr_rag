"""Installed UI, saved actual results only; no model or external operations."""
from pathlib import Path
import json,tempfile,shutil,threading,functools,os,socket,subprocess
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from rag_package.ui_server import create_server
from rag_package.ui_registry import uid
from rag_package.storage import write_json,read_json
from rag_package import embedding,reranker,llm,retrieval,rag,chunk_artifact
from rag_package.llm import core,transport
E=Path(__file__).resolve().parent;R=E/'run001';ws=Path(tempfile.mkdtemp(prefix='p032-s2b-recovery-ui-')).resolve();blocked=[]
def deny(*a,**k):blocked.append('forbidden');raise AssertionError('stored model-free UI')
for module,name in [(embedding,'encode'),(reranker,'score'),(llm,'invoke'),(core,'invoke'),(core,'http_transport'),(transport,'http_transport'),(retrieval,'build'),(retrieval,'select'),(rag,'ask'),(rag,'compare'),(chunk_artifact,'build')]:setattr(module,name,deny)
subprocess.Popen=deny;socket.create_connection=deny
shutil.copyfile(R/'input/llm.json',ws/'llm.json');shutil.copytree(R/'comparison',ws/'comparison')
s=create_server(ws,[ws/'llm.json'],port=0);registry=s.ui.registry;root=ws/'comparison';sid=registry.add_artifact(root/'snapshot','snapshot');result=read_json(root/'comparison.json');builds={};answers={}
for c in result['configs']:
 cid=c['id'];builds[cid]=registry.add_artifact(root/cid/'build','build',snapshot_id=sid)
 aid=registry.add_artifact(root/cid/'build/frozen-chunks','chunks',snapshot_id=sid);key=uid();method=result['chunk_artifacts'][int(cid[-1])-1]['config']['method']
 s.ui.jobs.records[key]={'id':key,'request_id':key,'kind':'저장 경계 '+method,'status':'completed','stage':'model_free_replay','dispatch_attempted':False,'artifact_ids':[aid],'error':None}
for row in result['rows']:
 cid=row['config_id'];answers[cid+'/'+row['question_id']]=registry.add_artifact((root/row['result_path']).parent,'answer',snapshot_id=sid,build_id=builds[cid])
aid=registry.add_artifact(root,'comparison',snapshot_id=sid,build_ids=builds,answer_ids=answers,labels=[x['config']['method'] for x in result['chunk_artifacts']]);key=uid()
s.ui.jobs.records[key]={'id':key,'request_id':key,'kind':'실제 청킹 4방식 · 검색40 저장 재생','status':'completed','stage':'model_free_replay','dispatch_attempted':False,'artifact_ids':[aid],'error':None}
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
report=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(E)));t=threading.Thread(target=report.serve_forever,daemon=True);t.start()
info={'ui_url':s.origin,'report_url':'http://127.0.0.1:'+str(report.server_port)+'/report.html','pid':os.getpid(),'workspace':str(ws),'execution_flags':'all off','model_calls':0};write_json(E/'ui-server.json',info);print(json.dumps(info),flush=True)
try:s.serve_forever()
except KeyboardInterrupt:pass
finally:s.server_close();report.shutdown();report.server_close();t.join();write_json(E/'ui-closed.json',{'owned_servers_closed':True,'forbidden_attempts':blocked,'model_calls':0});print('owned_servers_closed',flush=True)
