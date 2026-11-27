"""Installed UI fixture, owned loopback only, no real model/network."""
from pathlib import Path
import json,os,socket
from rag_package.workspace import init
from rag_package.ui_server import create_server
import rag_package
base=Path.cwd();assert 'site-packages' in rag_package.__file__;assert 'PYTHONPATH' not in os.environ
ws=base/'browser-workspace';init(ws);calls=[]
for name,mid in [('e5','intfloat/multilingual-e5-small'),('bge','BAAI/bge-m3')]:
 p={'schema_version':1,'model_id':mid,'revision':'a'*40,'local_path':'/SYNTHETIC_NOT_LOADED','file_manifest':{'config.json':'b'*64},'device':'cpu','dtype':'float32','max_input_tokens':512,'batch_size':1,'timeout_seconds':120,'max_chunks':2000};(ws/(name+'.json')).write_text(json.dumps(p))
def backend(p,texts,ids,kind):
 calls.append({'kind':kind,'count':len(texts),'model':p['model_id']});dim=384 if 'e5' in p['model_id'] else 1024;rows=[]
 for n,t in enumerate(texts):
  r=[0.0]*dim;r[0]=1 if kind=='query' or '생일' in t else -.5;r[1]=.1*(n+1);rows.append(r)
 return {'vectors':rows,'sdk_versions':{'synthetic':'1'}}
def forbidden(*a,**k):raise AssertionError('outbound forbidden')
socket.socket.connect=forbidden;socket.getaddrinfo=forbidden
server=create_server(ws,[ws/'llm-local.json'],ws/'sources.json',port=0,embedding_configs=[ws/'e5.json',ws/'bge.json'],allow_retrieval=True,embedding_backend=backend)
record={'url':server.origin,'pid':os.getpid(),'installed_import':rag_package.__file__,'execution_kind':'test_fixture','pretrained_model_llm_drive_calls':0}
(base/'browser-server.json').write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close();record.update(stopped=True,embedding_fixture_calls=calls);(base/'browser-server.json').write_text(json.dumps(record,indent=2)+'\n')
