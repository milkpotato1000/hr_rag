"""Explicit complete chunk judgments; no answer/faithfulness evaluation."""
import math
from .llm.config import fields,ValidationError,read_json
from .storage import require,RagError

def validate_qrels(path,source,questions):
    value=read_json(path) if not isinstance(path,dict) else path
    try:fields(value,{'schema_version','source_fingerprint','chunk_fingerprint','questions_hash','judgments_complete','judgments'},set(),'qrels')
    except ValidationError:raise RagError('invalid_qrels','evaluation') from None
    require(type(value['schema_version']) is int and value['schema_version']==1 and type(value['judgments_complete']) is bool,'invalid_qrels','evaluation')
    require(value['source_fingerprint']==source and value['questions_hash']==questions,'qrels_identity_mismatch','evaluation')
    require(isinstance(value['judgments'],dict),'invalid_qrels','evaluation')
    for q,grades in value['judgments'].items():
        require(isinstance(q,str) and isinstance(grades,dict),'invalid_qrels','evaluation')
        require(all(isinstance(k,str) and type(g) is int and 0<=g<=2 for k,g in grades.items()),'invalid_qrels','evaluation')
    return value

def validate_corpus(value,build,chunks,questions):
    require(value['chunk_fingerprint']==build['identity']['chunk_fingerprint'],'qrels_chunk_mismatch','evaluation')
    require(set(value['judgments'])=={q['id'] for q in questions},'qrels_question_mismatch','evaluation')
    known={c['chunk_id'] for c in chunks}
    require(all(set(gs)<=known for gs in value['judgments'].values()),'qrels_unknown_chunk','evaluation')

def metrics(rows,grades,k,complete):
    require(len({r['chunk_id'] for r in rows})==len(rows),'duplicate_retrieval_id','evaluation')
    names=('precision','recall','mrr','ndcg')
    if not complete:return {'k':k,'values':{n:None for n in names},'reason':'judgments_incomplete'}
    values=[grades.get(r['chunk_id'],0) for r in rows[:k]];relevant=sum(g>0 for g in grades.values());hits=sum(g>0 for g in values)
    dcg=sum((2**g-1)/math.log2(n+2) for n,g in enumerate(values));ideal=sum((2**g-1)/math.log2(n+2) for n,g in enumerate(sorted(grades.values(),reverse=True)[:k]))
    return {'k':k,'returned':len(values),'group':'answerable' if relevant else 'no_answer','reason':None if relevant else 'no_relevant','values':{
        'precision':hits/k,'recall':hits/relevant if relevant else None,'mrr':next((1/(n+1) for n,g in enumerate(values) if g>0),0) if relevant else None,'ndcg':dcg/ideal if ideal else None}}

def aggregate(rows,*,split_groups=True):
    result={}
    for config in sorted({r['config_id'] for r in rows}):
        selected=[r for r in rows if r['config_id']==config];out={}
        for name in ('precision','recall','mrr','ndcg'):
            values=[];excluded={}
            for row in selected:
                metric=row.get('metrics',{}).get('retrieval',{});v=metric.get('values',{}).get(name)
                reason='failed' if row['status']=='failed' else metric.get('reason') or 'not_measured'
                if row['status']!='failed' and v is not None:values.append(v)
                else:excluded[reason]=excluded.get(reason,0)+1
            out[name]={'value':sum(values)/len(values) if values else None,'valid':len(values),'excluded':sum(excluded.values()),'exclusion_reasons':excluded}
        if split_groups:
            out['groups']={group:aggregate([r for r in selected if r.get('metrics',{}).get('retrieval',{}).get('group')==group],split_groups=False).get(config,{}) for group in ('answerable','no_answer')}
        result[config]=out
    return result
