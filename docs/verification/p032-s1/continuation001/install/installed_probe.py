"""Source-free core-only CLI contract, no SDK or external endpoints."""
from pathlib import Path
import json,subprocess,sys,importlib.util
import rag_package
root=Path.cwd();assert 'site-packages' in str(rag_package.__file__);assert importlib.util.find_spec('sentence_transformers') is None
commands=[]
def cli(*args,code=0):
    p=subprocess.run([sys.executable,'-m','rag_package',*map(str,args)],capture_output=True,text=True)
    commands.append({'args':list(map(str,args)),'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr});assert p.returncode==code,(args,p.stdout,p.stderr)
    return json.loads(p.stdout)
cli('init','--out','workspace');ws=root/'workspace'
c=cli('model-catalog');assert len(c['models'])==4
for i,m in enumerate(c['models']):
    cli('model-plan','--model',m['model_id'],'--role',m['role'],'--out',ws/('plan-'+str(i)))
    r=cli('model-prepare','--plan',ws/('plan-'+str(i)),'--out',ws/('prepared-'+str(i)));assert r['status']=='preview' and not (ws/('prepared-'+str(i))).exists()
for name in ('local','api','mixed'):
    cli('llm-configure','--spec',ws/('llm-spec-'+name+'.json'),'--out',ws/('generated-'+name+'.json'))
    r=cli('doctor','--llm-config',ws/('generated-'+name+'.json'),code=3);assert r['secrets_read']==0 and r['network_requests']==0
    assert r['optional_dependencies']['preparation']['status']=='missing'
cli('doctor','--config',ws/'fixed.json','--embedding-config',ws/'embedding-e5.json','--reranker-config',ws/'reranker-bge.json','--chunk-config',ws/'chunk-semantic.json',code=3)
cli('snapshot','--sources',ws/'sources.json','--out',ws/'snapshot')
cli('build','--snapshot',ws/'snapshot','--config',ws/'fixed.json','--out',ws/'build')
cli('ask','--run',ws/'build','--config',ws/'fixed.json','--question','생일 휴가 자격?','--out',ws/'answer')
print(json.dumps({'status':'PASS','kind':'source_free_core_only','sdk_missing':True,'commands':commands,'network_calls':0,'secrets_read':0,'model_calls':0},ensure_ascii=False,indent=2))
