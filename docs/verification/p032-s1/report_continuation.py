"""Read-only frozen result replay and S1 report. Network/model entry points forbidden."""
from pathlib import Path
import sys,json,html,socket,statistics,math
from unittest.mock import patch
from rag_package import retrieval,candidates,reranking,embedding,reranker,fact_metrics,search_metrics
from rag_package.storage import read_json,write_json,verify,digest,fingerprint,require
E=Path(__file__).resolve().parent;I=E/'input';R=E/'run001';C=E/'continuation001/run';OUT=E/sys.argv[1]
OUT.mkdir(exist_ok=False)
def denied(*a,**k):raise AssertionError('report must not run a model or network')
socket.socket.connect=denied;socket.getaddrinfo=denied
questions=read_json(I/'questions.json');facts=read_json(I/'facts.json');qrels=read_json(I/'qrels.json');chunks=read_json(I/'build-bm25/chunks.json');byid={c['chunk_id']:c for c in chunks};sm=verify(I/'snapshot-installed','snapshot');rows=[]
search_labels=['bm25','e5-dense','e5-hybrid','bge-dense','bge-hybrid'];rank_labels=['none','mmini','bge-reranker']
with patch.object(embedding,'encode',denied),patch.object(reranker,'score',denied):
 for kind,labels in [('search',search_labels),('rerank',rank_labels)]:
  for label in labels:
   for q in questions:
    path=(C if label in ('bge-dense','bge-hybrid','mmini','bge-reranker') else R)/kind/label/q['id'];row={'kind':kind,'variant':label,'question_id':q['id'],'question':q['question'],'status':'not_executed','metrics':None,'elapsed_ms':None,'sampled_peak_rss_bytes':None,'contexts':[],'ranking':[]}
    fs=next(f['required_facts'] for f in facts['questions'] if f['question_id']==q['id'])
    if (path/'manifest.json').exists():
     if kind=='search':
      m=verify(path,'answer');r=read_json(path/'result.json');require(r['question']==q['question'] and r['query_hash']==fingerprint(q['question']) and r['generation_requests']==0,'wrong_result','report')
      require(r['source_fingerprint']==sm['fingerprint'] and r['chunk_fingerprint']==qrels['chunk_fingerprint'],'wrong_source','report')
      ranked=candidates.ranking(r,chunks);selected=r['candidates'];contexts=r['contexts'];full=[byid[x['chunk_id']] for x in ranked];top20=full[:20]
      metric=search_metrics.metrics(selected,qrels['judgments'][q['id']],5,True);require(metric==r['metrics']['retrieval'],'metric_mismatch','report')
      row.update(status='complete',provider_status=r['status'],generation_requests=0,embedding_execution_kind=r['embedding_work'].get('execution_kind','none'),elapsed_ms=r['latency_ms']['total'],sampled_peak_rss_bytes=(r['embedding_work'].get('monitor') or {}).get('sampled_peak_rss_bytes'),metrics={'retrieval':metric,'facts':{'candidate_N20':fact_metrics.coverage(top20,fs),'branch_union':fact_metrics.coverage(full,fs),'top_k':fact_metrics.coverage([byid[x['chunk_id']] for x in selected],fs),'contexts':fact_metrics.coverage(contexts,fs)}},contexts=contexts,ranking=[dict(byid[x['chunk_id']],rank=i+1,score=x['score']) for i,x in enumerate(ranked[:20])],branch_union_count=len(full),candidate_N20_count=len(top20))
     else:
      r,c,_,_=reranking.load(path);require(r['question_id']==q['id'] and c['question']==q['question'],'wrong_result','report')
      row.update(status=r['status'],candidate_fingerprint=c['candidate_fingerprint'],elapsed_ms=r['work']['elapsed_ms'],sampled_peak_rss_bytes=(r['work'].get('monitor') or {}).get('sampled_peak_rss_bytes'),metrics=r['metrics'],contexts=(r['selection'] or {}).get('contexts',[]),ranking=(r['selection'] or {}).get('ranking',[]),error=r['error'],worker_execution_kind=r['work']['execution_kind'])
     row['artifact_sha256']=verify(path,'answer' if kind=='search' else 'rerank')['fingerprint'];row['path']=str(path.relative_to(E))
    rows.append(row)
