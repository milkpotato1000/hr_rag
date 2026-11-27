"""Finish model-free checks after a report filename error; do not rebuild/repeat previews."""
from pathlib import Path
import hashlib,json,os,subprocess,zipfile,tarfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
commands=json.loads((OUT/'commands.json').read_text());BASE=Path(commands[-1]['cwd']);py=BASE/'env/bin/python';work=BASE/'practice'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','LANG':'en_US.UTF-8','PIP_NO_INDEX':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1','PYTHONDONTWRITEBYTECODE':'1'}
code="import sys,unittest; suite=unittest.defaultTestLoader.discover(sys.argv[1],pattern='test_installable.py'); result=unittest.TextTestRunner(verbosity=2).run(suite); assert result.testsRun==3; sys.exit(not result.wasSuccessful())"
p=subprocess.run([str(py),'-I','-c',code,str(BASE)],cwd=BASE,env=env,text=True,capture_output=True)
(OUT/'resource-regression.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
comparison=json.loads((work/'.rag-runs/compare-01/comparison.json').read_text());assert all(r['status']=='preview' and not r['dispatch_attempted'] for r in comparison['rows'])
rows=json.loads((OUT/'preservation.json').read_text());
for name,h in rows['files'].items():assert sha(ROOT/name)==h,name
assert sha(Path(rows['old_experiment_wheel']))==rows['old_wheel_sha256']
wheel=next((BASE/'dist').glob('*.whl'));sdist=next((BASE/'dist').glob('*.tar.gz'))
with zipfile.ZipFile(wheel) as z:
    names=z.namelist();payload={n:hashlib.sha256(z.read(n)).hexdigest() for n in names if '.dist-info/' not in n}
    for name,h in payload.items():assert sha(ROOT/name)==h
with tarfile.open(sdist) as t:paths=[m.name.split('/',1)[1] for m in t.getmembers() if m.isfile()]
installed=json.loads(next(c['stdout'] for c in commands if any('import rag_package,importlib.metadata,json' in str(a) for a in c['args'])))
save('installation.json',{'status':'PASS','adoption':'9be41de90ec370d67db4e2af4bf70e5636d5c2bf','source_head_at_build':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_changes':'S2c START_HERE/manifest payload hashes below; delivery source commit recorded in final-checks.json','base':str(BASE),'python':str(py),'wheel':str(wheel),'wheel_sha256':sha(wheel),'sdist':str(sdist),'sdist_sha256':sha(sdist),'wheel_inventory':names,'wheel_payload_hashes':payload,'sdist_inventory':paths,'installed':installed,'source_free_cwd':str(work),'PYTHONPATH':'unset','isolated_python':True,'no_network_worker_key_guard':True,'preview_rows':len(comparison['rows']),'resource_tests':3,'preserved_files':len(rows['files']),'model_calls':0,'network_calls':0,'key_reads':0,'existing_environment_modified':False,'old_wheel_preserved':True,'resource_sha256':sha(ROOT/'rag_package/resources/manifest.json'),'report_failure':'verify001 failed after successful CLI commands by reading summary.json instead of comparison.json; original preserved, no previews repeated','test_correction':'initial direct test file execution defined tests only; explicit unittest discovery ran 3 tests in source-free installed environment'})
print('PASS installed previews, 3 actual resource tests, preservation')
