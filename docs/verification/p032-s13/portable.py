"""Render both saved runs as a standalone UTF-8 page with no dependencies."""
from html import escape
from pathlib import Path
import json

here=Path(__file__).resolve().parent
def read(name):
    return json.loads((here/name).read_text())
def excerpt(text):
    return escape(text).replace('\n','&#10;')

def panel(name,side):
    answer=side['answer'] or {}
    items=[]
    for rank,c in enumerate(side['contexts'],1):
        pages=', '.join(str(p['page']) for p in c['pages'])
        items.append(f'<details><summary>{rank}위 · {pages}쪽 · [{c["start"]}, {c["end"]})</summary>'
                     f'<p>{excerpt(c["text"])}</p></details>')
    citations=''.join('<blockquote>'+excerpt(c['quote'])+'</blockquote>' for c in answer.get('citations',[]))
    return (f'<article><h2>{name}</h2><p>{escape(side["status"])}</p><h3>실제 답변</h3>'
            f'<strong>{escape(answer.get("answer") or "답변 없음")}</strong><h3>실제 인용</h3>{citations}'
            f'<h3>전달 문맥</h3>{"".join(items)}</article>')
pair=read('comparison.json')
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>규정집 승인권자 · 고정과 재귀 청킹</title>
<style>body{font:17px/1.65 system-ui,sans-serif;margin:auto;max-width:76rem;padding:1.5rem;color:#182b35}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,23rem),1fr));gap:2rem}
article{min-width:0;border-top:3px solid #28706b}blockquote{margin:0;padding:1rem;background:#edf5f3}
summary{cursor:pointer;padding:.4rem 0}strong{font-size:1.5rem}h1{line-height:1.3}</style>'''
page+='<h1>'+escape(pair['runs'][0]['question'])+'</h1><p>같은 규정집 · BM25 · 최종 5개 · Qwen 4B · 크기 400자와 겹침 80자</p><main>'
for name,side in zip(('고정 청킹','재귀 청킹'),pair['runs']):
    page+=panel(name,side)
(here/'report.html').write_text(page+'</main></html>\n',encoding='utf-8')
