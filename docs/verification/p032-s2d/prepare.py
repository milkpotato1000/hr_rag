"""Model-free S2d input/installed-byte audit and ten production CLI previews."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import *
import rag_package
from rag_package.llm import core
E.mkdir(exist_ok=True)
installation=read(ROOT/'docs/verification/p032-s2c/installation.json');need(sys.executable==installation['python'],'wrong_python')
need(sha(Path(installation['wheel']))==installation['wheel_sha256'],'wheel_hash')
package=Path(rag_package.__file__).parent;installed={}
for name,h in installation['wheel_payload_hashes'].items():
    p=package.parent/name;need(sha(p)==h,'installed_bytes');installed[str(p)]=h
profile={'schema_version':2,'profiles':{'local4b':{'mode':'local','provider':'ollama','model':'qwen3:4b','base_url':BASE,'max_output_tokens':1024,'timeout_seconds':180,'response_mode':'json_object','temperature':0,'seed':42,'num_ctx':8192,'identity':{'expected_digest':DIGEST,'hf_id':'Qwen/Qwen3-4B-Thinking-2507','conversion':'historical_ollama_import','source_revision':None,'quantization':'Q4_K_M','validation_status':'user_configured_unverified'}}},'roles':{'generation':'local4b','evaluation':'local4b','chunking':'local4b'}}
write(E/'profile.json',profile);audit=read(ROOT/'docs/planning/reviews/p032-s2d-input-audit.json');files={};rows=[];commands=[]
for row in audit['rows']:
    for name,h in row['files'].items():need(sha(ROOT/name)==h,'input_audit_mismatch');files[name]=h
    q=row['question_id'];out=E/'preview'/q
    env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','PYTHONDONTWRITEBYTECODE':'1'}
    p=subprocess.run([sys.executable,'-I','-B','-m','rag_package','answer-from-rerank','--run',str(ROOT/row['run']),'--llm-config',str(E/'profile.json'),'--out',str(out)],env=env,cwd=Path(installation['base']),text=True,capture_output=True)
    commands.append({'question_id':q,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr});write(E/'preview-commands.json',commands);need(p.returncode==0,'preview_failed')
    result=read(out/'result.json');need(result['status']=='preview' and not result['dispatch_attempted'] and result['generation_requests']==0,'preview_dispatched')
    req=result['preview'];data=json.loads(result['messages'][1]['content']);need(set(data)=={'question','contexts'},'prompt_leak');need(sum(len(c['text']) for c in result['contexts'])==1280,'context_length')
    rows.append({'question_id':q,'question':result['question'],'run':row['run'],'body_hash':core.hash_json(req['body']),'messages_hash':result['messages_hash'],'actual_messages_hash':result['actual_messages_hash'],'request_fingerprint':req['request_fingerprint'],'body_bytes':len(json.dumps(req['body'],ensure_ascii=False,allow_nan=False).encode()),'actual_message_chars':sum(len(m['content']) for m in req['body']['messages']),'context_fact_coverage':row['context_fact_coverage'],'exact_input_tokens':'unmeasured'})
need(len(files)==590,'input_count');files[audit['source_pdf']]=audit['source_pdf_sha256'];need(sha(ROOT/audit['source_pdf'])==audit['source_pdf_sha256'],'source_pdf_hash')
scripts={p.name:sha(p) for p in E.glob('*.py')}
write(E/'frozen.json',{'status':'prepared_model0','exact_adoption':'876067dc2f383fdc806d9e6f70031360e05c2c4d','python':sys.executable,'wheel':installation['wheel'],'wheel_sha256':installation['wheel_sha256'],'installed_package':str(package),'installed_files':installed,'profile_sha256':sha(E/'profile.json'),'input_files':files,'scripts':scripts,'rows':rows,'generation_limit':10,'metadata_limit':200,'server_inference_cancel_claim':False,'prompt_includes_GT':False,'runtime_source_unchanged':True})
# Preserve all prior S2c evidence hashes plus the prior protected-set chain.
previous=read(ROOT/'docs/verification/p032-s2c/preservation.json')['files'];
for p in (ROOT/'docs/verification/p032-s2c').rglob('*'):
    if p.is_file():previous[str(p.relative_to(ROOT))]=sha(p)
for name,h in previous.items():need(sha(ROOT/name)==h,'previous_evidence_changed')
write(E/'preservation.json',{'files':previous,'count':len(previous)})
print('PASS: installed payload, 590 input files + PDF, 10 CLI previews, no model/HTTP calls')
