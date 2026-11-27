from pathlib import Path
import json,socket,sys,importlib.metadata
import rag_package
from rag_package import chunk_artifact,embedding
from rag_package.workspace import init
from rag_package.documents import snapshot
from rag_package.storage import read_json,write_json
assert 'site-packages' in rag_package.__file__
def forbidden(*a,**k):raise AssertionError('network forbidden')
socket.socket.connect=forbidden;socket.getaddrinfo=forbidden
ws=Path.cwd()/'tiny-workspace';init(ws);snapshot(ws/'sources.json',ws/'snapshot')
p=read_json('tiny-profile.json');write_json(ws/'embedding.json',p)
c={'schema_version':1,'method':'semantic','size_chars':200,'overlap_chars':20,'unit_max_chars':40,'distance_threshold':.5,'minimum_chars':40,'embedding_config':'embedding.json'};write_json(ws/'semantic.json',c)
r=chunk_artifact.build(ws/'snapshot',ws/'semantic.json',ws/'chunks',execute=True);assert r['status']=='ready',r
obs=r['work']['unit_observation'];assert obs['workers_started']==1 and obs['worker_exited'] and obs['completed_items']>0
embedding.encode=lambda *a,**k:(_ for _ in ()).throw(AssertionError('no replay model'))
chunk_artifact.replay(ws/'chunks');write_json(ws/'derive.json',dict(c,distance_threshold=1.5));chunk_artifact.derive(ws/'chunks',ws/'derive.json',ws/'derived');chunk_artifact.replay(ws/'derived')
print(json.dumps({'status':'PASS','installed_path':rag_package.__file__,'random_weights_only':True,'pretrained_loads':0,'network_calls':0,'work':r['work']},indent=2))
