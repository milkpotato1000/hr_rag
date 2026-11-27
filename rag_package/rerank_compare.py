"""Paired fixed-candidate comparisons and model-free report replay."""
from pathlib import Path
import html
import json
from . import candidates,reranking,search_metrics,reranker
from .documents import safe_id
from .storage import require,RagError,read_json,write_json,fingerprint,staging,seal,verify,new_output


def resolve(base,value):
    require(isinstance(value,str) and value,'invalid_input_path','compare');p=Path(value)
    return p if p.is_absolute() else Path(base)/p


def inputs(candidate_set, variants, qrels=None, facts=None):
    cs=read_json(candidate_set);vs=read_json(variants)
    reranker.strict(cs,{'schema_version','candidates'});reranker.strict(vs,{'schema_version','variants'})
    require(type(cs['schema_version']) is int and cs['schema_version']==1 and type(vs['schema_version']) is int and vs['schema_version']==1,'invalid_compare_schema','compare')
    require(isinstance(cs['candidates'],list) and 1<=len(cs['candidates'])<=20 and isinstance(vs['variants'],list) and 2<=len(vs['variants'])<=4,'compare_limit','compare')
    sources=[];ids=set();qs=[]
    for row in cs['candidates']:
        reranker.strict(row,{'question_id','path'})
        require(safe_id(row['question_id']) and row['question_id'] not in ids,'duplicate_question','compare');ids.add(row['question_id'])
        path=resolve(Path(candidate_set).parent,row['path']);c,docs,corpus=candidates.load(path)
        require(row['question_id']==c['question_id'],'question_identity_mismatch','compare')
        sources.append((path,c,docs,corpus));qs.append({'id':c['question_id'],'question':c['question']})
    first=sources[0][1]
    require(all(c['source_fingerprint']==first['source_fingerprint'] and c['chunk_fingerprint']==first['chunk_fingerprint'] for _,c,_,_ in sources),'mixed_corpus','compare')
    checked=[];ids=set()
    for v in vs['variants']:
        reranker.strict(v,{'id','label','method','profile','top_k','context_budget_chars'})
        require(safe_id(v['id']) and v['id'] not in ids and isinstance(v['label'],str) and 1<=len(v['label'])<=120,'invalid_variant','compare');ids.add(v['id'])
        p=resolve(Path(variants).parent,v['profile']) if v['profile'] is not None else None
        profiles=[reranking.settings(v['method'],p,v['top_k'],v['context_budget_chars'],c['requested_n']) for _,c,_,_ in sources]
        checked.append(dict(v,profile=profiles[0]))
    require(sum(v['method']=='none' for v in checked)==1,'one_baseline_required','compare')
    require(len({(v['top_k'],v['context_budget_chars']) for v in checked})==1,'paired_settings_mismatch','compare')
    qrels,facts=reranking.validate_labels(first,sources[0][2],sources[0][3],qs,qrels,facts)
    return sources,checked,qs,qrels,facts


