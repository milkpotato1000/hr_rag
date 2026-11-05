"""Offline adapter for LangChain request traces; never infer delivered evidence."""
import json
from evaluator import sha, digest, loads, unique_ids


def from_langchain(result, identity):
    t=result['trace'];p=t.get('prompt',{});g=t.get('generation',{})
    export=dict(schema_version='p013-generation-v1',**identity,question=t['question'],status=result['status'],
        answer=result['answer'],citations=result['citations'],retriever=t['retriever'],
        top_k=t['settings']['top_k'],max_context_chars=t['settings']['max_context_chars'],
        trace={k:t[k] for k in ('candidates','contexts','excluded')},prompt=p,
        generation=dict(request=g.get('request'),request_dispatched=g.get('request_dispatched',False),model_digest=g.get('digest')),
        usage=g.get('observations',{}),error=t.get('error'),reason=result.get('reason'),citation_validation=t.get('validation',[]))
    validate(export)
    export['export_sha256']=digest(export)
    return export


def validate(e):
    if e.get('schema_version')!='p013-generation-v1': raise ValueError('unknown generation version')
    required={'run_id','question_id','question','status','answer','citations','code_commit','source_canonical_sha256','chunk_run_id','chunks_sha256','index_fingerprint','retriever','top_k','max_context_chars','trace','prompt','generation','usage','error'}
    if not required<=set(e): raise ValueError('missing generation metadata')
    if 'export_sha256' in e and digest({k:v for k,v in e.items() if k!='export_sha256'})!=e['export_sha256']: raise ValueError('generation export hash mismatch')
    if e['retriever']!='dense' or e['top_k']!=5 or e['max_context_chars']!=8000: raise ValueError('unapproved retrieval configuration')
    ctx=e['trace']['contexts'];unique_ids(ctx,'chunk_id'); candidates=e['trace']['candidates'];unique_ids(candidates,'chunk_id')
    cmap={c['chunk_id']:c for c in candidates}
    for c in ctx:
        if c['chunk_id'] not in cmap or any(cmap[c['chunk_id']].get(k)!=v for k,v in c.items()): raise ValueError('context differs from retrieval snapshot')
    if sum(len(c['text']) for c in ctx)>8000: raise ValueError('context character budget')
    if e['prompt']:
        messages=e['prompt']['messages']
        if sha(json.dumps(messages,ensure_ascii=False))!=e['prompt']['messages_sha256']: raise ValueError('dispatch messages changed')
        if len(messages)!=2 or [m['role'] for m in messages]!=['system','user']: raise ValueError('unexpected generation messages')
        data=loads(messages[1]['content'])
        if data!={'question':e['question'],'contexts':ctx}: raise ValueError('actual transmitted contexts mismatch')
    if e['generation']['request_dispatched']:
        if not ctx or not e['prompt'] or not e['generation']['request']: raise ValueError('incomplete dispatched request')
    elif e['status']=='answered': raise ValueError('non-dispatched answer cannot be evaluated')
    if e['error'] or e.get('citation_validation') or e['usage'].get('done_reason')=='length': return 'failed_generation'
    if not e['generation']['request_dispatched']: return 'deterministic_no_context'
    return 'generated_abstention' if e['status']=='abstained' else 'generated_answer'


def source_review(review, export_hash, canonical, claims):
    """Consume a human-authored source judgement; do not invent approval."""
    if review.get('schema_version')!='p013-source-review-v1' or review.get('reviewer')!='human_project_owner' or review.get('export_sha256')!=export_hash: raise ValueError('source review identity mismatch')
    if review.get('source_canonical_sha256')!=sha(canonical) or not review.get('user_statement','').strip(): raise ValueError('source review approval missing')
    unique_ids(review['items'],'claim_id'); ids={c['id'] for c in claims}
    for row in review['items']:
        if row['claim_id'] not in ids or row['status'] not in ('other_source_supported','source_contradicted','unverifiable','irrelevant'): raise ValueError('source review claim/status')
        if row['status'] in ('other_source_supported','source_contradicted') and not row['evidence']: raise ValueError('source evidence required')
        for evidence in row['evidence']:
            if canonical[evidence['start']:evidence['end']]!=evidence['quote'] or sha(evidence['quote'])!=evidence['quote_sha256']: raise ValueError('source review quote mismatch')
    return {r['claim_id']:r for r in review['items']}
