"""Immutable candidate reranking, selection, and source-grounded generation."""
from pathlib import Path
import time
from . import candidates, reranker, search_metrics, fact_metrics, llm
from .storage import require, RagError, fingerprint, read_json, write_json, seal, verify, staging, new_output
from .documents import intersections


def settings(method, profile, k, budget, requested_n):
    require(method in ('none','cross-encoder'),'unsupported_reranker','reranking')
    require((profile is None)==(method=='none'),'reranker_profile_required_or_forbidden','reranking')
    p=reranker.read_profile(profile) if isinstance(profile,(str,Path)) else reranker.profile(profile) if profile is not None else None
    reranker.integer(k,1,requested_n);reranker.integer(budget,1,64000)
    return p


def select(rows, scores, k, budget):
    byscore={r['chunk_id']:r['score'] for r in scores} if scores is not None else None
    ranked=sorted(rows,key=lambda r:(-byscore[r['chunk_id']],r['original_rank'],r['chunk_id'])) if byscore is not None else rows
    ranked=[dict(r,rank=i+1,rank_delta=r['original_rank']-i-1,reranker_score=byscore[r['chunk_id']] if byscore is not None else None) for i,r in enumerate(ranked)]
    contexts=[];excluded=[];used=0
    for row in ranked[:k]:
        if used+len(row['text'])>budget:excluded.append(dict(row,reason='budget'))
        else:contexts.append(row);used+=len(row['text'])
    return {'ranking':ranked,'top_k':ranked[:k],'contexts':contexts,'excluded':excluded,'used_chars':used}


def validate_labels(c, docs, corpus, questions, qrels, facts):
    qh=fingerprint(questions)
    if qrels is not None:
        qrels=search_metrics.validate_qrels(qrels,c['source_fingerprint'],qh)
        search_metrics.validate_corpus(qrels,{'identity':{'chunk_fingerprint':c['chunk_fingerprint']}},corpus,questions)
    if facts is not None:
        facts=read_json(facts) if not isinstance(facts,dict) else facts
        fact_metrics.validate(facts,c['source_fingerprint'],qh,questions,docs)
    return qrels,facts


def evaluate(c, selected, k, qrels=None, facts=None):
    result={'faithfulness':{'value':None,'reason':'evaluator_not_connected'},'correctness':{'value':None,'reason':'evaluator_not_connected'}}
    if qrels is None:
        result.update(retrieval={'values':{n:None for n in ('precision','recall','mrr','ndcg')},'reason':'qrels_not_configured'},candidate_recall=None,context_recall=None)
    else:
        grades=qrels['judgments'][c['question_id']];complete=qrels['judgments_complete']
        result['retrieval']=search_metrics.metrics(selected['top_k'],grades,k,complete)
        result['candidate_recall']=search_metrics.metrics(c['rows'],grades,c['requested_n'],complete)['values']['recall']
        result['context_recall']=search_metrics.metrics(selected['contexts'],grades,max(1,len(selected['contexts'])),complete)['values']['recall']
    result['facts']={}
    required=next((q['required_facts'] for q in facts['questions'] if q['question_id']==c['question_id']),[]) if facts else []
    for name,rows in [('candidate',c['rows']),('top_k',selected['top_k']),('contexts',selected['contexts'])]:
        result['facts'][name]=fact_metrics.coverage(rows,required) if facts else {'fact_recall':None,'all_required':None,'fulfilled':0,'total':0,'fulfilled_ids':[],'reason':'facts_not_configured'}
    return result


def run(candidate_dir,method,out,*,profile=None,top_k=5,context_budget_chars=4000,execute=False,backend=None,qrels=None,facts=None,questions=None):
    new_output(out);c,docs,corpus=candidates.load(candidate_dir)
    p=settings(method,profile,top_k,context_budget_chars,c['requested_n'])
    questions=questions or [{'id':c['question_id'],'question':c['question']}]
    require(any(q=={'id':c['question_id'],'question':c['question']} for q in questions),'question_identity_mismatch','reranking')
    qrels,facts=validate_labels(c,docs,corpus,questions,qrels,facts)
    r={'schema_version':1,'candidate_fingerprint':c['candidate_fingerprint'],'question_id':c['question_id'],'question':c['question'],
       'candidate_execution_kind':c['execution_kind'],'method':method,'profile_identity':reranker.identity(p) if p else None,'execution_settings':{k:p[k] for k in ('batch_size','timeout_seconds')} if p else None,
       'top_k_limit':top_k,'context_budget_chars':context_budget_chars,'status':'complete','reason':None,'error':None,'scores':None,'selection':None,'metrics':None,
       'questions':questions,'qrels':qrels,'facts':facts,'expected_pairs':len(c['rows']) if p else 0,'original_retrieval_ms':c['original_retrieval_ms'],
       'work':{'pairs':0,'queries':0,'workers':0,'fixture_calls':0,'retry_count':0,'worker_exited':True,'execution_kind':'none' if not p else 'preview','elapsed_ms':0,'peak_rss_bytes':None,'rss_method':'unavailable'}}
    dispatched=False;started=time.monotonic()
    try:
        with staging(out) as tmp:
            candidates.copy_artifact(candidate_dir,tmp/'candidates','candidates')
            if p and (not execute or not reranker.configured(p)):
                r.update(status='preview',reason='execution_not_enabled' if not execute else 'reranker_configuration_required')
            elif p and c['rows']:
                try:
                    r['scores'],r['work']=reranker.score(p,c['question'],c['rows'],backend=backend)
                    dispatched=bool(r['work']['workers'] or r['work']['fixture_calls'])
                except (RagError,OSError,UnicodeError) as e:
                    r.update(status='failed',error={'code':getattr(e,'code','reranker_io_failed'),'offending_ids':getattr(e,'offending_ids',[])})
                    r['work']=getattr(e,'work',r['work']);dispatched=getattr(e,'dispatch_attempted',False)
            if r['status']=='complete':
                if p and not c['rows']:r['scores']=[]
                r['selection']=select(c['rows'],r['scores'],top_k,context_budget_chars)
                r['metrics']=evaluate(c,r['selection'],top_k,qrels,facts)
            r['scorer_identity']={'profile':r['profile_identity'],'sdk_versions':r['work'].get('sdk_versions'),'execution_kind':r['work']['execution_kind']}
            r['fact_locations']=[dict(span,pages=intersections(next(d['pages'] for d in docs if d['document_id']==span['document_id']),span['start'],span['end'])) for q in (facts or {}).get('questions',[]) if q['question_id']==c['question_id'] for fact in q['required_facts'] for alt in fact['alternatives'] for span in alt['spans']]
            r['total_ms']=(time.monotonic()-started)*1000
            write_json(tmp/'result.json',r);seal(tmp,{'schema_version':1,'kind':'rerank','status':r['status'],'candidate_fingerprint':c['candidate_fingerprint']})
    except (RagError,OSError,UnicodeError) as e:
        err=e if isinstance(e,RagError) else RagError('output_write_failed','publish');err.dispatch_attempted=dispatched;raise err from None
    return r


