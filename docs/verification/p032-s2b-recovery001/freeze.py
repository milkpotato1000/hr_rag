"""Freeze model-free preflight evidence before the first actual S2b call."""
from pathlib import Path
import importlib.util,sys,shutil
spec=importlib.util.spec_from_file_location('runtime',Path(__file__).with_name('runtime.py'));rt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt)
ctl=rt.module('control')
import rag_package
from rag_package import embedding,chunk_artifact,chunk_policy
from rag_package.reranker import SDK_VERSIONS
from rag_package.documents import load_snapshot
from rag_package.storage import fingerprint
E,R=rt.E,rt.RUN
assert not R.exists();R.mkdir();I=R/'input';I.mkdir()
assert sys.flags.isolated and 'site-packages' in str(Path(rag_package.__file__)) and Path(rag_package.__file__).is_relative_to(Path(sys.prefix)) and not (Path.cwd()/'rag_package').exists()
installation=rt.read(E/'environment-ready.json');assert installation['status']=='PASS'
rt.check_recovery()
assert rt.sha(installation['wheel'])==installation['wheel_sha256']
assert embedding.versions()==SDK_VERSIONS
shutil.copytree(rt.S2A/'run001/snapshot',I/'snapshot')
for m in ctl.METHODS[:3]:shutil.copytree(rt.S2A/'run001/chunks'/m,I/'chunks'/m)
for name in ('questions.json','facts.json'):shutil.copyfile(rt.S1/'input'/name,I/name)
shutil.copyfile(rt.S2A/'run001/configs/llm-local-example.json',I/'llm.json')
p=embedding.read_profile(rt.S1/'run001/profiles/e5.json');embedding.check_files(p);rt.write(I/'e5.json',p)
sem={'schema_version':1,'method':'semantic','size_chars':256,'overlap_chars':64,'unit_max_chars':120,'minimum_chars':120,'distance_threshold':0.35,'embedding_config':'e5.json'}
rt.write(I/'semantic.json',sem)
for m in ctl.METHODS:
    target=R/'semantic' if m=='semantic' else I/'chunks'/m
    rt.write(I/'configs'/(m+'.json'),{'schema_version':3,'chunk_artifact':str(target),'retrieval':{'method':'hybrid','candidate_k':20,'rrf_k':60,'top_k':5,'context_budget_chars':2000},'embedding_config':str(I/'e5.json'),'llm_config':str(I/'llm.json')})
sm,docs=load_snapshot(I/'snapshot');us=chunk_policy.units(docs,sm['fingerprint'],120)
assert us==rt.read(rt.S2A/'run001/units.json')['units'] and len(us)==567
for m,n in [('fixed',201),('recursive',257),('structure',264)]:assert len(chunk_artifact.load(I/'chunks'/m)[2])==n
rt.write(R/'ledger.json',ctl.initial())
manifest={'schema_version':1,'contract_sha':'f32ab2582d517301b55e3dfcc4676cf945c55d5d','source_fingerprint':sm['fingerprint'],'units_hash':fingerprint(us),'profile':p,'sdk_versions':embedding.versions(),
    'installation':{k:installation[k] for k in ('python','wheel','wheel_sha256','lock','lock_sha256')},'installed_package_path':str(Path(rag_package.__file__).parent),'source_free_cwd':str(Path.cwd()),'python_isolated':sys.flags.isolated,
    'files':{'S1':rt.hashes(rt.S1),'S2a':rt.hashes(rt.S2A),'protected':rt.read(rt.S1/'preservation.json')['files'],'input':rt.hashes(I),'scripts':{p.name:rt.sha(p) for p in E.glob('*.py')}},
    'initial_ledger_hash':rt.sha(R/'ledger.json'),'order':ctl.ORDER,'order_hash':fingerprint(ctl.ORDER),'limits':ctl.initial()['limits'],
    'expected_items':{'semantic_units':567,'fixed_index':201,'recursive_index':257,'structure_index':264,'semantic_index_max':567,'query':40,'total_max':1896},
    'offline_tests':{'file':'tests-final.log','sha256':rt.sha(E/'tests-final.log'),'tests':31,'result':'PASS'},
    'downloads':0,'conversions':0,'S1_budget_clock':'S1 unchanged; original S2b start1795804963.61378/deadline1795808563.61378 inherited','forbidden':['LLM','API','Ollama','Drive','evaluation','reranking','keys','automatic_retry']}
manifest['parent']={'evidence_commit':'8c615d6b560dff766ccd02b172aedef36afb9cd4','halt_commit':'4576841c4a2c56b37430cb39f230536c1c2858b2','workers':1,'requested_items':567,'completed_items':None,'preservation_hash':rt.sha(E/'preservation.json')}
manifest['cumulative_limits']={'workers':46,'requested_items':2463}
manifest['environment_audit_hash']=rt.sha(E/'environment-audit.json')
manifest['environment_ready_hash']=rt.sha(E/'environment-ready.json')
# Enumerate only path changes; actual semantic/search/source/profile payload stays fixed.
parent=rt.read(rt.PARENT/'run001/manifest.json');assert manifest['source_fingerprint']==parent['source_fingerprint'] and manifest['units_hash']==parent['units_hash'] and manifest['profile']==parent['profile'] and manifest['order']==parent['order']
diffs=[]
for name in parent['files']['input']:
 old=rt.PARENT/'run001/input'/name;new=I/name
 if rt.sha(old)!=rt.sha(new):
  assert name.startswith('configs/') and name.endswith('.json'),name
  before=rt.read(old);after=rt.read(new)
  assert {k:v for k,v in before.items() if k not in ('chunk_artifact','embedding_config','llm_config')}=={k:v for k,v in after.items() if k not in ('chunk_artifact','embedding_config','llm_config')}
  for key in ('chunk_artifact','embedding_config','llm_config'):
   assert after[key]==before[key].replace(str(rt.PARENT/'run001'),str(R))
  diffs.append({'file':name,'before':before,'after':after})
manifest['input_path_differences']=diffs;assert len(diffs)==4
rt.write(R/'manifest.json',manifest);rt.check_frozen(manifest)
rt.write(E/'freeze-checks.json',{'status':'PASS','model_instances':0,'model_calls':0,'download_calls':0,'sdk_versions':embedding.versions(),'source':sm['fingerprint'],'S1_files':len(manifest['files']['S1']),'S2a_files':len(manifest['files']['S2a']),'protected_files':len(manifest['files']['protected']),'next':'Commit runner/tests/manifest before actual execution'})
print('PASS frozen; no model calls; commit required')
