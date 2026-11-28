"""Render the reviewed, normalized result. No provider or network access."""
from html import escape
from pathlib import Path
import json

base = Path(__file__).resolve().parent
def read(name):
    return json.loads((base / name).read_text())
result = read('answers/gt01/result.json')
review = read('answer-review.json')
provider = result['provider_result']
def esc(value):
    return escape(str(value))
parts = ['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>생일 특별휴가 답변 검토</title><style>body{margin:3rem auto;padding:0 1.2rem;max-width:48rem;color:#172b38;font:1.05rem/1.7 system-ui}h2{margin-top:2rem}blockquote{margin:1rem 0;padding-left:1rem;border-left:.25rem solid #789}details,article{margin:1rem 0}summary{cursor:pointer}pre{white-space:pre-wrap}body{overflow-wrap:anywhere}</style><main><h1>생일 특별휴가 답변 검토</h1>']
parts.append('<p>Qwen3-4B-Thinking-2507 · 로컬 Ollama · 저장된 근거 5개</p>')
parts.append('<h2>질문</h2><p>'+esc(result['question'])+'</p><h2>최종 답변</h2>')
answer = result.get('answer')
parts.append('<p>'+esc(answer['answer'] if answer else '게시된 답변 없음')+'</p>')
parts.append('<p>'+esc(review['conclusion'])+'</p>')
parts.append('<h2>근거 대조</h2>')
for item in review['notes']:
    parts.append('<p>'+esc(item)+'</p>')
cited = {c['chunk_id'] for c in (answer or {}).get('citations',[])}
for ctx in result['contexts']:
    label='답변 인용' if ctx['chunk_id'] in cited else '전달 문맥'
    parts.append('<details><summary>'+esc(label)+' · 검색 순위 '+esc(ctx['rank'])+'</summary><blockquote>'+esc(ctx['text'])+'</blockquote><small>'+esc(ctx['chunk_id'])+'</small></details>')
parts.append('<details><summary>실행 기록</summary><pre>'+esc(json.dumps({k:provider.get(k) for k in ('status','finish_reason','usage','elapsed_ms','error')},indent=2,ensure_ascii=False))+'</pre><p>출력 토큰은 provider 합계입니다. 추론과 최종 답변의 개별 토큰 수는 미측정입니다.</p></details></main></html>')
(base/'report.html').write_text('\n'.join(parts))
