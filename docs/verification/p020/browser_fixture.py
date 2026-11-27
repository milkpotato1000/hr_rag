"""Owned installed UI, synthetic sources and explicitly injected scores only."""
from pathlib import Path
import json,os,sys
from rag_package.workspace import init
from rag_package import candidates,reranker
from rag_package.documents import snapshot
from rag_package.retrieval import build
from rag_package.rag import ask
from rag_package.storage import read_json,write_json,fingerprint
from rag_package.ui_server import create_server
base=Path.cwd();ws=base/'ui-workspace';init(ws)
q='생일 휴가의 자격과 신청 기한, 사용 기간을 함께 알려 주세요.'
cfg=read_json(ws/'fixed.json');cfg.update(schema_version=2,embedding_config=None);cfg['retrieval'].update(candidate_k=20,rrf_k=60);write_json(ws/'rag.json',cfg)
snapshot(ws/'sources.json',ws/'snapshot');build(ws/'snapshot',ws/'rag.json',ws/'build')
ask(ws/'build',ws/'rag.json',q,ws/'answer',embedding_backend=lambda *a:None)
c=candidates.freeze(ws/'build',ws/'answer','q1',20,ws/'candidates')
profiles=[]
for n,model in enumerate(reranker.CATALOG):
 p=reranker.profile({'schema_version':1,'model_id':model,'revision':'a'*40,'local_path':'/SYNTHETIC_NOT_LOADED','file_manifest':{'config.json':'b'*64}});dest=ws/f'reranker-{n}.json';write_json(dest,p);profiles.append(dest)
corpus=read_json(ws/'build/chunks.json');birthday=[x for x in corpus if '생일' in x['text']];first=birthday[0]
qr={'schema_version':1,'source_fingerprint':c['source_fingerprint'],'chunk_fingerprint':c['chunk_fingerprint'],'questions_hash':fingerprint([{'id':'q1','question':q}]),'judgments_complete':True,'judgments':{'q1':{x['chunk_id']:2 for x in birthday}}};write_json(ws/'qrels.json',qr)
facts={'schema_version':1,'source_fingerprint':c['source_fingerprint'],'questions_hash':qr['questions_hash'],'offset_unit':'unicode_codepoint','questions':[{'question_id':'q1','required_facts':[{'fact_id':'birthday','alternatives':[{'spans':[{'document_id':first['document_id'],'start':first['start'],'end':first['end'],'quote':first['text']}]}]}]}]};write_json(ws/'facts.json',facts)
def backend(payload):
 assert set(payload)=={'profile','query','passages','ids'}
 return {'scores':[{'chunk_id':cid,'score':float(n) if payload['profile']['model_id'].startswith('BAAI') else -float(n)} for n,cid in enumerate(payload['ids'])]}
s=create_server(ws,[ws/'llm-local.json'],ws/'sources.json',port=0,reranker_configs=profiles,allow_reranking=True,reranker_backend=backend,embedding_backend=lambda *a:None,qrels=[ws/'qrels.json'],facts=[ws/'facts.json'])
r=s.ui.registry;sid=r.add_artifact(ws/'snapshot','snapshot');bid=r.add_artifact(ws/'build','build',snapshot_id=sid);aid=r.add_artifact(ws/'answer','answer',snapshot_id=sid,build_id=bid);cid=r.add_artifact(ws/'candidates','candidates')
record={'url':s.origin,'pid':os.getpid(),'workspace':str(ws),'candidate_id':cid,'answer_id':aid,'build_id':bid,'snapshot_id':sid,'kind':'test_fixture','pretrained_models':0,'actual_generation':0}
write_json(base/'browser-server.json',record);print(json.dumps(record),flush=True)
try:s.serve_forever()
except KeyboardInterrupt:pass
finally:s.server_close();print('owned_server_closed',flush=True)
