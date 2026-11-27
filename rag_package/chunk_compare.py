"""Source-span comparisons across frozen boundaries; replay never runs a model."""
from pathlib import Path
from .storage import require,read_json,fingerprint,verify,seal,staging,write_json,safe_path
from . import chunk_artifact,fact_metrics,search_metrics
from .documents import load_snapshot
from .candidates import ranking,copy_artifact
from .retrieval import load_build


def preflight(snapshot,checked,settings,qs,facts):
    sm,docs=load_snapshot(snapshot)
    require(all(all(s[k]==settings[0][k] for k in ('retrieval','embedding','llm')) for s in settings),'comparison_axes_mismatch','compare')
    for c,_ in checked:
        r,_,_,_=chunk_artifact.load(c['chunk_artifact']);require(r['source_fingerprint']==sm['fingerprint'],'stale_chunk_source','compare')
    if facts is not None:fact_metrics.validate(read_json(facts) if isinstance(facts,(str,Path)) else facts,sm['fingerprint'],fingerprint(qs),qs,docs)


def qrels_map(value,checked,qs,source):
    if value is None:return {}
    value=read_json(value) if isinstance(value,(str,Path)) else value
    require(isinstance(value,dict) and set(value)=={'schema_version','by_chunk_fingerprint'} and type(value['schema_version']) is int and value['schema_version']==1 and isinstance(value['by_chunk_fingerprint'],dict),'qrels_map_required','compare')
    artifacts={}
    for c,_ in checked:
        r,_,cs,_=chunk_artifact.load(c['chunk_artifact']);artifacts[r['chunk_fingerprint']]=cs
    require(set(value['by_chunk_fingerprint'])<=set(artifacts),'qrels_chunk_mismatch','compare')
    for fp,q in value['by_chunk_fingerprint'].items():
        search_metrics.validate_qrels(q,source,fingerprint(qs));require(q['chunk_fingerprint']==fp and set(q['judgments'])=={x['id'] for x in qs} and all(set(grades)<={c['chunk_id'] for c in artifacts[fp]} for grades in q['judgments'].values()),'qrels_chunk_mismatch','compare')
    return value['by_chunk_fingerprint']


def facts_for(result,chunks,docs,value,qs,qid):
    value=read_json(value) if isinstance(value,(str,Path)) else value
    f=fact_metrics.validate(value,result['source_fingerprint'],fingerprint(qs),qs,docs)
    facts=next(q['required_facts'] for q in f['questions'] if q['question_id']==qid)
    byid={c['chunk_id']:c for c in chunks}
    full=ranking(result,chunks)
    return {level:fact_metrics.coverage(rows,facts) for level,rows in (
        ('candidate',[byid[r['chunk_id']] for r in full]),('top_k',[byid[r['chunk_id']] for r in result['candidates']]),('contexts',result['contexts']))}


def aggregate(rows,ids):
    out={}
    for id in ids:
        group=[r for r in rows if r['config_id']==id];out[id]={}
        for level in ('candidate','top_k','contexts'):
            valid=[r['metrics'].get('facts',{}).get(level) for r in group if r['status']!='failed'];valid=[f for f in valid if f and f['total']>0]
            total=sum(f['total'] for f in valid);hit=sum(f['fulfilled'] for f in valid)
            out[id][level]={'macro':sum(f['fact_recall'] for f in valid)/len(valid) if valid else None,'micro':hit/total if total else None,'all_required_rate':sum(f['all_required'] for f in valid)/len(valid) if valid else None,
                'fulfilled':hit,'total_facts':total,'valid':len(valid),'questions':len(group),'failed':sum(r['status']=='failed' for r in group),'no_required_facts':sum(r.get('metrics',{}).get('facts',{}).get(level,{}).get('reason')=='no_required_facts' for r in group),'excluded':len(group)-len(valid)}
    return out


def describe(path):
    r,_,_,_=chunk_artifact.load(path)
    return {k:r[k] for k in ('chunk_fingerprint','config','statistics','work','source_fingerprint')}


