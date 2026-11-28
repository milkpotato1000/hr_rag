"""Invoke only the supplied first window and validate its source coverage."""
from rag_package import chunk_policy, llm
from rag_package.storage import RagError

def evaluate(window,profile,send):
    if window['id']!='w000':
        raise ValueError('first window required')
    units=window['units']
    messages=chunk_policy.messages(units,192)
    if messages!=window['messages']:
        raise ValueError('messages changed')
    response=llm.invoke(profile,'chunking',messages,transport=send)
    result={'status':'failed','actual_messages_hash':response['actual_messages_hash'],
            'provider_result':{k:response[k] for k in ('status','usage','finish_reason','elapsed_ms','identity_verification','outcome_unknown')},
            'selected_end_ids':None,'spans':None,'error':None}
    if response['status']!='complete':
        result['error']='provider_'+response['status']
        return result
    try:
        spans=chunk_policy.parse(response['parsed_json'],units,192)
    except RagError as exc:
        result['error']=exc.code
        return result
    cursor=units[0]['start']
    for span in spans:
        if span['document_id']!=units[0]['document_id'] or span['start']!=cursor or not 0<span['end']-cursor<=192:
            raise ValueError('coverage mismatch')
        cursor=span['end']
    if cursor!=units[-1]['end']:
        raise ValueError('incomplete coverage')
    result.update(status='valid_window',spans=spans,selected_end_ids=response['parsed_json']['end_unit_ids'])
    return result
