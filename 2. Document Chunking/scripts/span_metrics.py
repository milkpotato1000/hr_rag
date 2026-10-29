"""Source-span OR/AND evidence metrics, independent of retrievers and model input."""
import math
from experiment_common import need

def merge(spans):
    result=[]
    for a,b in sorted(spans):
        need(type(a)==int and type(b)==int and 0<=a<b,'invalid_offset','Invalid evidence interval')
        if result and a<=result[-1][1]:result[-1]=(result[-1][0],max(b,result[-1][1]))
        else:result.append((a,b))
    return result

def grouped(spans):
    out={}
    for s in spans:out.setdefault(s['document_id'],[]).append((s['start'],s['end']))
    return {did:merge(ss) for did,ss in out.items()}

def overlap_length(a,b):
    return sum(max(0,min(y,v)-max(x,u)) for x,y in merge(a) for u,v in merge(b))

def coverage(evidence,found):
    required=grouped(evidence);recovered=grouped(found)
    total=sum(b-a for spans in required.values() for a,b in spans)
    need(total>0,'invalid_evidence','Empty required evidence')
    matched=sum(overlap_length(spans,recovered.get(did,[])) for did,spans in required.items())
    return matched,total

def fact_result(fact,found):
    need(bool(fact['evidence_sets']),'invalid_evidence','Fact has no evidence sets')
    candidates=[coverage(s,found) for s in fact['evidence_sets']]
    return dict(complete=any(a==b for a,b in candidates),partial=max(a/b for a,b in candidates))

def grade(chunk,facts,texts):
    if any(fact_result(f,[chunk])['complete'] for f in facts):return 2
    for f in facts:
        for ss in f['evidence_sets']:
            for s in ss:
                if s['document_id']!=chunk['document_id']:continue
                a,b=max(chunk['start'],s['start']),min(chunk['end'],s['end'])
                if a<b and texts[s['document_id']][a:b].strip():return 1
    return 0

def evaluate(question,facts,maps,ranking,k,texts):
    if question is None:return dict(status='N/A',reason='no_registered_ground_truth')
    required=[facts[f] for f in question['required_fact_ids']]
    if question['answerability']!='answerable' or not required:return dict(status='N/A',reason='unanswerable_document_scope',required_facts=0)
    byid={m['chunk_id']:m for m in maps};need(all(cid in byid for cid in ranking),'invalid_ranking','Unknown chunk ID')
    grades={cid:grade(m,required,texts) for cid,m in byid.items()};seen=set();top=[];scores=[]
    for cid in ranking[:k]:
        if cid in seen:scores.append(0);continue
        seen.add(cid);top.append(byid[cid]);scores.append(grades[cid])
    results=[fact_result(f,top) for f in required];n=sum(r['complete'] for r in results);den=len(required)
    relevant=sum(g>0 for g in grades.values());hits=sum(g>0 for g in scores)
    dcg=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(scores));ideal=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(sorted(grades.values(),reverse=True)[:k]))
    return dict(status='ok',fact_recall=n/den,full_evidence_success=int(n==den),partial_coverage=sum(r['partial'] for r in results)/den,matched_facts=n,required_facts=den,
        precision=hits/k,recall=hits/relevant if relevant else None,mrr=next((1/(i+1) for i,g in enumerate(scores) if g>0),0),ndcg=dcg/ideal if ideal else None,
        relevant_corpus_chunks=relevant,returned=min(len(ranking),k),k=k,qrels=grades)

def select_budget(ranking,chunks,budget):
    selected=[];excluded=[];used=0;seen=set()
    for cid in ranking[:20]:
        length=len(chunks[cid]['text'])
        if cid in seen:excluded.append(dict(chunk_id=cid,reason='duplicate'));continue
        seen.add(cid)
        if used+length>budget:excluded.append(dict(chunk_id=cid,reason='whole_chunk_exceeds_remaining_budget',chars=length));continue
        selected.append(cid);used+=length
    return dict(kind='context_budget_simulation',selected=selected,excluded=excluded,used_chars=used,budget_chars=budget,actually_sent_to_llm=False)

def aggregate(rows):
    valid=[r for r in rows if r.get('status')=='ok'];keys=['fact_recall','full_evidence_success','partial_coverage','precision','recall','mrr','ndcg'];out={'valid_queries':len(valid),'na_queries':sum(r.get('status')=='N/A' for r in rows),'error_queries':sum(r.get('status') not in ('ok','N/A') for r in rows),'total_queries':len(rows)}
    for k in keys:
        values=[r[k] for r in valid if r[k] is not None];out[k]={'macro':sum(values)/len(values) if values else None,'denominator':len(values)}
    den=sum(r['required_facts'] for r in valid);out['fact_recall_micro']={'value':sum(r['matched_facts'] for r in valid)/den if den else None,'matched':sum(r['matched_facts'] for r in valid),'required':den}
    return out

def stability(runs,forced,end):
    sets=[set(x)-set(forced)-{0,end} for x in runs];pairs=[]
    for i,a in enumerate(sets):
        for j,b in enumerate(sets[i+1:],i+1):pairs.append(dict(a=i,b=j,exact=a==b,jaccard=len(a&b)/len(a|b) if a|b else 1.0))
    return dict(successful_repetitions=len(runs),pairs=pairs,pair_denominator=len(pairs),exact_pair_rate=sum(p['exact'] for p in pairs)/len(pairs) if pairs else None,mean_jaccard=sum(p['jaccard'] for p in pairs)/len(pairs) if pairs else None,excluded_forced_boundaries=len(set(forced)))
