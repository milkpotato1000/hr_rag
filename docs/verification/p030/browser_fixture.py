"""Installed UI synthetic boundary fixture; no real model or external HTTP."""
from pathlib import Path
import os,json
from rag_package.workspace import init
from rag_package.documents import snapshot,load_snapshot
from rag_package import chunk_artifact
from rag_package.storage import read_json,write_json,fingerprint
from rag_package.ui_server import create_server
base=Path.cwd();ws=base/'ui-workspace';init(ws)
# A non-BMP character checks the UI codepoint convention without touching old fixtures.
with (ws/'documents/birthday.md').open('a') as f:f.write('\n\n😀 학습용 부록: 생일휴가의 조건을 원문과 대조하세요.\n')
lc=read_json(ws/'llm-chunking.json');lc['profiles'][lc['roles']['chunking']]={'mode':'local','provider':'ollama','model':'fixture-model','base_url':'http://127.0.0.1:1','max_output_tokens':256,'timeout_seconds':1,'response_mode':'json_object','identity':{'expected_digest':'a'*64,'hf_id':'fixture/model','conversion':'synthetic'}};write_json(ws/'llm-chunking.json',lc)
ep=read_json(ws/'embedding-e5.json');ep.update(revision='a'*40,local_path='/SYNTHETIC_NOT_LOADED',file_manifest={'config.json':'b'*64});write_json(ws/'embedding-e5.json',ep)
def enc(p,texts,ids,kind):return {'vectors':[[1.0,n%2]+[0.0]*382 for n in range(len(texts))],'sdk_versions':{'synthetic':'1'}}
def send(method,url,headers,body,timeout):
 if method=='GET':return {'models':[{'name':'fixture-model','digest':'a'*64}]}
 data=json.loads(body['messages'][-1]['content']);assert set(data)=={'maximum_source_chars','units'}
 return {'model':'fixture-model','message':{'role':'assistant','content':json.dumps({'end_unit_ids':[u['id'] for u in data['units']]})},'done':True,'done_reason':'stop'}
snapshot(ws/'sources.json',ws/'snapshot');methods=('fixed','recursive','structure','semantic','llm')
for method in methods:
 r=chunk_artifact.build(ws/'snapshot',ws/f'chunk-{method}.json',ws/f'ready-{method}',execute=True,embedding_backend=enc if method=='semantic' else None,transport=send if method=='llm' else None);assert r['status']=='ready',r
sm,docs=load_snapshot(ws/'snapshot');q='생일 휴가의 자격과 신청 기한은?';d=next(d for d in docs if '생일' in d['text']);start=d['text'].index('생일')
write_json(ws/'facts.json',{'schema_version':1,'source_fingerprint':sm['fingerprint'],'questions_hash':fingerprint([{'id':'q1','question':q}]),'offset_unit':'unicode_codepoint','questions':[{'question_id':'q1','required_facts':[{'fact_id':'birthday','alternatives':[{'spans':[{'document_id':d['document_id'],'start':start,'end':start+2,'quote':'생일'}]}]}]}]})
s=create_server(ws,[ws/'llm-local.json'],ws/'sources.json',port=0,chunk_configs=[ws/f'chunk-{method}.json' for method in methods],facts=[ws/'facts.json'],allow_chunking=True,embedding_backend=enc,transport=send)
r=s.ui.registry;sid=r.add_artifact(ws/'snapshot','snapshot');ids={method:r.add_artifact(ws/f'ready-{method}','chunks') for method in methods}
record={'url':s.origin,'pid':os.getpid(),'workspace':str(ws),'snapshot_id':sid,'chunks':ids,'execution_kind':'test_fixture','real_models_or_api':0};write_json(base/'browser-server.json',record);print(json.dumps(record),flush=True)
try:s.serve_forever()
except KeyboardInterrupt:pass
finally:s.server_close();print('owned_server_closed',flush=True)
