"""Exact canonical interval coverage; AND spans, OR alternatives, no semantic judge."""
from .reranker import strict, integer
from .storage import require
from .documents import safe_id


def validate(value, source, questions_hash, questions, docs):
    strict(value, {'schema_version','source_fingerprint','questions_hash','offset_unit','questions'}, 'invalid_facts')
    require(type(value['schema_version']) is int and value['schema_version']==1 and value['offset_unit']=='unicode_codepoint','invalid_facts','evaluation')
    require(value['source_fingerprint']==source and value['questions_hash']==questions_hash,'facts_identity_mismatch','evaluation')
    require(isinstance(value['questions'],list),'invalid_facts','evaluation');seen=set();byid={d['document_id']:d for d in docs}
    for q in value['questions']:
        strict(q,{'question_id','required_facts'},'invalid_facts')
        require(safe_id(q['question_id']) and q['question_id'] not in seen,'invalid_fact_question','evaluation');seen.add(q['question_id'])
        require(isinstance(q['required_facts'],list) and len(q['required_facts'])<=100,'fact_limit','evaluation');ids=set()
        for f in q['required_facts']:
            strict(f,{'fact_id','alternatives'},'invalid_facts')
            require(safe_id(f['fact_id']) and f['fact_id'] not in ids,'duplicate_fact_id','evaluation');ids.add(f['fact_id'])
            require(isinstance(f['alternatives'],list) and 1<=len(f['alternatives'])<=4,'fact_limit','evaluation')
            for alt in f['alternatives']:
                strict(alt,{'spans'},'invalid_facts')
                require(isinstance(alt['spans'],list) and 1<=len(alt['spans'])<=8,'fact_limit','evaluation')
                for s in alt['spans']:
                    strict(s,{'document_id','start','end','quote'},'invalid_facts')
                    require(isinstance(s['document_id'],str) and s['document_id'] in byid,'unknown_fact_document','evaluation')
                    text=byid[s['document_id']]['text'];integer(s['start'],0,len(text)-1);integer(s['end'],s['start']+1,len(text))
                    require(isinstance(s['quote'],str) and s['quote']==text[s['start']:s['end']],'fact_quote_mismatch','evaluation')
    require(seen=={q['id'] for q in questions},'facts_question_mismatch','evaluation')
    return value


def coverage(rows, facts):
    intervals={}
    for r in rows:intervals.setdefault(r['document_id'],[]).append((r['start'],r['end']))
    def covered(s):
        cursor=s['start']
        for start,end in sorted(intervals.get(s['document_id'],[])):
            if end<=cursor:continue
            if start>cursor:break
            cursor=max(cursor,end)
            if cursor>=s['end']:return True
        return False
    fulfilled=[f['fact_id'] for f in facts if any(all(covered(s) for s in a['spans']) for a in f['alternatives'])]
    return {'fact_recall':len(fulfilled)/len(facts) if facts else None,'all_required':len(fulfilled)==len(facts) if facts else None,
            'fulfilled':len(fulfilled),'total':len(facts),'fulfilled_ids':fulfilled,'reason':None if facts else 'no_required_facts'}
