"""Build the offline comparison from normalized results, frozen evidence and Codex review."""
from html import escape
from pathlib import Path
import json
from urllib.parse import quote
import os

folder = Path(__file__).resolve().parent
root = folder.parents[2]
def read(path):
    return json.loads(path.read_text())
def esc(value):
    return escape(str(value))
def paragraph(text):
    return '<p>'+esc(text)+'</p>'
def section(row):
    qid = row['question_id']
    start = '<section id="'+qid+'"><h2>'+qid+' · '+esc(row['question'])+'</h2>'
    path = folder/'answers'/qid/'result.json'
    if not path.is_file():
        return start+paragraph('미실행')+'</section>'
    result = read(path)
    review = read(folder/(qid+'-review.json'))
    answer = result.get('answer')
    cited = {c['chunk_id'] for c in (answer or {}).get('citations',[])}
    body = [start, '<h3>최종 답변</h3>',paragraph(answer['answer'] if answer else '게시된 답변 없음'),
            '<h3>원문과 대조한 결과</h3>',paragraph(review['conclusion'])]
    labels = review.get('fact_verdicts',{})
    retrieved = row['context_fact_coverage']['fulfilled_ids']
    for fact in claims:
        if fact['question_id'] != qid or fact['role'] != 'required':
            continue
        ident = fact['claim_id']
        quote_text=' / '.join(span['quote'] for span in fact['alternatives'][0]['spans'])
        body.append('<article><strong>'+esc(fact['approved_claim'])+'</strong>'+paragraph(
          ('문맥에 있음' if ident in retrieved else '문맥 근거 불충분')+' · '+labels.get(ident,'답변 평가 불가'))+
          '<blockquote>'+esc(quote_text)+'</blockquote></article>')
    body.extend(paragraph(v) for v in review['notes'])
    body.append('<h3>전달 청크와 실제 인용</h3>')
    for c in result['contexts']:
        is_cited=c['chunk_id'] in cited
        body.append('<details'+(' open' if is_cited else '')+'><summary>'+('답변에서 인용' if is_cited else '미인용')+
          ' · 검색 순위 '+str(c['rank'])+' · PDF '+', '.join(str(p['page']) for p in c['pages'])+'쪽</summary><blockquote>'+
          esc(c['text'])+'</blockquote><small>'+esc(c['chunk_id'])+'</small></details>')
    provider=result.get('provider_result') or {}
    log={k:provider.get(k) for k in ('status','finish_reason','usage','elapsed_ms')}
    log.update(product_status=result['status'],error=result.get('error'))
    body.append('<details><summary>실행 기록</summary><pre>'+esc(json.dumps(log,ensure_ascii=False,indent=2))+'</pre></details></section>')
    return '\n'.join(body)
claims=read(folder.parent/'p032-s1/input/claims-mapping.json')
rows=read(folder/'frozen.json')['rows']
source=root/read(root/'docs/planning/reviews/p032-s2d-input-audit.json')['source_pdf']
page=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>규정집 답변과 인용 대조</title><style>body{font:1.05rem/1.65 system-ui;color:#172b38;max-width:50rem;margin:2rem auto;padding:0 1rem;overflow-wrap:anywhere}article,blockquote{padding:.45rem 1rem;margin:.6rem 0;background:#f3f6f8}section{border-top:1px solid #bbb;margin:2rem 0}summary{cursor:pointer}pre{white-space:pre-wrap}nav a{display:inline-block;padding:.2rem .4rem}</style><main><h1>규정집 답변과 인용 대조</h1>',
paragraph('같은 로컬 Qwen 4B와 저장 문맥으로 질문별 답변을 검토했습니다. 허용 인용 ID는 각 질문에 전달된 청크에서 정했습니다.'),
'<a href="'+quote(os.path.relpath(source,folder))+'">규정집 PDF 원문</a>',
'<nav>'+' '.join('<a href="#'+r['question_id']+'">'+r['question_id']+'</a>' for r in rows)+'</nav>']
page.extend(section(r) for r in rows)
(folder/'report.html').write_text('\n'.join(page)+'</main></html>')