# Independent arithmetic checks on a concrete rank list, not package implementation reuse.
for row in rows:
 if row['status']!='complete':continue
 grades=qrels['judgments'][row['question_id']];ranking=row['ranking'][:5];hits=sum(grades[x['chunk_id']]>0 for x in ranking);total=sum(g>0 for g in grades.values());v=row['metrics']['retrieval']['values']
 if not total:assert all(v[k] is None for k in ('recall','mrr','ndcg'));continue
 assert abs(v['recall']-hits/total)<1e-12
 expected=next((1/(i+1) for i,x in enumerate(ranking) if grades[x['chunk_id']]>0),0);assert abs(v['mrr']-expected)<1e-12
 gain=lambda gs:sum((2**g-1)/math.log2(i+2) for i,g in enumerate(gs))
 ideal=gain(sorted(grades.values(),reverse=True)[:5]);assert abs(v['ndcg']-gain([grades[x['chunk_id']] for x in ranking])/ideal)<1e-12
aggregates=[]
for kind,labels in [('search',search_labels),('rerank',rank_labels)]:
 for label in labels:
  rr=[r for r in rows if r['kind']==kind and r['variant']==label];valid=[r for r in rr if r['status']=='complete' and r['metrics']['retrieval']['values']['recall'] is not None]
  aggregate={'kind':kind,'variant':label,'complete':sum(r['status']=='complete' for r in rr),'failed':sum(r['status']=='failed' for r in rr),'not_executed':sum(r['status']=='not_executed' for r in rr),'metric_valid':len(valid),'no_answer_NA':sum(r['status']=='complete' and r['question_id'] in ('gt09','gt10') for r in rr)}
  for k in ('recall','mrr','ndcg'):aggregate[k]=statistics.mean(r['metrics']['retrieval']['values'][k] for r in valid) if valid else None
  good=[r for r in rr if r['status']=='complete' and r['metrics']['facts']['contexts']['total']]
  aggregate['context_fact_micro']=sum(r['metrics']['facts']['contexts']['fulfilled'] for r in good)/sum(r['metrics']['facts']['contexts']['total'] for r in good) if good else None
  aggregate['context_fact_count']=sum(r['metrics']['facts']['contexts']['fulfilled'] for r in good);aggregate['fact_denominator']=sum(r['metrics']['facts']['contexts']['total'] for r in good)
  ms=[r['elapsed_ms'] for r in rr if r['status']=='complete'];aggregate['median_ms']=statistics.median(ms) if ms else None
  rss=[r['sampled_peak_rss_bytes'] for r in rr if r['sampled_peak_rss_bytes'] is not None];aggregate['max_sampled_rss_bytes']=max(rss) if rss else None
  aggregates.append(aggregate)
