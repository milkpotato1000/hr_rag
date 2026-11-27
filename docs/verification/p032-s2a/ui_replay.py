"""Owned loopback UI of existing artifacts only; external/model transport denied."""
from pathlib import Path
import sys,json,tempfile,shutil,threading,functools,os,subprocess,socket
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from rag_package.ui_server import create_server
from rag_package.ui_registry import uid
from rag_package.storage import write_json
from rag_package import embedding,reranker,llm,retrieval,rag,chunk_artifact
from rag_package.llm import core,transport
E=Path(__file__).resolve().parent;R=E/'run001';ws=Path(tempfile.mkdtemp(prefix='p032-s2a-ui-')).resolve()
blocked=[]
def deny(*a,**kw):
    blocked.append('forbidden_model_or_external_operation');raise AssertionError('S2a read-only replay')
for module,name in [(embedding,'encode'),(reranker,'score'),(llm,'invoke'),(core,'invoke'),(core,'http_transport'),(transport,'http_transport'),(retrieval,'build'),(retrieval,'select'),(rag,'ask'),(rag,'compare'),(chunk_artifact,'build')]:
    setattr(module,name,deny)
subprocess.Popen=deny;socket.create_connection=deny
shutil.copyfile(R/'configs/llm-local-example.json',ws/'llm.json')
shutil.copytree(R/'snapshot',ws/'snapshot')
s=create_server(ws,[ws/'llm.json'],port=0)
r=s.ui.registry;sid=r.add_artifact(ws/'snapshot','snapshot');artifacts={}
for kind,names in [('chunks',('fixed','recursive','structure')),('chunk-preview',('semantic','llm-local','llm-api'))]:
    for name in names:
        src=R/('chunks' if kind=='chunks' else 'previews')/name
        shutil.copytree(src,ws/name)
        aid=r.add_artifact(ws/name,kind,snapshot_id=sid);artifacts[name]=aid
        key=uid();s.ui.jobs.records[key]={'id':key,'request_id':key,'kind':'S2a 저장 경계 '+name,'status':'completed','stage':'offline_replay','dispatch_attempted':False,'artifact_ids':[aid],'error':None}
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
report=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(E)))
t=threading.Thread(target=report.serve_forever,daemon=True);t.start()
info={'ui_url':s.origin,'report_url':'http://127.0.0.1:'+str(report.server_port)+'/report.html','pid':os.getpid(),
      'workspace':str(ws),'artifacts':artifacts,'model_execution_flags':'all off','external_network_model_calls':0,'loopback':'owned browser observation only; separate from network-free preparation'}
write_json(E/'ui-server.json',info);print(json.dumps(info),flush=True)
try:s.serve_forever()
except KeyboardInterrupt:pass
finally:
    s.server_close();report.shutdown();report.server_close();t.join()
    write_json(E/'ui-closed.json',{'owned_servers_closed':True,'forbidden_attempts':blocked,'model_external_calls':0})
    print('owned_servers_closed',flush=True)
