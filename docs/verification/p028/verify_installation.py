"""Inventory, sdist rebuild and installed-only subprocess verification."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
install=json.loads((OUT/'installation.json').read_text());base=Path(install['base']);dist=ROOT/'.rag-runs/p028-build/dist';allow=json.loads((ROOT/'packaging/allowlist.json').read_text());expected=set(allow['modules']+allow['resources']);commands=[]
def run(args,expected_code=0):
    env={'PATH':'/opt/homebrew/bin:/usr/bin:/bin','HOME':str(base/'isolated-home'),'TMPDIR':str(base),'PYTHONNOUSERSITE':'1'}
    p=subprocess.run([str(x) for x in args],cwd=base,env=env,text=True,capture_output=True)
    commands.append({'args':[str(x) for x in args],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    (OUT/'installed-commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n')
    assert p.returncode==expected_code,(args,p.stdout,p.stderr)
    return p.stdout
wheel=next(dist.glob('*.whl'));sdist=next(dist.glob('*.tar.gz'))
with zipfile.ZipFile(wheel) as z:
    inventory=z.namelist();assert {p for p in inventory if not '.dist-info/' in p}==expected
    assert {p.split('.dist-info/')[1] for p in inventory if '.dist-info/' in p}=={'METADATA','WHEEL','RECORD','entry_points.txt','top_level.txt'}
    metadata=z.read(next(p for p in inventory if p.endswith('/METADATA'))).decode();assert 'License-Expression:' not in metadata
    for p in expected:assert z.read(p)==(ROOT/p).read_bytes()
with tarfile.open(sdist) as t:
    members=t.getmembers();names=[m.name for m in members if m.isfile()];prefix=names[0].split('/')[0]+'/'
    paths={p.removeprefix(prefix) for p in names}
    extras={p for p in paths if p not in expected and p not in allow['sdist_extra']}
    assert extras <= {'PKG-INFO','setup.cfg','milkpotato_rag_lab.egg-info/PKG-INFO','milkpotato_rag_lab.egg-info/SOURCES.txt','milkpotato_rag_lab.egg-info/dependency_links.txt','milkpotato_rag_lab.egg-info/entry_points.txt','milkpotato_rag_lab.egg-info/requires.txt','milkpotato_rag_lab.egg-info/top_level.txt'},extras
    assert expected<=paths
    assert all(not m.issym() and not m.islnk() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
    t.extractall(base/'sdist',filter='data')
run([ROOT/'.rag-runs/p028-build/.venv/bin/python','-m','build','--wheel','--no-isolation','--outdir',base/'rebuilt-dist',base/'sdist'/prefix])
rebuilt=next((base/'rebuilt-dist').glob('*.whl'))
with zipfile.ZipFile(wheel) as a,zipfile.ZipFile(rebuilt) as b:
    assert set(a.namelist())==set(b.namelist())
    assert all(a.read(n)==b.read(n) for n in a.namelist())
run(['uv','--cache-dir',base/'uv-cache','pip','install','--python',base/'rebuilt/bin/python','--reinstall','--no-deps',rebuilt])
shutil.copyfile(OUT/'installed_probe.py',base/'probe.py')
for mode in ('core','extras','rebuilt'):
    py=base/mode/'bin/python';cli=base/mode/'bin/rag-lab'
    assert run([cli,'--version']).strip()=='0.1.0.dev1';assert run([py,'-m','rag_package','--version']).strip()=='0.1.0.dev1'
    run([cli,'--help']);run([py,'-m','rag_package.llm','--help']);run([py,base/'probe.py',mode])
    shutil.copyfile(base/(mode+'-probe.json'),OUT/(mode+'-probe.json'))
(OUT/'artifacts.json').write_text(json.dumps({'status':'PASS','source_commit':'pending_freeze','wheel':{'filename':wheel.name,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'inventory':inventory},'sdist':{'filename':sdist.name,'sha256':hashlib.sha256(sdist.read_bytes()).hexdigest(),'inventory':sorted(paths)},'rebuilt_wheel':{'sha256':hashlib.sha256(rebuilt.read_bytes()).hexdigest(),'same_members_and_bytes':True},'base':str(base),'new_venvs':['core','extras','rebuilt'],'source_free_cwd':True,'pythonpath_unset':True,'actual_other_os_verified':False},indent=2)+'\n')
print('PASS wheel/sdist inventories, independent rebuild and installed core/extras/rebuilt probes')
