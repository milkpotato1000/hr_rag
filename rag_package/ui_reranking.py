"""Registered-ID bridge to P020 core; no browser model paths or GT payloads."""
from . import candidates,reranking,rerank_compare
from .ui_registry import exact
from .storage import require,write_json,read_json,verify
from .documents import safe_id


def prepare(jobs,v):
    r=jobs.registry;kind=v['kind'];plan={}
    def get(key,expected):
        p,e,m=r.artifact(key);require(e['kind']==expected,'wrong_artifact_kind','input');return p,e,m
    if kind=='candidates':
        exact(v,('request_id','kind','answer_id','question_id','n'))
        p,e,m=get(v['answer_id'],'answer');b,_,_=get(e['build_id'],'build')
        require(safe_id(v['question_id']),'invalid_question_id','input')
        from .reranker import integer
        integer(v['n'],1,100);plan.update(answer=str(p),build=str(b),parent=m['fingerprint'])
    elif kind=='rerank_answer':
        exact(v,('request_id','kind','rerank_id','llm_config_id','execute'));require(type(v['execute']) is bool,'invalid_execute','input')
        p,e,m=get(v['rerank_id'],'rerank');data,_,_,_=reranking.load(p);require(data['status']=='complete','rerank_not_complete','input')
        plan.update(path=str(p),parent=m['fingerprint'],llm=jobs._llm(v['llm_config_id'],v['execute']))
    else:
        common=('request_id','kind','candidate_ids','top_k','context_budget_chars','execute_reranking','qrels_id','facts_id')
        exact(v,common+('method','reranker_id') if kind=='rerank' else common+('reranker_ids',))
        require(type(v['execute_reranking']) is bool,'invalid_execute','input')
        if v['execute_reranking']:require(jobs.allow_reranking,'reranking_execution_disabled','permission')
        ids=v['candidate_ids'];require(isinstance(ids,list) and 1<=len(ids)<=20 and all(isinstance(i,str) for i in ids) and len(ids)==len(set(ids)),'candidate_set_limit','input')
        loaded=[];qs=[]
        for key in ids:
            p,e,m=get(key,'candidates');c,docs,corpus=candidates.load(p)
            loaded.append({'path':str(p),'fingerprint':m['fingerprint'],'question_id':c['question_id']});qs.append({'id':c['question_id'],'question':c['question']})
        require(len({q['id'] for q in qs})==len(qs),'duplicate_question','input')
        if kind=='rerank':
            require(len(ids)==1,'single_candidate_required','input')
            require((v['reranker_id'] is None)==(v['method']=='none'),'reranker_profile_required_or_forbidden','input')
            variants=[{'id':'selected','label':'선택 설정','method':v['method'],'profile':r.reranker(v['reranker_id']) if v['reranker_id'] else None}]
        else:
            ids=v['reranker_ids'];require(isinstance(ids,list) and 1<=len(ids)<=3 and all(isinstance(i,str) for i in ids) and len(ids)==len(set(ids)),'reranker_variant_limit','input')
            variants=[{'id':'none','label':'none 기준선','method':'none','profile':None}]+[{'id':f'model-{n+1}','label':r.reranker(k)['model_id'],'method':'cross-encoder','profile':r.reranker(k)} for n,k in enumerate(ids)]
        qr=r.label('qrels',v['qrels_id']);facts=r.label('facts',v['facts_id'])
        for entry in loaded:
            c,docs,corpus=candidates.load(entry['path'])
            for variant in variants:reranking.settings(variant['method'],variant['profile'],v['top_k'],v['context_budget_chars'],c['requested_n'])
            reranking.validate_labels(c,docs,corpus,qs,qr,facts)
        require(len({(candidates.load(x['path'])[0]['source_fingerprint'],candidates.load(x['path'])[0]['chunk_fingerprint']) for x in loaded})==1,'mixed_corpus','input')
        plan.update(candidates=loaded,variants=variants,questions=qs,qrels=qr,facts=facts)
    return plan


def execute(jobs,v,plan,work):
    registry=jobs.registry;kind=v['kind'];dest=work/'result'
    if kind=='candidates':
        require(verify(plan['answer'],'answer')['fingerprint']==plan['parent'],'stale_artifact','jobs')
        result=candidates.freeze(plan['build'],plan['answer'],v['question_id'],v['n'],dest);artifact_kind='candidates';meta={}
    elif kind=='rerank_answer':
        require(verify(plan['path'],'rerank')['fingerprint']==plan['parent'],'stale_artifact','jobs')
        write_json(work/'llm.json',plan['llm'])
        result=reranking.answer(plan['path'],work/'llm.json',dest,execute=v['execute'],transport=jobs.transport,key_resolver=jobs.key_resolver);artifact_kind='rerank-answer';meta={}
    else:
        for c in plan['candidates']:require(verify(c['path'],'candidates')['fingerprint']==c['fingerprint'],'stale_artifact','jobs')
        if kind=='rerank':
            variant=plan['variants'][0]
            result=reranking.run(plan['candidates'][0]['path'],variant['method'],dest,profile=variant['profile'],top_k=v['top_k'],context_budget_chars=v['context_budget_chars'],execute=v['execute_reranking'],backend=jobs.reranker_backend,qrels=plan['qrels'],facts=plan['facts'],questions=plan['questions'])
            artifact_kind='rerank';meta={}
        else:
            write_json(work/'candidates-set.json',{'schema_version':1,'candidates':[{'question_id':c['question_id'],'path':c['path']} for c in plan['candidates']]})
            variants=[]
            for variant in plan['variants']:
                p=work/(variant['id']+'.json')
                if variant['profile']:write_json(p,variant['profile'])
                variants.append(dict(variant,profile=str(p) if variant['profile'] else None,top_k=v['top_k'],context_budget_chars=v['context_budget_chars']))
            write_json(work/'variants.json',{'schema_version':1,'variants':variants})
            result=rerank_compare.compare(work/'candidates-set.json',work/'variants.json',dest,qrels=plan['qrels'],facts=plan['facts'],execute=v['execute_reranking'],backend=jobs.reranker_backend)
            children={}
            for row in result['rows']:
                if row['result_path']:children[row['variant_id']+'/'+row['question_id']]=registry.add_artifact(dest/row['result_path'],'rerank')
            artifact_kind='rerank-comparison';meta={'rerank_ids':children}
    key=registry.add_artifact(dest,artifact_kind,**meta)
    return [key],'failed' if result.get('status')=='failed' else 'completed',result


def artifact(p,entry):
    kind=entry['kind']
    if kind=='candidates':
        c,_,_=candidates.load(p);return {'result':c}
    if kind=='rerank':
        r,c,_,_=reranking.load(p);return {'result':r,'candidate':c}
    if kind=='rerank-comparison':return {'result':rerank_compare.load(p),'rerank_ids':entry.get('rerank_ids',{})}
    r=read_json(p/'result.json');reranking.load(p/'rerank');return {'result':r}
