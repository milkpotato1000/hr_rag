"""Verify an explicit file, the default handbook and all printed CLI arguments."""
from pathlib import Path
import hashlib
import json
import shlex
import shutil
import subprocess

E=Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text())
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
base=Path(read(E/'installation.json')['base'])
ws=base/'practice'
env={'PATH':str(base/'env/bin')+':/usr/bin:/bin','LANG':'en_US.UTF-8','PYTHONDONTWRITEBYTECODE':'1','PIP_NO_INDEX':'1'}
site=Path('env/lib/python3.12/site-packages')
old=Path(read(E.parent/'p032-s7/installation.json')['base'])
for name in ('pypdf','pypdf-6.21.2.dist-info'):
    shutil.copytree(old/site/name,base/site/name)
def run(args,cwd=ws,ok=True):
    p=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=30)
    assert (p.returncode==0)==ok,(args,p.stdout,p.stderr)
    return json.loads(p.stdout)
run(['rag-lab','init','--out','practice'],cwd=base)
run(['rag-lab','generation-setup','--provider','ollama','--model','qwen3:4b','--out','my-model'])
original=E.parents[2]/'2. Document Chunking/data/source-v3/output/pdf/training.pdf'
source=base/"입력 파일/교육 휴가's 규정.pdf"
source.parent.mkdir()
shutil.copyfile(original,source)
q='교육 휴가 규정의 문서 식별자와 버전은 무엇인가요?'
title='자격시험 교육 휴가 규정'
quote='문서 식별자: HR-V3-TRAINING | 버전: 3 | 시행일: 정보 없음'
folder='내 문서 실습'
setup=['rag-lab','pipeline-setup','--llm-config','my-model/model.json','--chunk-config','chunk-fixed.json','--method','bm25']
handbook=ws/'documents/handbook.pdf'
inputs=[source,original,handbook,ws/'handbook-sources.json',ws/'my-model/model.json']
before=[sha(p) for p in inputs]
selected=run(setup+['--document',str(source),'--title',title,'--question',q,'--synthetic','--out',folder])
info=selected['selected_document']
assert info['original_name']==source.name and info['original_sha256']==sha(source)==sha(ws/folder/info['path'])
assert info['synthetic'] is True and info['title']==title
preview=run(shlex.split(selected['commands']['pipeline_preview']))
default=run(setup+['--out','기본 실습'])
standard=run(shlex.split(default['commands']['pipeline_preview']))
assert preview['plan']['source_fingerprint']!=standard['plan']['source_fingerprint']
assert preview['question']==q and '생일 특별휴가' in standard['question']
assert preview['plan']['retrieval']==standard['plan']['retrieval'] and preview['plan']['generation']==standard['plan']['generation']
assert preview['generation_requests']==standard['generation_requests']==0
snap=ws/(folder+'-preview')/'snapshot'
page=(snap/info['document_id']/'page-1.txt').read_text()
default_text=(ws/'기본 실습-preview/snapshot/handbook/canonical.txt').read_text()
assert quote in page and 'HR-V3-TRAINING' not in default_text
run(['rag-lab','build','--snapshot',str(snap),'--config',folder+'/search.json','--out','bm25'])
run(['rag-lab','ask','--run','bm25','--config',folder+'/search.json','--question',q,'--out','bm25-preview'])
evidence=read(ws/'bm25-preview/result.json')
assert evidence['status']=='preview' and not evidence['dispatch_attempted']
c=evidence['contexts'][0]
assert c['text']==page[c['start']:c['end']] and quote in c['text'] and c['pages'][0]['page']==1
for ext in ('txt','md'):
    text=base/('문서.'+ext);text.write_text('합성 신청 코드 W-12')
    r=run(setup+['--out',ext,'--document',str(text),'--question','신청 코드는?'])
    assert r['selected_document']['synthetic'] is False and r['selected_document']['title']==text.name
    assert run(shlex.split(r['commands']['pipeline_preview']))['status']=='preview'
badfile=base/'지원 안 함.docx';badfile.write_bytes(b'fixture')
for args,code in [(['--document','missing.pdf','--question',q],'source_unreadable'),
                  (['--document',str(badfile),'--question',q],'unsupported_source'),
                  (['--document',str(source)],'question_required')]:
    assert run(setup+args+['--out','invalid'],ok=False)['error']['code']==code
    assert not (ws/'invalid').exists()
assert run(setup+['--document',str(source),'--question',q,'--out',folder],ok=False)['error']['code']=='output_exists'
assert before==[sha(p) for p in inputs]
verified=dict(selected=selected,default_pdf_sha256=sha(handbook),default_source_fingerprint=standard['plan']['source_fingerprint'],
              selected_source_fingerprint=preview['plan']['source_fingerprint'],question=q,quote=quote,
              page=c['pages'][0]['page'],rank=1,text=c['text'],primary_inputs_preserved=True,inference_calls=0)
(E/'verified.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2)+'\n')
print('PASS source SHA, distinct snapshots, unique evidence, preservation, TXT/MD and rejected inputs')