ledger=read_json(C/'ledger.json');manifest=read_json(C/'manifest.json')
summary={'scope':'P032 S1 synthetic PDF live CPU retrieval; no answer generation','rows':rows,'aggregates':aggregates,'ledger':ledger,'manifest_sha256':digest((C/'manifest.json').read_bytes()),'parent_manifest_sha256':digest((R/'manifest.json').read_bytes()),'continuation_failures':[read_json(p) for p in sorted(C.glob('*-failure.json'))],'model_calls_this_replay':0,'network_calls_this_replay':0,'metric_check':'independent Recall/MRR/nDCG arithmetic PASS','limits':'10 exposed synthetic questions, same-agent labels, no blind generalization; sampled RSS not instantaneous peak','stages_remaining':['S2 generation/LLM chunking','S3 user Drive'],'live_failure':read_json(R/'mmini-failure-diagnosis.json'),'candidate_note':'search candidate_N20 uses top20 fused candidates; branch_union is <=40 from two top20 branches; reranker N is fixed20'}
paired=[]
for label in ('mmini','bge-reranker'):
 valid=[]
 for q in questions:
  baseline=next(r for r in rows if r['kind']=='rerank' and r['variant']=='none' and r['question_id']==q['id'])
  selected=next(r for r in rows if r['kind']=='rerank' and r['variant']==label and r['question_id']==q['id'])
  if baseline['status']=='complete' and selected['status']=='complete':
   require(baseline['candidate_fingerprint']==selected['candidate_fingerprint'],'unpaired_candidate','report')
   if baseline['metrics']['retrieval']['values']['ndcg'] is not None:
    valid.append({'question_id':q['id'],'ndcg_delta':selected['metrics']['retrieval']['values']['ndcg']-baseline['metrics']['retrieval']['values']['ndcg'],'required_fact_delta':selected['metrics']['facts']['contexts']['fulfilled']-baseline['metrics']['facts']['contexts']['fulfilled']})
 paired.append({'variant':label,'valid_pairs':len(valid),'questions':valid,'ndcg_delta':statistics.mean(r['ndcg_delta'] for r in valid) if valid else None,'required_fact_delta':sum(r['required_fact_delta'] for r in valid) if valid else None})
summary['paired_none_comparison']=paired
write_json(OUT/'summary.json',summary)
def esc(x):return html.escape(str(x))
def num(x):return 'N/A' if x is None else f'{x:.3f}'
def table(head,body):return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in body)+'</tbody></table></div>'
body='<h1>검색과 리랭커, 실제로 달라졌나?</h1><p>가상 HR 규정집 23쪽 · 201청크 · 고정 256자 / overlap 64자 · 10개 질문</p><p class="notice">공개 사전학습 모델의 CPU 검색 실험입니다. 답변 생성·LLM 평가·Drive 호출은 0회이며, 답변 품질은 측정하지 않았습니다.</p>'
body+='<p class="notice">첫 mMiniLM smoke의 model_weights_mismatch는 부모 기록에 보존했습니다. 후속 정확 계약으로 고정 위치 buffer를 검증하고 누적 예산·원래 마감을 이어받았습니다. 각 모델의 현재 완료·실패·미실행은 아래 표와 작업 기록을 확인하세요. none은 저장 후보의 모델 없는 재생입니다.</p>'
body+='<p>필수 fact 회수는 충분한 원문 구간의 포함 여부이며, nDCG는 qrels 청크 등급과 순위입니다. 두 지표가 다른 방향으로 움직일 수 있습니다. 최초 실패 작업의 완료 pair 수는 미확정으로 보존했습니다.</p>'
body+='<h2>완료·미실행과 유효 분모</h2>'+table(['단계/설정','완료/10','실패','미실행','유효 질문','Recall@5','MRR@5','nDCG@5','문맥 사실/38','중앙 지연 ms','최대 관측 MiB'],[[a['kind']+'/'+a['variant'],a['complete'],a['failed'],a['not_executed'],a['metric_valid'],num(a['recall']),num(a['mrr']),num(a['ndcg']),f"{a['context_fact_count']}/{a['fact_denominator']}",num(a['median_ms']),num(a['max_sampled_rss_bytes']/1024**2 if a['max_sampled_rss_bytes'] is not None else None)] for a in aggregates])
body+='<p>gt09/gt10은 정답 근거가 없는 질문이므로 지표 N/A입니다. 미실행은 0점이 아닙니다. 지연은 cold worker 기준이며 검색은 load+query, 리랭커는 파일 검증·load·pair scoring을 포함한 전체 작업 시간으로 범위가 다릅니다. 색인 준비 시간은 아래 작업 기록에서 별도로 확인합니다.</p><p>Hybrid는 각 branch top20을 합칩니다. 아래 후보 fact는 합친 순위의 앞 20개 기준이며, 저장된 branch_union 수치와 구분합니다. 리랭커는 동일 E5 Hybrid N20 후보를 고정했습니다.</p>'
body+='<h2>동일 후보 none 대비</h2>'+table(['모델','유효 paired 질문','평균 nDCG 차이','필수 사실 개수 차이'],[[p['variant'],p['valid_pairs'],num(p['ndcg_delta']),p['required_fact_delta'] if p['required_fact_delta'] is not None else 'N/A'] for p in paired])
body+='<nav aria-label="질문 탐색">'+''.join('<a href="#'+q['id']+'">'+q['id']+'</a> ' for q in questions)+'</nav>'
for q in questions:
 body+='<section id="'+q['id']+'"><h2>'+esc(q['id']+' · '+q['question'])+'</h2>'
 for r in (x for x in rows if x['question_id']==q['id']):
  body+='<details><summary>'+esc(r['kind']+' / '+r['variant']+' · '+r['status'])+'</summary>'
  if r['metrics']:
   f=r['metrics']['facts'];body+='<p>필수 사실 회수 · 후보 '+num(f.get('candidate_N20',f.get('candidate',{})).get('fact_recall'))+' → top5 '+num(f['top_k']['fact_recall'])+' → 전달 문맥 '+num(f['contexts']['fact_recall'])+'</p>'
   inc={x['chunk_id'] for x in r['contexts']}
   body+=table(['원래 순위','현재 순위','선택','원문 구간'],[[x.get('original_rank','—'),x['rank'],'전달' if x['chunk_id'] in inc else 'top K 밖' if x['rank']>5 else '예산 제외',f"{x['start']}–{x['end']}"] for x in r['ranking']])
   for x in r['ranking'][:5]:body+='<blockquote><strong>'+esc('순위 '+str(x['rank'])+' · 페이지 '+str([p['page'] for p in x['pages']]))+'</strong><br>'+esc(x['text'])+'</blockquote>'
  else:body+='<p>결과 없음 · 실패/미실행 상태를 작업 기록과 함께 확인하세요.</p>'
  body+='</details>'
 body+='</section>'