def summarize(rows,variants):
    baseline=next(v['id'] for v in variants if v['method']=='none');paired={}
    aggregates=search_metrics.aggregate([dict(r,config_id=r['variant_id'],metrics=r['metrics'] or {}) for r in rows])
    facts={}
    for v in variants:
        selected=[r for r in rows if r['variant_id']==v['id']];facts[v['id']]={}
        for level in ('candidate','top_k','contexts'):
            values=[r['metrics']['facts'][level] for r in selected if r['status']=='complete' and r['metrics']['facts'][level]['fact_recall'] is not None]
            facts[v['id']][level]={'macro':sum(x['fact_recall'] for x in values)/len(values) if values else None,
                'micro':sum(x['fulfilled'] for x in values)/sum(x['total'] for x in values) if values else None,
                'valid':len(values),'excluded':len(selected)-len(values),'fulfilled':sum(x['fulfilled'] for x in values),'total_facts':sum(x['total'] for x in values)}
        if v['id']==baseline:continue
        paired[v['id']]={}
        for metric in ('precision','recall','mrr','ndcg','context_recall','candidate_recall','fact_top_k','fact_contexts'):
            differences=[];excluded={};per_question=[]
            for row in selected:
                base=next(r for r in rows if r['variant_id']==baseline and r['question_id']==row['question_id'])
                def value(r):
                    if r['status']!='complete':return None,r['status']
                    m=r['metrics']
                    if metric.startswith('fact_'):
                        part=m['facts'][metric[5:]];return part['fact_recall'],part['reason']
                    if metric in ('context_recall','candidate_recall'):return m[metric],m['retrieval']['reason']
                    return m['retrieval']['values'][metric],m['retrieval']['reason']
                a,ar=value(base);b,br=value(row)
                if a is None or b is None:
                    reason=ar if a is None else br;reason=reason or 'not_measured';excluded[reason]=excluded.get(reason,0)+1
                    per_question.append({'question_id':row['question_id'],'delta':None,'reason':reason})
                else:
                    d=b-a;differences.append(d);per_question.append({'question_id':row['question_id'],'delta':d,'outcome':'better' if d>0 else 'worse' if d<0 else 'same'})
            paired[v['id']][metric]={'delta':sum(differences)/len(differences) if differences else None,'paired_valid':len(differences),'total':len(selected),'exclusion_reasons':excluded,'questions':per_question}
    return {'retrieval':aggregates,'facts':facts,'paired':paired}


def compare(candidate_set,variants,out,*,qrels=None,facts=None,execute=False,backend=None):
    new_output(out);sources,checked,qs,qrels,facts=inputs(candidate_set,variants,qrels,facts);rows=[]
    dispatched=False
    try:
        with staging(out) as tmp:
            for path,c,_,_ in sources:
                for v in checked:
                    dest=tmp/v['id']/c['question_id'];entry={'variant_id':v['id'],'question_id':c['question_id'],'candidate_fingerprint':c['candidate_fingerprint'],'candidate_execution_kind':c['execution_kind']}
                    try:
                        r=reranking.run(path,v['method'],dest,profile=v['profile'],top_k=v['top_k'],context_budget_chars=v['context_budget_chars'],execute=execute,backend=backend,qrels=qrels,facts=facts,questions=qs)
                        dispatched=dispatched or bool(r['work'].get('queries'))
                        entry.update(result_path=dest.relative_to(tmp).as_posix(),status=r['status'],error=r['error'],reason=r['reason'],metrics=r['metrics'],work=r['work'],original_retrieval_ms=r['original_retrieval_ms'])
                    except (RagError,OSError,UnicodeError) as e:
                        dispatched=dispatched or getattr(e,'dispatch_attempted',False)
                        entry.update(status='failed',error={'code':getattr(e,'code','output_write_failed')},reason=None,metrics=None,result_path=None,work=None,dispatch_attempted=getattr(e,'dispatch_attempted',False))
                    rows.append(entry)
            summary={'schema_version':1,'questions':qs,'questions_hash':fingerprint(qs),'variants':[dict(v,profile=reranker.identity(v['profile']) if v['profile'] else None) for v in checked],
                'source_fingerprint':sources[0][1]['source_fingerprint'],'chunk_fingerprint':sources[0][1]['chunk_fingerprint'],'qrels':qrels,'facts':facts,'rows':rows,
                'aggregates':summarize(rows,checked),'retry_count':0,'generation_requests':0,'latency_note':'Original search recorded earlier; new reranking uses sequential cold workers. Not a simultaneous warm benchmark.'}
            write_json(tmp/'comparison.json',summary);seal(tmp,{'schema_version':1,'kind':'rerank-comparison','questions_hash':summary['questions_hash']})
    except (RagError,OSError,UnicodeError) as e:
        err=e if isinstance(e,RagError) else RagError('output_write_failed','publish');err.dispatch_attempted=dispatched;raise err from None
    return summary


