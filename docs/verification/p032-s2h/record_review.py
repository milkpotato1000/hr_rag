"""Bind a manual content review to the normalized answer and verify PDF citations."""
import sys
from pypdf import PdfReader
from runtime import *

def record(q, verdicts, passed, conclusion, notes):
    target=E/(q+'-review.json')
    need(not target.exists(),'review_already_recorded')
    path=E/'answers'/q/'result.json'
    r=read(path)
    claims=read(E.parent/'p032-s1/input/claims-mapping.json')
    ids=[c['claim_id'] for c in claims if c['question_id']==q and c['role']=='required']
    need(len(ids)==len(verdicts),'incomplete_review')
    pdf=PdfReader(ROOT/read(ROOT/'docs/planning/reviews/p032-s2d-input-audit.json')['source_pdf'])
    for citation in (r['answer'] or {}).get('citations',[]):
        pages=''.join(pdf.pages[x['page']-1].extract_text() for x in citation['pages'])
        need(''.join(citation['quote'].split()) in ''.join(pages.split()),'pdf_citation_mismatch')
    write(target,dict(question_id=q,reviewer='dev Codex source comparison',result_sha256=sha(path),
         passed=passed,technical_pass=r['status'] in ('answered','abstained'),fact_verdicts=dict(zip(ids,verdicts)),
         conclusion=conclusion,notes=notes))
    if q in ORDER[:2] and not passed:
        with transact(LEDGER) as c:c.halt(q+'_content_review_failed')
        LEDGER.with_suffix('.halted').touch()
