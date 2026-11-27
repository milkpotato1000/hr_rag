"""Copied into source-free cwd; execute with core-only installed wheel."""
from pathlib import Path
import json,sys,subprocess,importlib.util
import rag_package
from rag_package.storage import read_json,write_json
from rag_package import reranking
root=Path.cwd();assert 'site-packages' in str(rag_package.__file__)
assert importlib.util.find_spec('sentence_transformers') is None
commands=[]
def cli(*args):
 p=subprocess.run([sys.executable,'-m','rag_package',*map(str,args)],capture_output=True,text=True)
 commands.append({'args':list(map(str,args)),'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr});assert p.returncode==0,(args,p.stdout,p.stderr)
cli('snapshot','--sources','stage/sources.json','--out','snap')
cli('build','--snapshot','snap','--config','stage/bm25.json','--out','build')
cli('ask','--run','build','--config','stage/bm25.json','--question','생일 휴가 자격은?','--out','answer')
cli('candidates','--build','build','--result','answer','--question-id','q1','--n',20,'--out','candidates')
cli('rerank','--candidates','candidates','--method','none','--top-k',5,'--out','none')
cli('rerank','--candidates','candidates','--method','cross-encoder','--profile','stage/bge-reranker.json','--out','preview')
write_json(root/'set.json',{'schema_version':1,'candidates':[{'question_id':'q1','path':'candidates'}]})
v=read_json(root/'stage/rerank-variants.json')
for row in v['variants']:
 if row['profile']:row['profile']='stage/'+row['profile']
write_json(root/'variants.json',v)
cli('rerank-compare','--candidates-set','set.json','--variants','variants.json','--out','comparison')
cli('rerank-report','--run','comparison','--out','report')
cli('answer-from-rerank','--run','none','--llm-config','stage/llm-local.json','--out','generation')
from rag_package.ui_server import create_server
s=create_server(root/'stage',[root/'stage/llm-local.json'],root/'stage/sources.json',port=0,reranker_configs=[root/'stage/bge-reranker.json']);assert len(s.ui.bootstrap()['reranker_configs'])==1;s.server_close()
assert not any(k.startswith(('torch','transformers','sentence_transformers')) for k in sys.modules)
print(json.dumps({'status':'PASS','installed_path':str(rag_package.__file__),'sdk_absent':True,'SDK_imports':0,'commands':commands,'ui_assets_and_server':'PASS','generation_requests':0},ensure_ascii=False,indent=2))
