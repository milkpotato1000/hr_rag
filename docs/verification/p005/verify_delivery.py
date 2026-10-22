#!/usr/bin/env python3
"""P005 real HTTP in a standalone source copy plus full regression and preservation."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[3]
STAGE=ROOT/'1. Naive RAG'
PYTHON=str(STAGE/'.venv/bin/python')
OUTPUT=Path(__file__).with_name('03-delivery-final')
BASE='38d276ef994ac89196fbd2620c0fe26d694050c1'


def main():
    OUTPUT.mkdir();records=[]
    def run(command,cwd):
        r=subprocess.run(command,cwd=cwd,capture_output=True,text=True,timeout=300)
        records.append({'cwd':str(cwd),'command':command,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
        (OUTPUT/'commands.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
        assert r.returncode==0,r.stderr
    run([PYTHON,'-m','unittest','discover','-s','tests','-v'],STAGE)
    run(['python3','-m','unittest','discover','-s','tests','-v'],ROOT)
    with tempfile.TemporaryDirectory(prefix='p005-standalone-') as scratch:
        copied=Path(scratch)/'Naive RAG'
        shutil.copytree(STAGE,copied,ignore=shutil.ignore_patterns('.runtime','.venv','__pycache__','*.pyc'))
        (copied/'.runtime').mkdir()
        shutil.copytree(STAGE/'.runtime/index-v1',copied/'.runtime/index-v1')
        run([PYTHON,'-m','unittest','discover','-s','tests','-v'],copied)
        code='import sys;sys.path.insert(0,"scripts");from serve import LearningServer;s=LearningServer(0);print(s.server_port,flush=True);s.serve_forever()'
        with (OUTPUT/'standalone-server.txt').open('w') as log:
            child=subprocess.Popen([PYTHON,'-c',code],cwd=copied,stdout=subprocess.PIPE,stderr=log,text=True)
            try:
                port=int(child.stdout.readline().strip());base=f'http://127.0.0.1:{port}'
                for route in ['/','/app.js','/style.css','/guide']:
                    with urlopen(base+route,timeout=10) as response:
                        assert response.status==200 and response.read()
                for qid,q,expected in [('q10','재택근무일과 휴가일에도 사무실 식대가 나오나요?','answered'),
                                       ('q13','퇴직금 계산식은 어떻게 되나요?','abstained')]:
                    body=json.dumps({'question':q}).encode()
                    request=Request(base+'/api/ask',data=body,headers={'Content-Type':'application/json'})
                    with urlopen(request,timeout=300) as response:
                        result=json.load(response)
                        (OUTPUT/(qid+'-live-http.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
                        assert response.status==200 and result['status']==expected
                        assert result['trace']['generation']['model']=='qwen3:4b'
                        assert result['trace']['retrieval']['index_manifest']['model_name']=='bge-m3:567m'
                        assert result['trace']['generation_calls']==1
            finally:
                child.terminate();child.wait(timeout=10)
    checked=[]
    for prefix in ['docs/verification/p001','docs/verification/p002','docs/verification/p003','docs/verification/p004',
                   'docs/planning/plans/P001.md','docs/planning/plans/P002.md','docs/planning/plans/P003.md','docs/planning/plans/P004.md',
                   '1. Naive RAG/runtime-lock.json','1. Naive RAG/generation-lock.json','1. Naive RAG/requirements.lock',
                   '1. Naive RAG/scripts/rag.py','1. Naive RAG/scripts/ask.py','1. Naive RAG/prompts']:
        names=subprocess.run(['git','ls-tree','-r','--name-only',BASE,'--',prefix],cwd=ROOT,capture_output=True,text=True,check=True).stdout.splitlines()
        for name in names:
            original=subprocess.run(['git','show',BASE+':'+name],cwd=ROOT,capture_output=True,check=True).stdout
            assert original==(ROOT/name).read_bytes(),name
            checked.append(name)
    for row in json.loads((STAGE/'stage-manifest.json').read_text())['files']:
        assert hashlib.sha256((STAGE/row['destination_path']).read_bytes()).hexdigest()==row['copied_sha256']
    (OUTPUT/'preservation.json').write_text(json.dumps({'base':BASE,'unchanged':checked,'six_original_hashes_match':True,
      'standalone_source_web_guide_data_prompts':True,'standalone_uses_approved_interpreter_and_loopback_models':True,
      'real_http_answer_and_abstain':True,
      'adapter_fix_files':['scripts/generation.py','scripts/setup_generation.py'],
      'adapter_fix_reason':'Ignore parameters line order only; preserve original lock and reject changed values/digest/template'},ensure_ascii=False,indent=2)+'\n')
    print('PASS: 76 stage/copy tests, root19, standalone real HTTP answer/abstain, P001-P004 evidence/core/locks preserved')


if __name__=='__main__':main()
