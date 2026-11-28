"""Installed preview and real saved replay; only explicit BM25 execution uses a fake provider."""
from pathlib import Path
import json,sys
from rag_package.ui_server import create_server
E=Path(__file__).resolve().parent
ws=Path(json.loads((E/'installation.json').read_text())['base'])/'practice'
def fixture(method,url,headers,body,timeout):
    if method=='GET':
        model=json.loads((ws/'handbook-model.json').read_text())['profiles']['local']
        return {'models':[{'name':model['model'],'digest':model['identity']['expected_digest']}]}
    request=json.loads(body['messages'][-1]['content'])
    fail='실패 시험' in request['question']
    with (E/'fixture-calls.log').open('a') as f:f.write('failure\n' if fail else 'success\n')
    content='invalid JSON' if fail else json.dumps({'status':'answered','answer':'시험 어댑터의 합성 답변','citations':[{'chunk_id':request['contexts'][0]['chunk_id']}]})
    return {'model':'qwen3:4b','done':True,'done_reason':'stop','message':{'role':'assistant','content':content}}
server=create_server(ws,[ws/'handbook-model.json',ws/'handbook-api.json'],sources=ws/'handbook-sources.json',port=0,
    allow_model=True,transport=fixture,key_resolver=lambda _:None,
    embedding_configs=[ws/'e5.json'],reranker_configs=[ws/'mmini.json'],
    chunk_configs=[ws/'chunk-handbook.json',ws/'chunk-fixed.json'],pipeline_runs=['.rag-runs/pipeline-live'])
print(server.origin,flush=True)
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close()
