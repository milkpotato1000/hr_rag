"""Shared model-free identity helpers for the frozen S2b runner."""
from pathlib import Path
import hashlib,json,importlib.util,sys
E=Path(__file__).resolve().parent;ROOT=E.parents[2];S1=E.parent/'p032-s1';S2A=E.parent/'p032-s2a';RUN=E/'run001'
def module(name):
    spec=importlib.util.spec_from_file_location('s2b_'+name,E/(name+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def hashes(root):return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
def read(path):return json.loads(Path(path).read_text())
def write(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def check_frozen(manifest):
    from rag_package.storage import require
    for group,root in [('S1',S1),('S2a',S2A),('input',RUN/'input')]:
        require(hashes(root)==manifest['files'][group],'s2b_'+group+'_changed','s2b')
    for name,h in manifest['files']['protected'].items():require(sha(ROOT/name)==h,'s2b_preservation_changed','s2b')
    for name,h in manifest['files']['scripts'].items():require(sha(E/name)==h,'s2b_script_changed','s2b')

PARENT=E.parent/'p032-s2b'
def check_parent(root,expected):
    from rag_package.storage import require
    require(hashes(root)==expected,'recovery_parent_files_changed','s2b')
def check_recovery():
    from rag_package.storage import require
    p=read(E/'preservation.json');check_parent(PARENT,p['parent_files'])
    parent=read(PARENT/'run001/ledger.json')
    require(parent['status']=='halted' and parent['reserved_workers']==1 and parent['reserved_items']==567 and parent['operations'][0]['completed_items'] is None,'recovery_parent_state','s2b')
    require(parent['started_at']==1795804963.61378 and parent['deadline']==1795808563.61378,'recovery_parent_clock','s2b')
    preparation=read(E/'environment-ready.json');require(preparation['status']=='PASS','recovery_environment_not_ready','s2b')
