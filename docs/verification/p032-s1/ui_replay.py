"""Installed UI + report, registered stored S1 artifacts; all execution flags off."""
from pathlib import Path
import sys,json,shutil,tempfile,threading,functools,os
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from rag_package.ui_server import create_server
from rag_package.ui_registry import uid
from rag_package.storage import read_json,write_json
E=Path(__file__).resolve().parent;I=E/'input';R=E/'run001';base=Path(tempfile.mkdtemp(prefix='p032-ui-replay-')).resolve();ws=base/'workspace';ws.mkdir()
shutil.copyfile(I/'llm-preview-only.json',ws/'llm.json');shutil.copyfile(I/'qrels.json',ws/'qrels.json');shutil.copyfile(I/'facts.json',ws/'facts.json')
for key in ('e5','mmini'):shutil.copyfile(R/'profiles'/(key+'.json'),ws/(key+'.json'))
shutil.copytree(I/'snapshot-installed',ws/'snapshot');shutil.copytree(I/'build-bm25',ws/'bm25-build');shutil.copytree(R/'builds/e5',ws/'e5-build')
s=create_server(ws,[ws/'llm.json'],port=0,embedding_configs=[ws/'e5.json'],reranker_configs=[ws/'mmini.json'],qrels=[ws/'qrels.json'],facts=[ws/'facts.json'])
r=s.ui.registry;sid=r.add_artifact(ws/'snapshot','snapshot');bids={k:r.add_artifact(ws/(k+'-build'),'build',snapshot_id=sid) for k in ('bm25','e5')}
artifacts={}
for qid in ('gt01','gt02'):
 cp=ws/('candidates-'+qid);shutil.copytree(R/'candidates'/qid,cp);artifacts['candidates/'+qid]=r.add_artifact(cp,'candidates')
 rp=ws/('none-'+qid);shutil.copytree(R/'rerank/none'/qid,rp);artifacts['none/'+qid]=r.add_artifact(rp,'rerank')
for method in ('bm25','e5-dense','e5-hybrid'):
 qid='gt01';ap=ws/(method+'-'+qid);shutil.copytree(R/'search'/method/qid,ap);artifacts[method+'/'+qid]=r.add_artifact(ap,'answer',snapshot_id=sid,build_id=bids['bm25' if method=='bm25' else 'e5'])
for label,aid in artifacts.items():
 if label.startswith('candidates'):continue
 key=uid();record={'id':key,'request_id':key,'kind':'저장 결과 재생 '+label,'status':'completed','stage':'model_free_replay','dispatch_attempted':False,'artifact_ids':[aid],'error':None}
 s.ui.jobs.records[key]=record
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
report=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(E/'report-final')))
t=threading.Thread(target=report.serve_forever,daemon=True);t.start()
info={'ui_url':s.origin,'report_url':'http://127.0.0.1:'+str(report.server_port)+'/report.html','pid':os.getpid(),'workspace':str(ws),'registered_artifacts':artifacts,'execution_flags':'all off','replay_new_model_calls':0,'original_results':'live E5 search; none model-free; mMiniLM failed, no BGE'}
write_json(E/'ui-server.json',info);print(json.dumps(info,ensure_ascii=False),flush=True)
try:s.serve_forever()
except KeyboardInterrupt:pass
finally:s.server_close();report.shutdown();report.server_close();t.join();print('owned_ui_and_report_servers_closed',flush=True)
