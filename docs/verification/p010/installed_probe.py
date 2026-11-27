"""Installed wheel probe. Run in a copied stage without checkout on sys.path."""
from pathlib import Path
import contextlib,io,json,socket,os,sys
import rag_package
from rag_package.__main__ import main
from rag_package.storage import read_json,write_json
base=Path.cwd();assert 'site-packages' in rag_package.__file__;assert 'PYTHONPATH' not in os.environ;assert not any('/hr_rag_dev' in x for x in sys.path)
def forbidden(*a,**k):raise AssertionError('network forbidden')
socket.socket.connect=forbidden;socket.getaddrinfo=forbidden
calls=[]
def call(args,code=0):
 f=io.StringIO()
 with contextlib.redirect_stdout(f):got=main(args)
 calls.append({'args':args,'exit_code':got,'stdout':f.getvalue()});assert got==code,(args,got,f.getvalue())
call(['snapshot','--sources','stage/sources.json','--out','stage/.rag-runs/snapshot'])
call(['retrieval-preview','--config','stage/e5-hybrid.json'])
call(['build','--snapshot','stage/.rag-runs/snapshot','--config','stage/e5-hybrid.json','--out','stage/.rag-runs/disallowed'],2)
call(['build','--snapshot','stage/.rag-runs/snapshot','--config','stage/bm25.json','--out','stage/.rag-runs/bm25'])
call(['ask','--run','stage/.rag-runs/bm25','--config','stage/bm25.json','--question','생일 휴가','--out','stage/.rag-runs/bm25-answer'])
# Locally-generated random model copied by harness, not pretrained E5.
p=read_json('tiny-profile.json');p['local_path']=str(base/'tiny-model');write_json('stage/e5-embedding.json',p)
call(['build','--snapshot','stage/.rag-runs/snapshot','--config','stage/e5-hybrid.json','--out','stage/.rag-runs/hybrid','--execute-retrieval'])
call(['ask','--run','stage/.rag-runs/hybrid','--config','stage/e5-hybrid.json','--question','birthday leave','--out','stage/.rag-runs/hybrid-answer','--execute-retrieval'])
r=read_json('stage/.rag-runs/hybrid-answer/result.json');assert r['embedding_work']['queries']==1 and not r['dispatch_attempted'];assert r['retrieval_trace']['dense']
Path('installed-probe.json').write_text(json.dumps({'status':'PASS','label':'tiny_random_local_SDK_not_pretrained_quality','installed_import':rag_package.__file__,'network_calls':0,'pretrained_models_loaded':0,'generation_calls':0,'calls':calls},ensure_ascii=False,indent=2)+'\n');print('installed stage/SDK PASS')
