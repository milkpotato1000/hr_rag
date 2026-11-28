"""Create an isolated source-free workspace and freeze the exact one-shot run."""
from pathlib import Path
import importlib.metadata as md,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import *
import rag_package
from rag_package import embedding,reranker
inst=read(E/'installation.json')
base=Path(inst['base'])
ws=base/'practice'
cli=base/'env/bin/rag-lab'
need(sys.executable==inst['python'] and Path(rag_package.__file__).is_relative_to(base/'env'),'installation')
source=ROOT/'.rag-runs/p032-s1-live/run001'
ep=source/'e5/prepared/profile.json'
rp=source/'mmini/prepared/profile.json'
for mod,path in ((embedding,ep),(reranker,rp)):
    profile=mod.read_profile(path)
    mod.check_files(profile)
    need(profile['device']=='cpu' and profile['batch_size']==1 and profile['timeout_seconds']<=300,'worker_settings')
lock=ROOT/'rag_package/requirements-retrieval.lock'
for name,version in re.findall(r'^([\w.-]+)==([^\s\\]+)',lock.read_text(),re.M):
    need(md.version(name)==version,name)
need(md.version('pypdf')=='6.21.2','pdf')
os.chdir(base)
subprocess.run([cli,'init','--out','practice'],check=True,stdout=subprocess.DEVNULL)
os.chdir(ws)
audit=read(ROOT/'docs/planning/reviews/p032-s2d-input-audit.json')
pdf=ws/'documents/handbook.pdf'
shutil.copyfile(ROOT/audit['source_pdf'],pdf)
need(sha(pdf)==audit['source_pdf_sha256'],'pdf_changed')
for path in (E/'profile.json',ws/'handbook-model.json'):
    shutil.copyfile(E.parent/'p032-s5/profile.json',path)
cfg=read(ws/'rag-hybrid.json')
cfg.update(llm_config='handbook-model.json',embedding_config=str(ep))
write(ws/'pipeline-search.json',cfg)
question='생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
args=['pipeline','--sources','handbook-sources.json','--chunk-config','chunk-handbook.json','--search-config','pipeline-search.json','--reranker-profile',str(rp),'--question',question]
preview=json.loads(subprocess.check_output([cli,*args,'--out','.rag-runs/pipeline-plan'],text=True))
need(preview['status']=='preview' and preview['generation_requests']==0,'preview')
write(E/'preview.json',preview)
inputs=[pdf,ep,rp,lock,*(ws/n for n in ('handbook-model.json','handbook-sources.json','pipeline-search.json','chunk-handbook.json')),ROOT/'docs/verification/p032-s1/live_control.py']
parent={str(p):sha(p) for name in ('p032-s5','p032-s7') for p in (E.parent/name).iterdir() if p.is_file()}
write(E/'parent-hashes.json',parent)
site=Path(rag_package.__file__).parent.parent
write(E/'frozen.json',dict(python=sys.executable,practice=str(ws),wheel=inst['wheel'],wheel_sha256=inst['wheel_sha256'],installed_files={str(site/n):h for n,h in inst['wheel_payload_hashes'].items()},input_files={str(p):sha(p) for p in inputs},profile_sha256=sha(E/'profile.json'),scripts={p.name:sha(p) for p in E.glob('*.py')},rows=[dict(question_id='first',question=question)],cli_args=args))
verify_parent()