def load(root):
    root=Path(root);m=verify(root,'comparison');s=read_json(root/'comparison.json');sm,docs=load_snapshot(root/'snapshot');facts=read_json(root/'facts.json');qrels=read_json(root/'qrels.json')
    require(s.get('comparison_axis')=='frozen_chunk_artifact' and s['boundary_inference_calls']==0 and s['source_fingerprint']==sm['fingerprint']==m['identity']['source_fingerprint'] and s['questions_hash']==fingerprint(s['questions'])==m['identity']['questions_hash'],'stale_comparison','compare')
    configs=s['configs'];qs=s['questions'];require(2<=len(configs)<=5 and 1<=len(qs)<=20,'invalid_comparison','compare')
    ids=[c['id'] for c in configs];qids=[q['id'] for q in qs];require(len(set(ids))==len(ids) and len(set(qids))==len(qids),'duplicate_comparison_ids','compare')
    require(len(s['rows'])==len(ids)*len(qids) and {(r['config_id'],r['question_id']) for r in s['rows']}=={(c,q) for c in ids for q in qids},'comparison_pair_mismatch','compare')
    require(all(all(c['settings'][k]==configs[0]['settings'][k] for k in ('retrieval','embedding','llm')) for c in configs),'comparison_axes_mismatch','compare')
    if facts is not None:fact_metrics.validate(facts,sm['fingerprint'],fingerprint(qs),qs,docs)
    for i,c in enumerate(configs):
        require(c['id']==f'config-{i+1}' and c['hash']==fingerprint(c['settings']) and c['settings']['schema_version']==3,'stale_comparison_config','compare')
        build=next(b for b in s['builds'] if b['config_id']==c['id'])
        if build['status']!='ready':continue
        bm,bd,cs=load_build(root/c['id']/'build',c['settings']);require(bm['identity']['source_fingerprint']==sm['fingerprint'],'stale_comparison_source','compare')
        require(s['chunk_artifacts'][i]==describe(root/c['id']/'build/frozen-chunks'),'stale_chunk_description','compare')
        for row in (r for r in s['rows'] if r['config_id']==c['id']):
            if 'result_path' not in row:require(row['status']=='failed','missing_result','compare');continue
            expected=f"{c['id']}/answers/{row['question_id']}/result.json";require(row['result_path']==expected,'comparison_result_mismatch','compare')
            file=safe_path(root,expected);rm=verify(file.parent,'answer');r=read_json(file)
            question=next(q['question'] for q in qs if q['id']==row['question_id'])
            require(r['question']==question and r['query_hash']==fingerprint(question)==rm['identity']['query_hash'] and r['effective_settings']==c['settings'] and r['config_hash']==c['hash'],'comparison_result_mismatch','compare')
            require(all(r[k]==bm['identity'][k] for k in ('source_fingerprint','chunk_fingerprint','index_fingerprint')),'comparison_result_mismatch','compare')
            ranking(r,cs)
            byid={x['chunk_id']:x for x in cs};contexts=[];excluded=[];used=0
            for candidate in r['candidates']:
                chunk=byid[candidate['chunk_id']]
                if used+len(chunk['text'])>c['settings']['retrieval']['context_budget_chars']:excluded.append(dict(candidate,reason='budget'))
                else:contexts.append(chunk);used+=len(chunk['text'])
            require(r['contexts']==contexts and r['excluded']==excluded,'stale_comparison_contexts','compare')
            if facts is not None:require(r['metrics']['facts']==facts_for(r,cs,bd,facts,qs,row['question_id']),'stale_fact_metrics','compare')
            if r['chunk_fingerprint'] in qrels:
                qr=search_metrics.validate_qrels(qrels[r['chunk_fingerprint']],sm['fingerprint'],fingerprint(qs))
                require(r['metrics']['retrieval']==search_metrics.metrics(r['candidates'],qr['judgments'][row['question_id']],c['settings']['retrieval']['top_k'],qr['judgments_complete']),'stale_search_metrics','compare')
            require(all(row[k]==r[k] for k in ('status','metrics','usage','dispatch_attempted','execution_kind','source_fingerprint','latency_ms')),'comparison_detail_mismatch','compare')
    require(s['fact_aggregates']==aggregate(s['rows'],ids),'stale_fact_aggregates','compare')
    return s


def report(root,out):
    import html,json
    s=load(root)
    with staging(out) as tmp:
        write_json(tmp/'comparison.json',s)
        rows=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in (r['config_id'],r['question_id'],r['status'],r['metrics'].get('facts',{}).get('contexts',{}).get('fact_recall','N/A')) )+'</tr>' for r in s['rows'])
        text='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>청킹 비교</title><style>body{font-family:system-ui;max-width:1000px;margin:auto;padding:20px;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px}pre{white-space:pre-wrap}</style><h1>저장된 청크 비교</h1><p>경계 모델 재실행 0. 원문 span 회수는 답변 정답 판정과 별개입니다. 실행 출처: '+html.escape(s['execution_kind'])+'</p><table><tr><th>설정</th><th>질문</th><th>상태</th><th>문맥 fact 회수</th></tr>'+rows+'</table><details><summary>집계·실행 기록</summary><pre>'+html.escape(json.dumps(s,ensure_ascii=False,indent=2))+'</pre></details>'
        (tmp/'report.html').write_text(text,encoding='utf-8');seal(tmp,{'schema_version':1,'kind':'chunk-report','model_calls':0})
    return {'status':'complete','model_calls':0,'fact_aggregates':s['fact_aggregates']}
