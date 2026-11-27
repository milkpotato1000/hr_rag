"""Core-only installed artifact/CLI/UI integration, source-free cwd."""
from pathlib import Path
import json,sys,subprocess,importlib.util
from unittest.mock import patch
import rag_package
from rag_package import chunk_artifact,chunk_compare,embedding,llm
from rag_package.storage import read_json,write_json,fingerprint
from rag_package.documents import load_snapshot
root=Path.cwd();assert 'site-packages' in str(rag_package.__file__);assert importlib.util.find_spec('sentence_transformers') is None
commands=[]
def cli(*args):
 p=subprocess.run([sys.executable,'-m','rag_package',*map(str,args)],capture_output=True,text=True);commands.append({'args':list(map(str,args)),'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr});assert p.returncode==0,(args,p.stdout,p.stderr)
cli('init','--out','ws');ws=root/'ws';cli('snapshot','--sources',ws/'sources.json','--out',ws/'snapshot')
for method in ('fixed','recursive','structure','semantic','llm'):cli('chunk','--snapshot',ws/'snapshot','--config',ws/('chunk-'+method+'.json'),'--out',ws/('chunks-'+method))
for method in ('fixed','recursive','structure'):cli('chunk-replay','--run',ws/('chunks-'+method))
ep=read_json(ws/'embedding-e5.json');ep.update(revision='a'*40,local_path='/SYNTHETIC_NOT_LOADED',file_manifest={'config.json':'b'*64});write_json(ws/'embedding-fixture.json',ep)
c=read_json(ws/'chunk-semantic.json');c['embedding_config']='embedding-fixture.json';write_json(ws/'semantic-fixture.json',c)
count=[]
def enc(p,texts,ids,kind):count.append(kind);return {'vectors':[[1.0,n%2]+[0.0]*382 for n in range(len(texts))],'sdk_versions':{'synthetic':'1'}}
r=chunk_artifact.build(ws/'snapshot',ws/'semantic-fixture.json',ws/'semantic-ready',execute=True,embedding_backend=enc);assert r['status']=='ready',r
lc=read_json(ws/'llm-chunking.json');name=lc['roles']['chunking'];lc['profiles'][name]={'mode':'local','provider':'ollama','model':'fixture-model','base_url':'http://127.0.0.1:1','max_output_tokens':256,'timeout_seconds':1,'response_mode':'json_object','identity':{'expected_digest':'a'*64,'hf_id':'fixture/model','conversion':'synthetic'}};write_json(ws/'llm-fixture.json',lc)
c=read_json(ws/'chunk-llm.json');c['llm_config']='llm-fixture.json';write_json(ws/'llm-fixture-chunk.json',c)
def send(method,url,headers,body,timeout):
 if method=='GET':return {'models':[{'name':'fixture-model','digest':'a'*64}]}
 count.append('boundary POST');units=json.loads(body['messages'][-1]['content'])['units'];return {'model':'fixture-model','message':{'role':'assistant','content':json.dumps({'end_unit_ids':[u['id'] for u in units]})},'done':True,'done_reason':'stop'}
r=chunk_artifact.build(ws/'snapshot',ws/'llm-fixture-chunk.json',ws/'llm-ready',execute=True,transport=send);assert r['status']=='ready',r
paths=[]
for n,artifact in enumerate(['chunks-fixed','chunks-recursive','chunks-structure','semantic-ready','llm-ready']):
 c=read_json(ws/'rag-frozen.json');c['chunk_artifact']=artifact;write_json(ws/f'v3-{n}.json',c);paths.append(ws/f'v3-{n}.json')
sm,docs=load_snapshot(ws/'snapshot');qs=[{'id':'q1','question':'생일'},{'id':'q2','question':'연차'}];write_json(ws/'compare-questions.json',qs)
d=next(d for d in docs if '생일' in d['text']);start=d['text'].index('생일');facts={'schema_version':1,'source_fingerprint':sm['fingerprint'],'questions_hash':fingerprint(qs),'offset_unit':'unicode_codepoint','questions':[{'question_id':q['id'],'required_facts':[{'fact_id':'birthday','alternatives':[{'spans':[{'document_id':d['document_id'],'start':start,'end':start+2,'quote':'생일'}]}]}]} for q in qs]};write_json(ws/'facts.json',facts)
cli('compare','--snapshot',ws/'snapshot','--configs',*paths,'--questions',ws/'compare-questions.json','--facts',ws/'facts.json','--out',root/'comparison')
cli('chunk-report','--run',root/'comparison','--out',root/'report')
with patch.object(llm,'invoke',side_effect=AssertionError('model')),patch.object(embedding,'encode',side_effect=AssertionError('model')):
 chunk_compare.load(root/'comparison')
 for name in ('semantic-ready','llm-ready'):chunk_artifact.replay(ws/name)
cli('candidates','--build',root/'comparison/config-4/build','--result',root/'comparison/config-4/answers/q1','--question-id','q1','--n','20','--out',root/'candidate')
cli('rerank','--candidates',root/'candidate','--method','none','--out',root/'none')
assert read_json(root/'none/result.json')['candidate_execution_kind']=='test_fixture'
from rag_package.ui_server import create_server
s=create_server(ws,[ws/'llm-local.json'],ws/'sources.json',port=0,chunk_configs=[ws/('chunk-'+m+'.json') for m in ('fixed','recursive','structure','semantic','llm')]);assert len(s.ui.bootstrap()['chunk_configs'])==5;s.server_close()
assert not any(k.startswith(('torch','transformers','sentence_transformers')) for k in sys.modules)
print(json.dumps({'status':'PASS','installed_path':str(rag_package.__file__),'sdk_absent':True,'SDK_imports':0,'commands':commands,'fake_boundary_calls':count,'five_way_compare_rows':10,'real_calls':0},ensure_ascii=False,indent=2))
