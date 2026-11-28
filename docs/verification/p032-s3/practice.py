"""Run the installed tutorial from a new, source-free practice folder."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import *
from rag_package.llm.core import hash_json
import rag_package
from importlib.metadata import version

installation=read(E/'installation.json')
need(sys.executable==installation['python'],'wrong_python')
base=Path(installation['base']);ws=base/'handbook-practice';cli=base/'env/bin/rag-lab'
env={'PATH':str(cli.parent)+':/usr/bin:/bin:/usr/sbin:/sbin','LANG':'en_US.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
commands=[]
def run(args,cwd=ws,codes=(0,)):
    result=subprocess.run([str(cli),*args],cwd=cwd,env=env,text=True,capture_output=True)
    commands.append(dict(args=args,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
    write(E/'practice-commands.json',commands)
    need(result.returncode in codes,'tutorial_step_'+args[0])
    return json.loads(result.stdout)
verify_parent()
need(version('pypdf')=='6.21.2','pdf_dependency')
question='생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
run(['init','--out','handbook-practice'],base)
run(['doctor'])
audit=read(ROOT/'docs/planning/reviews/p032-s2d-input-audit.json');pdf=ROOT/audit['source_pdf']
need(sha(pdf)==audit['source_pdf_sha256'],'pdf_changed')
shutil.copyfile(pdf,ws/'documents/handbook.pdf')
run(['snapshot','--sources','handbook-sources.json','--out','.rag-runs/pdf'])
run(['build','--snapshot','.rag-runs/pdf','--config','fixed.json','--out','.rag-runs/bm25'])
run(['ask','--run','.rag-runs/bm25','--config','fixed.json','--question',question,'--out','.rag-runs/preview'])
r=read(ws/'.rag-runs/preview/result.json');need(r['status']=='preview' and not r['dispatch_attempted'],'preview')
write(E/'search-preview.json',{'question':question,'contexts':r['contexts'],'candidates':r['candidates']})
api=run(['llm-configure','--spec','llm-spec-api.json','--out','handbook-api.json'])
need(api['http_requests']==api['secrets_read']==0,'api_work')
run(['doctor','--llm-config','handbook-api.json'],codes=(0,3))
run(['llm-configure','--spec','handbook-qwen-spec.json','--out','offline-model.json'])
expected=read(ws/'offline-model.json')
identity=expected['profiles']['local']['identity']
identity.update(expected_digest=DIGEST,validation_status='user_configured_unverified')
write(E/'profile.json',expected)
# Preview must match the normal installed configuration once its digest has been inspected.
from rag_package import llm
request=llm.preview(expected,'generation',r['messages'],response_schema=r['preview']['body']['format'])
files={str(p):sha(p) for p in (ws/'.rag-runs/bm25').rglob('*') if p.is_file()}
for name in ('handbook-local.json','handbook-qwen-spec.json','documents/handbook.pdf'):files[str(ws/name)]=sha(ws/name)
installed={str(Path(rag_package.__file__).parent.parent/name):h for name,h in installation['wheel_payload_hashes'].items()}
for name,h in installed.items():need(sha(Path(name))==h,'installed_bytes')
write(E/'frozen.json',dict(python=sys.executable,practice=str(ws),wheel=installation['wheel'],wheel_sha256=installation['wheel_sha256'],installed_files=installed,input_files=files,profile_sha256=sha(E/'profile.json'),scripts={p.name:sha(p) for p in E.glob('*.py')},rows=[dict(question_id='first',question=question,body_hash=hash_json(request['body']),actual_messages_hash=request['actual_messages_hash'])]))
