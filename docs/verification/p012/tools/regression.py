import subprocess,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p012';a=root/'1. Naive RAG';b=a/'variants/langchain';rows=[]
for label,stage,folder,expected in [('baseline',a,'tests',107),('candidate',b,'tests',107),('langchain',b,'tests_langchain',32),('learning',b,'tests_learning',11),('root',root,'tests',19),('harness',root,'tests/harness',12)]:
 python=stage/'.venv/bin/python' if stage!=root else a/'.venv/bin/python'
 with (ev/(label+'-tests.log')).open('w') as out:r=subprocess.run([str(python),'-m','unittest','discover','-s',folder],cwd=stage,stdout=out,stderr=subprocess.STDOUT)
 text=(ev/(label+'-tests.log')).read_text();rows.append({'suite':label,'returncode':r.returncode,'expected_tests':expected,'status':'PASS' if r.returncode==0 and f'Ran {expected} tests' in text and text.rstrip().endswith('OK') else 'FAIL'});print(rows[-1],flush=True)
(ev/'regression.json').write_text(json.dumps({'status':'PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL','suites':rows},indent=2)+'\n');assert all(r['status']=='PASS' for r in rows)
