"""Standalone escaped HTML, preserving model errors and review boundaries."""
import html
import json


def render(report):
    esc=lambda s:html.escape(str(s),quote=True)
    pretty=lambda v:esc(json.dumps(v,ensure_ascii=False,indent=2))
    parts=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>P013 평가기 검증</title>',
        '<style>body{font:16px/1.65 system-ui;margin:auto;padding:24px;max-width:1000px;background:#faf9f6;color:#222}article{background:white;border:1px solid #ddd;border-radius:12px;margin:20px 0;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 monospace}p,li,code{overflow-wrap:anywhere}summary{cursor:pointer;padding:8px}summary:focus-visible,a:focus-visible{outline:3px solid #2678b7}blockquote{border-left:3px solid #2678b7;margin:12px 0;padding:8px 16px}nav{display:flex;flex-wrap:wrap;gap:12px}.status{font-weight:bold}@media(max-width:480px){body{padding:12px}article{padding:12px}}</style>',
        '<h1>P013 평가기 단계 검증</h1><p>승인 정답과 새 모델 출력의 검토는 별개입니다. 공개 학습 세트이며 일반화 성능 보장이 아닙니다.</p>',
        f'<p>실제 모델 요청: {report["model_requests"]} · 실제 RAG 평가: {esc(report["actual_rag_evaluated"])}</p>',
        '<h2>단계 진행 기준</h2><pre>'+pretty(report['gates'])+'</pre>',
        '<p>정확한 문장·발생 위치 일치는 자동 대조합니다. 표현이 다른 추출 결과는 의미 오류로 단정하거나 자동 승인하지 않고 별도 검토로 남깁니다.</p>',
        '<nav>'+''.join(f'<a href="#{esc(r["case_id"])}">{esc(r["case_id"])}</a>' for r in report['cases'])+'</nav>']
    for row in report['cases']:
        d=row['data'];c=row['comparison']
        parts.append(f'<article id="{esc(row["case_id"])}"><h2>{esc(row["case_id"])} · {esc(row["role"])}</h2><p class="status">{esc(c["status"])}</p>')
        if 'question' in d: parts.append('<h3>질문</h3><p>'+esc(d['question'])+'</p>')
        if 'answer' in d: parts.append('<h3>고정 답변</h3><blockquote>'+esc(d['answer'])+'</blockquote>')
        for claim in c.get('generated_claims',[]):
            parts.append('<h3>추출 주장</h3><p>'+esc(claim['text'])+'</p>')
            for occurrence in claim['occurrences']: parts.append('<blockquote>'+esc(occurrence['quote'])+'</blockquote>')
        if d.get('contexts'): parts.append('<h3>실제 판정 입력 문맥</h3><pre>'+pretty(d['contexts'])+'</pre>')
        parts.append('<h3>기대값 대조 · 점수/미확정</h3><pre>'+pretty(c)+'</pre>')
        parts.append('<details><summary>실험 기록</summary><pre>'+pretty({k:v for k,v in row.items() if k not in ('comparison','data')})+'</pre></details></article>')
    parts.append('<details><summary>버전과 실행 상태</summary><pre>'+pretty({k:v for k,v in report.items() if k!='cases'})+'</pre></details></html>')
    return '\n'.join(parts)