def load(root):
    root=Path(root);m=verify(root,'rerank');r=read_json(root/'result.json');c,docs,corpus=candidates.load(root/'candidates')
    require(r['candidate_fingerprint']==c['candidate_fingerprint']==m['identity']['candidate_fingerprint'] and r['status']==m['identity']['status'],'stale_rerank','reranking')
    require(r['candidate_execution_kind']==c['execution_kind'],'stale_provenance','reranking')
    require(r['question_id']==c['question_id'] and r['question']==c['question'],'stale_rerank','reranking')
    reranker.integer(r['top_k_limit'],1,c['requested_n']);reranker.integer(r['context_budget_chars'],1,64000)
    validate_labels(c,docs,corpus,r['questions'],r['qrels'],r['facts'])
    require(r['scorer_identity']=={'profile':r['profile_identity'],'sdk_versions':r['work'].get('sdk_versions'),'execution_kind':r['work']['execution_kind']},'stale_scorer_identity','reranking')
    require(r['method'] in ('none','cross-encoder'),'stale_rerank','reranking')
    if r['status']=='complete':
        if r['method']=='cross-encoder':reranker.validate_scores({'scores':r['scores']},[x['chunk_id'] for x in c['rows']])
        else:require(r['scores'] is None,'stale_scores','reranking')
        expected=select(c['rows'],r['scores'],r['top_k_limit'],r['context_budget_chars'])
        require(r['selection']==expected and r['metrics']==evaluate(c,expected,r['top_k_limit'],r['qrels'],r['facts']),'stale_rerank_metrics','reranking')
    else:require(r['status'] in ('preview','failed') and r['selection'] is None and r['metrics'] is None,'invalid_rerank_status','reranking')
    return r,c,docs,corpus


def answer(run_dir,llm_config,out,*,execute=False,transport=None,key_resolver=None):
    from .rag import messages_for,business_answer,PROMPT_VERSION
    new_output(out);r,c,docs,_=load(run_dir);require(r['status']=='complete','rerank_not_complete','generation')
    lc=llm.validate_config(read_json(llm_config));require(lc['profiles'][lc['roles']['generation']]['response_mode']=='json_object','json_object_required','generation')
    contexts=r['selection']['contexts'];messages=messages_for(c['question'],contexts,docs);preview=llm.preview(lc,'generation',messages)
    result={'schema_version':1,'status':'preview','parent_rerank_fingerprint':verify(run_dir,'rerank')['fingerprint'],'candidate_fingerprint':c['candidate_fingerprint'],
            'candidate_execution_kind':c['execution_kind'],'scorer_execution_kind':r['work']['execution_kind'],'question':c['question'],'source_fingerprint':c['source_fingerprint'],'contexts':contexts,'messages':messages,'messages_hash':fingerprint(messages),
            'actual_messages_hash':preview['actual_messages_hash'],'prompt_version':PROMPT_VERSION,'preview':preview,'answer':None,'provider_result':None,
            'dispatch_attempted':False,'generation_requests':0,'failed_stage':None,'error':None,'execution_kind':'test_fixture' if transport else ('live' if execute else 'preview')}
    try:
        with staging(out) as tmp:
            candidates.copy_artifact(run_dir,tmp/'rerank','rerank')
            if not contexts:result.update(status='abstained',answer={'status':'abstained','answer':'제공할 근거가 없어 답변을 보류합니다.','citations':[]})
            elif execute:
                response=llm.invoke(lc,'generation',messages,transport=transport,key_resolver=key_resolver)
                result.update(provider_result={k:v for k,v in response.items() if k not in ('content','parsed_json')},dispatch_attempted=response['dispatch_attempted'],generation_requests=int(response['dispatch_attempted']))
                if response['status']!='complete':result.update(status='failed',failed_stage='provider',error={'code':'provider_'+response['status']})
                else:
                    try:
                        result['answer']=business_answer(response['parsed_json'],contexts);result['status']=result['answer']['status']
                    except RagError as e:result.update(status='failed',failed_stage=e.stage,error={'code':e.code})
            write_json(tmp/'result.json',result);seal(tmp,{'schema_version':1,'kind':'rerank-answer','source_fingerprint':c['source_fingerprint'],'status':result['status']})
    except (RagError,OSError,UnicodeError) as e:
        err=e if isinstance(e,RagError) else RagError('output_write_failed','publish');err.dispatch_attempted=result['dispatch_attempted'];raise err from None
    return result
