"""Model-free report from frozen previews, actual results and explicit source reviews."""
from pathlib import Path
import json,html
E=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def esc(x):return html.escape(str(x))
f=read(E/'frozen.json');ledger=read(E/'ledger.json');reviews=read(E/'answer-review.json') if (E/'answer-review.json').exists() else {'rows':[]};byid={r['question_id']:r for r in reviews['rows']};parts=[]
for row in f['rows']:
    q=row['question_id'];preview=read(E/'preview'/q/'result.json');path=E/'answers'/q/'result.json';r=read(path) if path.exists() else None;review=byid.get(q);fact=row['context_fact_coverage'];fact_text=(str(fact['fulfilled'])+'/'+str(fact['total'])) if fact['total'] else 'N/A (필수 fact 0개)';status=r['status'] if r else 'not_executed'
    parts.append(f'<article id="{q}"><p class="eyebrow">{q} · {esc(status)}</p><h2>{esc(row["question"])}</h2><p>동결 문맥: 5청크 · 1,280자 · 필수 근거 {fact_text}. 검색은 재실행하지 않았습니다.</p><h3>전달 문맥과 원문</h3>')
    for ci,c in enumerate(preview['contexts'],1):
        parts.append(f'<details {"open" if r else ""}><summary>청크 {ci} · {esc(", ".join(str(x["page"]) for x in c["pages"]))}쪽</summary><blockquote>{esc(c["text"])}</blockquote><p class="meta">{esc(c["chunk_id"])} · 원문 위치 {c["start"]}–{c["end"]}</p></details>')
    parts.append('<h3>실제 답변과 인용</h3>')
    if r and r.get('answer'):
        a=r['answer'];parts.append(f'<p class="answer">{esc(a["answer"])}</p>')
        for c in a['citations']:parts.append(f'<blockquote>{esc(c["quote"])}</blockquote><p class="meta">{esc(c["chunk_id"])} · 페이지 {esc(c["pages"])}</p>')
    elif r:parts.append('<p class="notice">제품이 유효한 답변을 게시하지 못했습니다. 출력 상한에 도달해 잘린 응답을 그대로 실패로 기록했습니다. 미완성 본문을 답변으로 복원하지 않았습니다.</p>')
    else:parts.append('<p class="notice">미실행. 앞선 smoke 검증이 통과하지 않아 요청을 확대하지 않았습니다.</p>')
    parts.append('<h3>Codex 원문 대조</h3>')
    if review:
        parts.append(f'<p>{esc(review["conclusion"])}</p>')
        for note in review.get('notes',[]):parts.append(f'<p>• {esc(note)}</p>')
    else:parts.append('<p>실제 유효 답변이 없어 내용 검토를 수행하지 않았습니다. 근거 회수와 답변 품질은 별도입니다.</p>')
    metadata={'question_id':q,'body_bytes':row['body_bytes'],'actual_messages_hash':row['actual_messages_hash'],'exact_input_tokens_before_dispatch':row['exact_input_tokens'],'provider':r.get('provider_result') if r else None,'error':r.get('error') if r else None,'dispatch_attempted':r.get('dispatch_attempted',False) if r else False}
    parts.append('<details><summary>실행 로그·설정·실패 상세</summary><pre>'+esc(json.dumps(metadata,ensure_ascii=False,indent=2))+'</pre></details></article>')
content='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>로컬 4B 실제 답변 검증</title><style>
:root{color-scheme:light;font:16px/1.7 system-ui,sans-serif;color:#172938;background:#edf1f4}body{margin:0}main{max-width:1000px;margin:auto;padding:32px 20px}header,article{background:white;border:1px solid #cdd8df;border-radius:12px;padding:24px;margin:0 0 24px}h1{font-size:clamp(1.6rem,4vw,2.3rem);line-height:1.3}h2{font-size:1.35rem}h3{border-top:1px solid #dde4e9;padding-top:14px}nav{display:flex;flex-wrap:wrap;gap:10px}a{color:#075985}details{border:1px solid #ccd7df;border-radius:7px;padding:10px 14px;margin:10px 0}summary{cursor:pointer;font-weight:600}summary:focus-visible,a:focus-visible{outline:3px solid #0e7490;outline-offset:3px}blockquote{white-space:pre-wrap;border-left:3px solid #0e7490;padding:8px 15px;margin:15px 0;background:#f3f7f9}.notice{padding:14px;background:#fff4df}.answer{padding:18px;background:#edf8f4}.meta,.eyebrow{color:#516776;font-size:.88rem}p,pre,blockquote,summary{overflow-wrap:anywhere;word-break:normal}pre{white-space:pre-wrap;font-size:.82rem}*{box-sizing:border-box}@media(max-width:500px){main{padding:14px 10px}header,article{padding:16px}}
</style><main><header><p class="eyebrow">P032 S2d · 가상 규정집 · 실제 로컬 실행</p><h1>근거는 준비됐을 때,<br>4B가 답변까지 완성하는가?</h1>'''
content+=f'<p>상태: <strong>{esc(ledger["status"])}</strong> · 생성 시도 {len(ledger["requests"])}/10 · 검색/임베딩/리랭커 재실행 0회.</p>'
content+='<p class="notice"><strong>첫 문항에서 중단:</strong> 1,024 출력 토큰 상한에 도달해 잘린 응답. 유효 답변 0개 · 나머지 9문항 미실행 · 재시도 0회. 모델 해제와 정상 메모리 복귀를 확인했습니다.</p>'
content+='<p>Qwen3-4B-Thinking-2507 / Q4_K_M · 기존 설치 CLI · think=false · 출력 상한 1,024토큰. gt01·gt02 smoke 통과 후에만 나머지 질문으로 확대합니다.</p><p>이 보고서는 dev Codex가 원문과 대조한 실행 관찰입니다. 자동 평가기·사람의 새 승인·일반 품질 보장을 뜻하지 않습니다. Drive·LLM 청킹·API·평가기 실험은 보류입니다.</p><nav>'
content+=''.join(f'<a href="#{r["question_id"]}">{r["question_id"]}</a>' for r in f['rows']);content+='</nav></header>'+''.join(parts)+'</main></html>'
(E/'report.html').write_text(content)
print('Rendered frozen10 questions; actual results only, no model calls')
