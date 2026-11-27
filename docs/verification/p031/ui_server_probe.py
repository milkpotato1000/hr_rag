"""Owned installed-package UI. Generated random profiles, no model execution flags."""
from pathlib import Path
import json,sys
from rag_package.llm_setup import configure
from rag_package.ui_server import create_server
from rag_package.storage import read_json,write_json
ws=Path(sys.argv[1]);out=ws/'ui-llm.json'
if not out.exists():configure(ws/'llm-spec-local.json',out)
chunk=read_json(ws/'chunk-semantic.json');chunk['embedding_config']='model-0/prepared/profile.json';write_json(ws/'ui-semantic.json',chunk)
server=create_server(ws,[out],sources=ws/'sources.json',port=0,
    embedding_configs=[ws/'model-0/prepared/profile.json',ws/'model-1/prepared/profile.json'],
    reranker_configs=[ws/'model-2/prepared/profile.json',ws/'model-3/prepared/profile.json'],
    chunk_configs=[ws/'chunk-fixed.json',ws/'ui-semantic.json'])
print(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'workspace':str(ws),'flags':'all_off','fixture':'tiny_random_preparation'}),flush=True)
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close();print('owned_server_closed',flush=True)
