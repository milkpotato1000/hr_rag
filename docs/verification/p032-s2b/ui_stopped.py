"""Owned loopback failure report + installed UI; no inference or repair."""
from pathlib import Path
import json,tempfile,shutil,threading,functools,os,socket
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from rag_package.ui_server import create_server
from rag_package.ui_registry import uid
from rag_package.storage import write_json
from rag_package import embedding,reranker,llm,rag,retrieval,chunk_artifact
def deny(*a,**kw):raise RuntimeError('Stopped S2b forbids execution')
embedding.encode=reranker.score=llm.invoke=rag.ask=rag.compare=retrieval.build=chunk_artifact.build=deny
socket.create_connection=deny
E=Path(__file__).resolve().parent;ws=Path(tempfile.mkdtemp(prefix='p032-s2b-stopped-ui-')).resolve()
shutil.copyfile(E/'run001/input/llm.json',ws/'llm.json')
s=create_server(ws,[ws/'llm.json'],port=0)
for name in ('fixed','recursive','structure'):
    shutil.copytree(E/'run001/input/chunks'/name,ws/name)
    aid=s.ui.registry.add_artifact(ws/name,'chunks');key=uid()
    s.ui.jobs.records[key]={'id':key,'request_id':key,'kind':'기존 S2a 경계 '+name,'status':'completed','stage':'stored_replay_only','artifact_ids':[aid],'dispatch_attempted':False,'error':None}
key=uid();s.ui.jobs.records[key]={'id':key,'request_id':key,'kind':'S2b 의미 경계 실패 · 검색40 미실행','status':'failed','stage':'semantic_boundary','artifact_ids':[],'dispatch_attempted':True,'error':{'code':'embedding_sdk_failed'}}
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
report=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(E)))
t=threading.Thread(target=report.serve_forever,daemon=True);t.start()
info={'ui_url':s.origin,'report_url':'http://127.0.0.1:'+str(report.server_port)+'/report.html','pid':os.getpid(),'model_calls':0,'purpose':'stored failure visualization, existing rules only','flags':'all off'}
write_json(E/'ui-server.json',info);print(json.dumps(info),flush=True)
try:s.serve_forever()
except KeyboardInterrupt:pass
finally:s.server_close();report.shutdown();report.server_close();t.join();write_json(E/'ui-closed.json',{'owned_servers_closed':True,'model_calls':0});print('owned_servers_closed',flush=True)
