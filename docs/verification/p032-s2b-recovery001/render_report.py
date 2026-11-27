"""Render audited stored results only."""
from pathlib import Path
import json,html
E=Path(__file__).resolve().parent;r=json.loads((E/'results.json').read_text());esc=lambda x:html.escape(str(x));methods=('fixed','recursive','structure','semantic')
css='body{font:16px/1.65 system-ui;max-width:1080px;margin:auto;padding:22px;background:#f6f8f5;color:#21382d;overflow-wrap:anywhere}h1,h2,h3{line-height:1.3}header,section,details{background:white;border:1px solid #cbd7cb;border-radius:12px;padding:20px;margin:18px 0}header{border-top:6px solid #297a56}.scroll{overflow:auto}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #d8e1d8}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere}blockquote{margin:12px 0;padding:12px;border-left:4px solid #81a993;background:#f5f8f5}.muted{color:#52675a}.tag{padding:3px 8px;background:#e0f0e3;border-radius:5px}:focus-visible{outline:3px solid #aa5920}@media(max-width:600px){body{padding:12px}header,section,details{padding:14px}td,th{padding:6px;font-size:14px}}'
s=f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>같은 문서의 청킹 4방식 비교</title><style>{css}</style><header><p class="muted">동일 가상 규정집 · E5 Hybrid · K5 · 문맥 2,000자</p><h1>청킹 경계가 검색 근거를 어떻게 바꾸는가</h1><p>실제 검색 {sum(a["complete"] for a in r["aggregates"].values())}/40건 · 답변 생성·평가기 0회 · 아래 화면 재생은 모델 0회</p><p>고정·재귀·제목/섹션·의미 방식에서 원문 사실이 검색 후보와 전달 문맥에 얼마나 남는지 비교했습니다. 한 규정집·10질문의 관찰이며 일반적인 품질 순위를 보장하지 않습니다.</p></header>'
s+='<section><h2>후보에서 전달 문맥까지</h2><p>각 셀은 회수한 필수 사실 수 / 38개입니다. 사실이 있는8질문을 합산했습니다. gt09·gt10은 필수 사실이 없어 N/A이며 만점으로 세지 않습니다.</p><div class="scroll"><table><tr><th>청킹</th><th>청크</th><th>branch union</th><th>최종 후보20</th><th>top5</th><th>전달 문맥</th></tr>'
for method in methods:
 a=r['aggregates'][method];b=r['boundaries'].get(method,{});s+='<tr><th>'+method+'</th><td>'+esc(b.get('count','N/A'))+'</td>'+''.join(f'<td>{a["levels"][level]["fulfilled"]}/{a["levels"][level]["total"]}</td>' for level in ('branch_union','candidate_N20','top_k','contexts'))+'</tr>'
s+='</table></div><p><b>branch union</b>은 BM2520개와 Dense20개의 합집합(최대40개)입니다. <b>후보20</b>은 이 합집합을 RRF로 정렬한 앞20개입니다. 설치 UI의 기존 “후보 fact”는 branch union을 뜻합니다. 두 값을 같다고 읽으면 안 됩니다.</p><p>새 청크 관련성 qrels가 없어 chunk Recall/MRR/nDCG는 N/A입니다. 위 원문 fact 회수와 답변 정확성·충실성은 서로 다른 지표입니다.</p></section>'
b=r['boundaries'].get('semantic',{})
s+='<section><h2>의미 청킹에서 모델이 결정한 경계</h2><p>원문567단위에 E5 임베딩을 적용했습니다. 최대256자·overlap64자 때문에 기본 구간은192자를 넘지 않습니다. 의미 거리 임계값0.35, 최소120자를 실행 전에 고정했습니다.</p><p>최종 '+esc(b.get('count','N/A'))+'청크 · 경계 이유 '+esc(b.get('cut_reasons',{}))+' · 최대 길이로 강제된 경계 비율 '+(f'{100*b["maximum_cut_fraction"]:.1f}%' if b.get('maximum_cut_fraction') is not None else 'N/A')+'</p><p>의미 방식도 길이 제한에 의해 나뉩니다. 임베딩을 사용했다는 사실만으로 모든 경계가 의미 변화에 의해 선택됐다고 해석하지 않습니다.</p><div class="scroll"><table><tr><th>방식</th><th>길이 중앙값</th><th>중복 문자</th><th>최소–최대</th></tr>'
for method in methods:
 b=r['boundaries'].get(method,{});s+=f'<tr><th>{method}</th><td>{b.get("median_chars","N/A")}</td><td>{b.get("statistics",{}).get("duplicate_chars","N/A")}</td><td>{b.get("min_chars","N/A")}–{b.get("max_chars","N/A")}</td></tr>'