def load(root):
    from .storage import safe_path
    root=Path(root);m=verify(root,'rerank-comparison');s=read_json(root/'comparison.json')
    require(fingerprint(s['questions'])==s['questions_hash']==m['identity']['questions_hash'],'stale_comparison','replay')
    require(len(s['rows'])==len(s['questions'])*len(s['variants']) and len({(r['variant_id'],r['question_id']) for r in s['rows']})==len(s['rows']),'stale_comparison_rows','replay')
    qs={q['id']:q['question'] for q in s['questions']};vs={v['id']:v for v in s['variants']};seen={}
    require(len(qs)==len(s['questions']) and len(vs)==len(s['variants']) and {(r['variant_id'],r['question_id']) for r in s['rows']}=={(v,q) for v in vs for q in qs},'stale_comparison_keys','replay')
    require(sum(v['method']=='none' for v in vs.values())==1 and len({(v['top_k'],v['context_budget_chars']) for v in vs.values()})==1,'stale_comparison_variants','replay')
    for row in s['rows']:
        old=seen.setdefault(row['question_id'],row['candidate_fingerprint'])
        require(old==row['candidate_fingerprint'],'unpaired_candidates','replay')
        if row['result_path'] is None:require(row['status']=='failed','missing_result','replay');continue
        r,c,_,_=reranking.load(safe_path(root,row['result_path']))
        require(all(row[k]==r[k] for k in ('status','error','reason','metrics','work','original_retrieval_ms','candidate_fingerprint')) and r['qrels']==s['qrels'] and r['facts']==s['facts'] and r['questions']==s['questions'],'stale_comparison_detail','replay')
        v=vs[row['variant_id']]
        require(row['question_id']==r['question_id']==c['question_id'] and r['question']==c['question']==qs[row['question_id']] and c['query_hash']==fingerprint(qs[row['question_id']]),'unpaired_question','replay')
        require(v['method']==r['method'] and v['profile']==r['profile_identity'] and v['top_k']==r['top_k_limit'] and v['context_budget_chars']==r['context_budget_chars'],'unpaired_variant','replay')
        require(row['candidate_execution_kind']==r['candidate_execution_kind']==c['execution_kind'],'stale_provenance','replay')
        require(c['source_fingerprint']==s['source_fingerprint'] and c['chunk_fingerprint']==s['chunk_fingerprint'],'stale_comparison_source','replay')
    require(s['aggregates']==summarize(s['rows'],s['variants']),'stale_comparison_metrics','replay')
    return s