body+='<details><summary>실험 기록 · 실제 작업량·중단 상태</summary><pre>'+esc(json.dumps(ledger,ensure_ascii=False,indent=2))+'</pre></details><p>감시 간격 목표 250ms. 시스템 전체 OOM 방지나 샘플 사이 순간 peak 측정을 보장하지 않습니다. P032 S2/S3는 이번 범위에서 실행하지 않았습니다.</p>'
page='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>P032 S1 검색 비교</title><style>body{max-width:1180px;margin:auto;padding:24px;font:16px/1.65 system-ui;background:#f4f7f7;color:#16323b}h1{font-size:2rem;line-height:1.3}section{background:white;border:1px solid #dce5e7;border-radius:12px;padding:20px;margin:20px 0}.notice{border-left:4px solid #147d92;padding:12px;background:#e5f3f5}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;border-bottom:1px solid #cdd;padding:10px}summary{cursor:pointer;padding:12px;font-weight:600}details{border:1px solid #dce5e7;margin:12px 0;border-radius:8px}blockquote{white-space:pre-wrap;margin:12px;padding:16px;background:#f2f6f7;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:500px;overflow:auto}a{padding:8px;display:inline-block;color:#075e72}:focus-visible{outline:3px solid #c75000;outline-offset:3px}@media(max-width:600px){body{padding:12px}section{padding:12px}h1{font-size:1.6rem}}</style></head><body>'+body+'</body></html>'
(OUT/'report.html').write_text(page,encoding='utf-8')
write_json(OUT/'replay-check.json',{'status':'PASS','network_calls':0,'model_calls':0,'rows':len(rows),'complete':sum(r['status']=='complete' for r in rows),'artifacts_verified':sum('artifact_sha256' in r for r in rows)})
print(json.dumps({'report':str(OUT/'report.html'),'aggregates':aggregates},ensure_ascii=False))
