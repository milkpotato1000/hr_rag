"""Freeze the first production preflight window from the complete S2a snapshot."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import *
from rag_package import chunk_artifact
from rag_package.llm.core import hash_json
verify_parent()
installation=read(E/'installation.json')
need(sys.executable==installation['python'],'wrong_interpreter')
pkg=Path(chunk_artifact.__file__).parent.parent
installed={str(pkg/name):h for name,h in installation['wheel_payload_hashes'].items()}
for name,h in installed.items():need(sha(Path(name))==h,'installed_bytes_changed')
need(sha(Path(installation['wheel']))==installation['wheel_sha256'],'wheel_changed')
parent=E.parent/'p032-s2a/run001/previews/llm-local'
snapshot=parent/'snapshot'
sm,docs,c,model,cfg,units,records=chunk_artifact.preflight(snapshot,E/'config.json')
old=read(parent/'preview.json')
need(sm['fingerprint']==old['source_fingerprint'] and units==old['units'],'source_unit_mismatch')
need(len(records)==len(old['requests'])==34,'window_count')
w=records[0];prior=old['requests'][0]
for key in ('window_id','unit_ids'):
    need(w[key]==prior[key],'window_mismatch')
previous=read(E.parent/'p032-s2i/window.json')
import copy
expected=copy.deepcopy(previous['request']['body'])
content=expected['messages'][1]['content']
data=json.loads(content)
for n,u in enumerate(data['units'],1):u['id']=str(n)
expected['messages'][1]['content']=json.dumps(data,ensure_ascii=False,separators=(',',':'))
need(expected==w['request']['body'],'non_id_request_diff')
write(E/'input-diff.json',{'previous_bytes':len(content.encode()),'current_bytes':len(expected['messages'][1]['content'].encode()),'changed_fields':['user.units[*].id']})
batch=units[:len(w['unit_ids'])]
need([u['id'] for u in batch]==w['unit_ids'],'ordered_ids')
text=docs[0]['text']
for u in batch:need(text[u['start']:u['end']]==u['text'],'source_slice')
window={'id':w['window_id'],'units':batch,'messages':w['messages'],'request':w['request'],'source_fingerprint':sm['fingerprint'],'source_text':text[batch[0]['start']:batch[-1]['end']]}
write(E/'window.json',window)
paths=list(snapshot.rglob('*'))+[parent/'preview.json',E/'window.json',E/'config.json',E/'parent-hashes.json']
files={str(p.relative_to(ROOT)):sha(p) for p in paths if p.is_file()}
write(E/'frozen.json',dict(python=sys.executable,wheel=installation['wheel'],wheel_sha256=installation['wheel_sha256'],installed_files=installed,profile_sha256=sha(E/'profile.json'),input_files=files,scripts={p.name:sha(p) for p in E.glob('*.py')},rows=[dict(question_id='w000',body_hash=hash_json(w['request']['body']),actual_messages_hash=w['request']['actual_messages_hash'])],windows=34,eligible_windows=1))
