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
assert sys.flags.isolated and 'site-packages' in str(Path(rag_package.__file__)) and not Path(rag_package.__file__).is_relative_to(rt.ROOT)
installation=rt.read(rt.S1/'continuation001/install/installation.json')
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
manifest={'schema_version':1,'contract_sha':'f12d52c99b78bfc83352c9b3e038cf08865f6d28','source_fingerprint':sm['fingerprint'],'units_hash':fingerprint(us),'profile':p,'sdk_versions':embedding.versions(),
    'installation':{k:installation[k] for k in ('python','wheel','wheel_sha256','sdist_sha256')},'installed_package_path':str(Path(rag_package.__file__).parent),'source_free_cwd':str(Path.cwd()),'python_isolated':sys.flags.isolated,
    'files':{'S1':rt.hashes(rt.S1),'S2a':rt.hashes(rt.S2A),'protected':rt.read(rt.S1/'preservation.json')['files'],'input':rt.hashes(I),'scripts':{p.name:rt.sha(p) for p in E.glob('*.py')}},
    'initial_ledger_hash':rt.sha(R/'ledger.json'),'order':ctl.ORDER,'order_hash':fingerprint(ctl.ORDER),'limits':ctl.initial()['limits'],
    'expected_items':{'semantic_units':567,'fixed_index':201,'recursive_index':257,'structure_index':264,'semantic_index_max':567,'query':40,'total_max':1896},
    'offline_tests':{'file':'tests-final.log','sha256':rt.sha(E/'tests-final.log'),'tests':18,'result':'PASS'},
    'downloads':0,'conversions':0,'S1_budget_clock':'unchanged; separate one-shot S2b clock starts at first worker reservation','forbidden':['LLM','API','Ollama','Drive','evaluation','reranking','keys','automatic_retry']}
rt.write(R/'manifest.json',manifest);rt.check_frozen(manifest)
rt.write(E/'freeze-checks.json',{'status':'PASS','model_instances':0,'model_calls':0,'download_calls':0,'sdk_versions':embedding.versions(),'source':sm['fingerprint'],'S1_files':len(manifest['files']['S1']),'S2a_files':len(manifest['files']['S2a']),'protected_files':len(manifest['files']['protected']),'next':'Commit runner/tests/manifest before actual execution'})
print('PASS frozen; no model calls; commit required')
