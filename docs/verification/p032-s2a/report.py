"""Model-free human-readable report of already frozen S2a artifacts."""
from pathlib import Path
import json,html
E=Path(__file__).resolve().parent;R=E/'run001'
read=lambda name:json.loads((R/name).read_text())
esc=lambda x:html.escape(str(x))
stats=read('rule-statistics.json');facts=read('fact-boundaries.json')['rows'];examples=read('boundary-examples.json')
questions=json.loads((E.parent/'p032-s1/input/questions.json').read_text())
chunks={m:read('chunks/'+m+'/chunks.json') for m in stats}
def table(head,rows):
    return '<div class="table"><table><thead><tr>'+''.join('<th>'+esc(c)+'</th>' for c in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def card(c,index):
    return '<article><p><b>청크 '+str(index+1)+'</b> · '+esc(str(c['start'])+'–'+str(c['end']))+' · '+str(len(c['text']))+'자 · '+esc(' / '.join(c['heading_path']))+'</p><pre>'+esc(c['text'])+'</pre></article>'
parts=['''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>청킹 경계 사전 비교</title>
<style>body{font:16px/1.65 system-ui,sans-serif;max-width:1080px;margin:auto;padding:24px;color:#18302c;background:#f6f8f7}h1,h2{line-height:1.3}h2{margin-top:40px}a{color:#08645b}article,details,.note{background:white;border:1px solid #c9d8d1;border-radius:10px;padding:16px;margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}table{border-collapse:collapse;width:100%}th,td{text-align:left;border-bottom:1px solid #c9d8d1;padding:9px}.table{overflow-x:auto}summary{cursor:pointer;font-weight:600}:focus-visible{outline:3px solid #b44d05}nav{display:flex;gap:12px;flex-wrap:wrap}.muted{color:#49615b}</style>
<h1>같은 원문, 달라진 청크 경계</h1><p>가상 규정집 23쪽 · 원문 38,582자 · 최대 256자 / overlap 64자</p>
<div class="note"><b>준비 단계입니다.</b> 규칙 3종은 실제 청크입니다. 의미·LLM 방식은 요청 미리보기만 있으며 경계가 아직 없습니다. 모델·검색·답변 호출은 0회입니다. 아래 표는 검색 품질 점수가 아닙니다.</div>''']
parts.append(table(['방식','청크 수','길이 중앙값','중복 문자','페이지 교차','제목 경계 교차'],[(m,s['chunk_count'],s['median'],s['duplicate_chars'],s['page_crossing_chunks'],s['heading_crossing_chunks']) for m,s in stats.items()]))
parts.append('<p>세 방식 모두 원문 전체를 보존했습니다. fixed는 192자씩 이동합니다. recursive는 최대 192자의 기본 구간 앞에 최대 64자를 붙입니다. structure는 제목 구간 안에서 재귀 분할하며 이전 섹션으로 overlap하지 않습니다. 제목 인식 범위는 현재 구현의 장/조·Markdown 규칙입니다.</p>')
parts.append('<h2>목차 제목이 본문에 섞인 사례</h2><p>고정 청크는 생일휴가 본문에 출장 제목이, 재귀 청크에는 교육휴가 제목이 붙었습니다. 구조 방식은 이 위치에서 생일휴가 제목으로 분리됩니다. 이 관찰만으로 검색 성능 향상을 단정할 수 없습니다.</p>')
for m,data in examples.items():
    parts.append('<details><summary>'+esc(m)+' · 원문 경계 보기</summary>')
    for c in data['toc_birthday']:parts.append(card(c,c['index']))
    parts.append('</details>')
parts.append('<h2>필수 사실과 청크 경계</h2><p>각 사실의 충분한 원문 구간을 담는 최소 청크 수입니다. 1은 단일 청크에 있다는 뜻이며, 실제 검색 여부를 뜻하지 않습니다. 여러 대체 근거는 OR, 한 대안 안의 여러 구간은 AND로 검사했습니다.</p>')
parts.append(table(['방식','단일 청크에 포함','2개 청크 합집합 필요'],[(m,sum(r['minimum_chunks']==1 for r in facts if r['method']==m),sum(r['minimum_chunks']==2 for r in facts if r['method']==m)) for m in stats]))
parts.append('<nav>'+''.join('<a href="#'+q['id']+'">'+q['id']+'</a>' for q in questions)+'</nav>')
for q in questions:
    rows=[r for r in facts if r['question_id']==q['id']]
    parts.append('<section id="'+q['id']+'"><h2>'+q['id']+' · '+esc(q['question'])+'</h2>')
    if not rows:parts.append('<p>필수 사실이 없는 질문입니다. 포함률 100%로 표시하지 않습니다.</p>')
    else:
        ids=list(dict.fromkeys(r['fact_id'] for r in rows))
        parts.append(table(['사실','fixed','recursive','structure'],[(id,*[next(r['minimum_chunks'] for r in rows if r['fact_id']==id and r['method']==m) for m in stats]) for id in ids]))
        for id in ids:
            group=[r for r in rows if r['fact_id']==id]
            parts.append('<details><summary>'+esc(id)+' · 충분한 원문과 실제 청크</summary>')
            for r in group:
                parts.append('<h3>'+r['method']+' · '+str(r['minimum_chunks'])+'개 필요</h3><p>'+esc(' + '.join(s['quote'] for s in r['chosen']['spans']))+'</p>')
                for n in r['chosen']['chunk_indices']:parts.append(card(chunks[r['method']][n],n))
            parts.append('</details>')
    parts.append('</section>')
parts.append('<h2>아직 실행하지 않은 의미·LLM 방식</h2><p>의미 방식은 E5 경계용 567개 단위, 예상 embedding 1작업입니다. 검색용 청크 임베딩과 별도입니다. LLM은 미설정 local/API 예시 각각 34개 window이며 최대 요청 body는 local 5,948byte / API 5,888byte입니다. 실제 모델·키 선택, 토큰 수, 경계와 최종 청크 수는 미확정입니다.</p><p>후속 4방식의 E5 Hybrid 비교는 보수적으로 경계 1 + 색인 4 + 질문 40 = 45 embedding 작업을 예상합니다. 과거 fixed 결과를 그대로 비교 기준으로 쓰면 34작업이지만 새 v3 실행과 동일한 것으로 바꾸어 표시할 수 없습니다. 별도 실행 계약 전에는 실행하지 않습니다.</p><details><summary>identity·출처·미리보기 기록</summary><pre>'+esc(json.dumps({'fixed_reuse':read('fixed-reuse.json'),'summary':read('summary.json'),'workload':read('workload.json')},ensure_ascii=False,indent=2))+'</pre></details><p class="muted">원문·GT·S1 ledger 불변. 생성·평가기·Drive 미실행. 이 보고서는 청크 경계와 예상 작업량을 설명하며 검색/답변 품질 비교를 대체하지 않습니다.</p></html>')
(E/'report.html').write_text(''.join(parts))
print('saved',E/'report.html')
