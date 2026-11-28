"""Compare the selected PDF to citations and reopen the saved run with no model."""
from experiment import E,ws,base,python,out,reference,read,write,rt,audit,pdf
import json,os,sys,subprocess
if sys.executable!=str(python):
    os.execv(python,[str(python),__file__])
from pypdf import PdfReader
from rag_package.storage import verify
cli=python.parent/'rag-lab'
def replay(path):
    return json.loads(subprocess.check_output([cli,'pipeline-replay','--run',path],cwd=ws,text=True))
def sha(path):return rt.sha(path)
result=read(out/'answer/result.json')
report=replay(out)
assert report==read(out/'pipeline.json') and report['question']==reference['question']
assert report['answer']==result['answer'] and result['preview']['body']==audit()
assert result['contexts'][0]['text']==reference['text']
expected_id=reference['selected']['selected_document']['document_id']
snapshot=out/'snapshot'/expected_id
assert sha(pdf)==sha(snapshot/'original.pdf')==sha(ws/'내 문서 실습/original.pdf')
assert sha(pdf)!=sha(ws/'documents/handbook.pdf')
reader=PdfReader(pdf)
assert len(reader.pages)==1 and reference['quote'] in reader.pages[0].extract_text()
page=(snapshot/'page-1.txt').read_text()
assert page==reference['text']
answer=result['answer']
for cite in (answer or {}).get('citations',[]):
    assert cite['document_id']==expected_id and cite['source_fingerprint']==reference['selected_source_fingerprint']
    assert [p['page'] for p in cite['pages']]==[1] and cite['quote']==page[cite['start']:cite['end']]
    assert reference['quote'] in cite['quote']
first=base/'rag-lab-first/practice'
verify(first/'first-answer/answer','answer')
default=read(first/'first-answer/answer/result.json')
assert default['status']=='answered' and default['source_fingerprint']==reference['default_source_fingerprint']
ledger=read(E/'ledger.json')
assert len(ledger['requests'])==1 and ledger['automatic_retries']==0 and read(E/'server-closed.json')['listener_closed']
write(E/'review.json',dict(question=report['question'],technical_status=result['status'],answer=answer,
    expected_identifier='HR-V3-TRAINING',expected_version=3,source_quote=reference['quote'],
    selected_pdf_sha256=sha(pdf),source_fingerprint=result['source_fingerprint'],default_pdf_sha256=sha(first/'documents/handbook.pdf'),
    context_count=len(result['contexts']),model_identity=result['provider_result']['identity_verification'],
    generation_requests=result['generation_requests'],additional_replay_calls=0,default_answer_preserved=True))
