"""Render sanitized first-window evidence without loading models."""
from html import escape
from runtime import *

def render():
    window=read(E/'window.json')
    result=read(E/'window-result.json')
    review=read(E/'review.json')
    data=read(E/'final-checks.json')
    spans=result['spans'] or []
    pieces=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>규정집 첫 창의 청킹 경계</title><style>body{max-width:52rem;margin:2.5rem auto;padding:0 1.2rem;color:#172b38;font:1.05rem/1.65 system-ui}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f8;padding:1rem;margin:1rem 0}td,th{padding:.35rem;text-align:left;vertical-align:top}table{border-collapse:collapse}tr{border-bottom:1px solid #ccd5d8}code{overflow-wrap:anywhere}summary{cursor:pointer}</style><main><h1>규정집 첫 창의 청킹 경계</h1>']
    def p(s):pieces.append('<p>'+escape(s)+'</p>')
    p('34개 창 중 첫 번째 창 w000 · 원문 0–762자(끝 위치 제외) · 단위 20개 · 로컬 Qwen 4B')
    p(review['conclusion'])
    p(review['comparison'])
    pieces.append('<h2>첫 창 원문</h2><pre>'+escape(window['source_text'])+'</pre><h2>선택한 경계</h2>')
    if spans:
        for i,(s,ident) in enumerate(zip(spans,result['selected_end_ids']),1):
            pieces.append(f'<article><h3>구간 {i} · {s["start"]}–{s["end"]}자</h3><code>'+escape(result['selected_numbers'][i-1])+' → '+escape(ident)+'</code><blockquote>'+escape(window['source_text'][s['start']:s['end']])+'</blockquote></article>')
    else:p('검증을 통과한 경계 없음. 아래 단위는 모델에 제시한 선택 후보입니다.')
    p(review['meaning'])
    pieces.append('<details><summary>20개 단위와 원문 위치</summary><table><tr><th>위치</th><th>후보 ID와 원문</th></tr>')
    for i,u in enumerate(window['units'],1):
        pieces.append(f'<tr><td>{u["start"]}–{u["end"]}</td><td><code>'+str(i)+' → '+escape(u['id'])+'</code><br>'+escape(u['text'])+'</td></tr>')
    pieces.append('</table></details><h2>시간과 메모리</h2>')
    p(f"관측한 모델 호출 {data['elapsed_seconds']:.1f}초. 같은 시간이 든다고 가정한 나머지 33개 창의 단순 추정은 {data['estimated_remaining_minutes']:.1f}분입니다. 창별 길이·출력량·성공 여부와 준비·정리 시간에 따라 달라집니다.")
    p(f"입력 {data['usage']['input_tokens']:,}토큰, 전체 출력 {data['usage']['output_tokens']:,}토큰. 관측 최대 RSS {data['peak_rss_bytes']/2**30:.2f} GiB.")
    pieces.append('<details><summary>실행 기록</summary><pre>'+escape(json.dumps(data,ensure_ascii=False,indent=2))+'</pre></details></main></html>')
    (E/'report.html').write_text('\n'.join(pieces))

if __name__=='__main__':render()