s+='</table></div></section><section><h2>질문별 결과와 실제 전달 근거</h2><p>gt01 생일휴가, gt03 재택 조건, gt06 출장 예외를 먼저 대조하세요. 숫자를 펼치면 충족·누락 fact ID와 실제 전달 원문을 볼 수 있습니다.</p>'
for q in ('gt'+str(i).zfill(2) for i in range(1,11)):
 group=[x for x in r['rows'] if x['question_id']==q];s+=f'<details><summary>{q} · {esc(group[0]["question"])}</summary>'
 for row in group:
  s+='<h3>'+row['method']+'</h3>'
  if row['metrics'] is None:s+='<p>미실행 · 지표 N/A</p>';continue
  metrics=row['metrics'];s+='<p>'+' → '.join(f'{name} {metrics[level]["fulfilled"]}/{metrics[level]["total"]}' if metrics[level]['total'] else name+' N/A' for name,level in [('합집합','branch_union'),('후보20','candidate_N20'),('top5','top_k'),('문맥','contexts')])+'</p>'
  allids=set(metrics['branch_union']['fulfilled_ids']);missing=allids-set(metrics['contexts']['fulfilled_ids'])
  s+='<p>후보 합집합에서 찾았으나 문맥에 남지 않은 fact: '+esc(', '.join(sorted(missing)) or '없음')+'</p>'
  for c in row['selected']:s+=f'<details><summary>전달 {c["rank"]} · 원문 {c["start"]}–{c["end"]}</summary><p>{esc(c["heading_path"])} · {esc(c["pages"])}</p><blockquote>{esc(c["text"])}</blockquote></details>'
 s+='</details>'
s+='</section><section><h2>경계·색인·질문 계산 시간</h2><p>매 작업은 새 owned worker에서 모델을 읽습니다. 아래 시간에는 시작/모델 적재가 포함되며 OS 파일 캐시는 남을 수 있습니다. 같은 모델의 순차 실험 관측값으로 읽으세요.</p><div class="scroll"><table><tr><th>단계</th><th>worker 수</th><th>요청 항목</th><th>worker 시간 합</th></tr>'
for label,ops in [('semantic 경계',[o for o in r['stage_work'] if o['label']=='semantic-boundary'])]+[(m+' 색인',[o for o in r['stage_work'] if o['label']==m+'-index']) for m in methods]+[(m+' 질문10',[o for o in r['stage_work'] if o['label'].startswith(m+'-gt')]) for m in methods]:
 s+=f'<tr><th>{label}</th><td>{len(ops)}</td><td>{sum(o["requested_items"] for o in ops)}</td><td>{sum(o["elapsed_ms"] or 0 for o in ops)/1000:.2f}초</td></tr>'
s+='</table></div>'
s+='</section><section><h2>실행량·실패 이력·해석 한계</h2><p>기존 실패1worker/567요청의 완료 수는 미확정으로 보존했습니다. 복구 child '+str(r['child_workers'])+'worker, '+str(r['child_requested_items'])+'요청; 누적 '+str(r['cumulative_workers'])+'worker / '+str(r['cumulative_requested_items'])+'요청입니다.</p><p>원래 시작·종료 시각을 유지했고 새 모델 다운로드·생성·API·리랭커·평가기·Drive 호출은 없습니다. sampled peak RSS '+f'{r["sampled_peak_rss_bytes"]/1024**3:.2f}'+'GiB는 관측된 owned worker 값이며 전체 머신의 메모리가 아닙니다. 비용·토큰은 미측정입니다.</p><p>현재 비교의 완성은 전체 RAG 검증 완료가 아닙니다. LLM 청킹·답변 생성·사용자 문서 연결은 별도 단계입니다.</p></section><details><summary>실험 기록 · 독립 검증 · 전체 수치</summary><pre>'+esc(json.dumps(r,ensure_ascii=False,indent=2))+'</pre></details></html>'
(E/'report.html').write_text(s)