def report(root,out):
    s=load(root);new_output(out)
    def esc(value):return html.escape(str(value))
    def number(value):return 'N/A' if value is None else f'{value:.4f}'
    def table(headers,rows):
        return '<div class="table"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    lines=['# 고정 후보 리랭커 비교','',s['latency_note'],'','Faithfulness / Correctness: N/A (evaluator_not_connected).','',
           '| 설정 | 질문 | 상태 | Recall@K | 문맥 Recall |','| --- | --- | --- | --- | --- |']
    body=[];summary_rows=[];paired_rows=[]
    labels={v['id']:v['label'] for v in s['variants']}
    for variant,metrics in s['aggregates']['paired'].items():
        for metric in ('recall','ndcg','fact_top_k','fact_contexts'):
            item=metrics[metric];paired_rows.append([labels[variant],metric,number(item['delta']),f"{item['paired_valid']} / {item['total']}",json.dumps(item['exclusion_reasons'],ensure_ascii=False)])
    for row in s['rows']:
        metrics=row['metrics'] or {};values=metrics.get('retrieval',{}).get('values',{});recall=values.get('recall');context=metrics.get('context_recall')
        lines.append(f"| {row['variant_id']} | {row['question_id']} | {row['status']} | {number(recall)} | {number(context)} |")
        summary_rows.append([labels[row['variant_id']],row['question_id'],row['status'],number(metrics.get('candidate_recall')),number(recall),number(values.get('ndcg')),number(context),number(metrics.get('facts',{}).get('top_k',{}).get('fact_recall'))])
        detail={'row':row};section='<section><h2>'+esc(labels[row['variant_id']]+' / '+row['question_id'])+'</h2><p>후보 출처: '+esc(row['candidate_execution_kind'])+' · scorer: '+esc((row.get('work') or {}).get('execution_kind','미실행'))+'</p>'
        if row['result_path']:
            r,c,_,_=reranking.load(Path(root)/row['result_path']);detail['selection']=r['selection']
            section+='<p>'+esc(c['question'])+'</p><p>후보 N '+str(c['requested_n'])+' (실제 '+str(c['actual_n'])+') → K '+str(r['top_k_limit'])+' → 문자 예산 '+str(r['context_budget_chars'])+'</p>'
            if r['selection']:
                included={x['chunk_id'] for x in r['selection']['contexts']}
                section+=table(['청크','원래 순위','새 순위','raw score','전달 여부'],[[x['chunk_id'],x['original_rank'],x['rank'],number(x['reranker_score']),'포함' if x['chunk_id'] in included else 'top K 밖' if x['rank']>r['top_k_limit'] else '문자 예산 제외'] for x in r['selection']['ranking']])
                for x in r['selection']['ranking']:
                    section+='<details><summary>'+esc(x['document_id']+' · '+str(x['start'])+'–'+str(x['end']))+' 원문 청크</summary><blockquote>'+esc(x['text'])+'</blockquote></details>'
            else:section+='<p>'+esc(r['reason'] or (r['error'] or {}).get('code','미실행'))+' · 점수 0이 아닙니다.</p>'
        section+='<details><summary>실험 기록 · JSON</summary><pre>'+esc(json.dumps(detail,ensure_ascii=False,indent=2))+'</pre></details></section>';body.append(section)
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>리랭커 비교</title><style>body{max-width:1100px;margin:auto;padding:24px;font:16px system-ui;color:#142b34;background:#f4f7f8}section{background:white;padding:20px;margin:24px 0;border:1px solid #d7e2e5;border-radius:12px}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;padding:12px}table{width:100%;border-collapse:collapse;font-size:14px}td,th{border-bottom:1px solid #ccd;padding:8px;text-align:left;overflow-wrap:anywhere}.table{overflow:auto}details{margin-top:12px}</style><h1>고정 후보 리랭커 비교</h1><p>후보 N은 검색의 회수 범위, K는 재정렬 후 선택 범위입니다. 문맥 예산으로 제외된 청크는 답변 모델에 전달되지 않습니다.</p><p>'+esc(s['latency_note'])+'</p><p>합성·주입 후보와 tiny 모델 시험은 실제 한국어 품질 증거가 아닙니다. 답변 평가 N/A · 실제 품질 미검증.</p><h2>질문별 결과</h2>'+table(['설정','질문','상태','후보 Recall','Recall@K','nDCG@K','문맥 Recall','필수 fact@K'],summary_rows)+'<h2>none 대비 변화와 유효 분모</h2>'+table(['설정','지표','평균 차이','paired 유효/전체','제외 이유'],paired_rows)+'<details><summary>전체 집계 · macro/micro 및 분모</summary><pre>'+esc(json.dumps(s['aggregates'],ensure_ascii=False,indent=2))+'</pre></details>'+''.join(body)+'</html>'
    with staging(out) as tmp:
        write_json(tmp/'replayed.json',s);(tmp/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');(tmp/'report.html').write_text(page,encoding='utf-8')
        seal(tmp,{'schema_version':1,'kind':'rerank-report','parent_fingerprint':verify(root,'rerank-comparison')['fingerprint']})
    return {'status':'complete','model_requests':0,'report':'report.html','aggregates':s['aggregates']}
