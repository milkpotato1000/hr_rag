"""Create the actual user profile through installed CLI after server identity checks."""
from runtime import *
f=read(E/'frozen.json');ws=Path(f['practice'])
cli=Path(f['python']).parent/'rag-lab'
env={'PATH':str(cli.parent)+':/usr/bin:/bin','LANG':'en_US.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
need(read(E/'preflight.json')['status']=='PASS','preflight_missing')
need(listener()==read(E/'server-ownership.json')['pid'],'server_changed')
args=['llm-configure','--spec','handbook-qwen-spec.json','--out','handbook-model.json','--inspect-local']
r=subprocess.run([str(cli),*args],cwd=ws,env=env,capture_output=True,text=True)
write(E/'live-configure.json',{'args':args,'code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
need(r.returncode==0,'installed_configure_failed')
need(read(ws/'handbook-model.json')==read(E/'profile.json'),'profile_diff')
for args in (['doctor','--llm-config','handbook-model.json'],['ask','--run','.rag-runs/bm25','--config','handbook-local.json','--question',f['rows'][0]['question'],'--out','.rag-runs/live-preview']):
    subprocess.run([str(cli),*args],cwd=ws,env=env,check=True)
live=read(ws/'.rag-runs/live-preview/result.json')
need(not live['dispatch_attempted'] and live['actual_messages_hash']==f['rows'][0]['actual_messages_hash'],'live_preview_changed')
