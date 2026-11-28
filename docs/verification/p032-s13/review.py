"""Produce portable evidence using only sealed, already-finished results."""
from pathlib import Path
import json
import os
import subprocess
import sys
from unittest.mock import patch

from experiment import E, S11, base, old, out, private, quote, read, write, need, audit, rt

if __name__=='__main__':
    python=base/'env/bin/python'
    if Path(sys.executable)!=python:
        # Isolated interpreter for imports; permit this verification module explicitly.
        os.execv(python,[str(python),__file__])
    from rag_package import pipeline
    inputs=read(E/'inputs.json')
    audit()
    need(inputs==read(E/'inputs.json'),'baseline_evidence_changed')
    before=[rt.sha(p/'manifest.json') for p in (old,out)]
    command=[str(base/'env/bin/rag-lab'),'pipeline-compare','--runs',str(old),str(out)]
    pair=json.loads(subprocess.check_output(command,cwd=base,text=True))
    with patch('rag_package.llm.invoke',side_effect=AssertionError('unexpected generation')):
        need(pair==pipeline.compare(old,out),'replay_changed')
    need(pair['same_source'] and pair['same_question'] and pair['interpretation']=='incomplete_settings','legacy_status_changed')
    need(before==[rt.sha(p/'manifest.json') for p in (old,out)],'replay_changed_inputs')
    observations=[]
    for side,path in zip(pair['runs'],(old,out)):
        result=read(path/'answer/result.json')
        provider=result['provider_result']
        canonical=(path/'snapshot/handbook/canonical.txt').read_text()
        page=(path/'snapshot/handbook/page-1.txt').read_text()
        assert quote in page
        ranks=[i for i,c in enumerate(side['contexts'],1) if quote in c['text']]
        answer=result.get('answer') or {}
        checked=[]
        for cite in answer.get('citations',[]):
            same=canonical[cite['start']:cite['end']]==cite['quote']
            same_context=any(c['chunk_id']==cite['chunk_id'] and c['text']==cite['quote'] for c in side['contexts'])
            need(same and same_context,'citation_changed')
            checked.append(dict(chunk_id=cite['chunk_id'],source_matches=same,contains_rule=quote in cite['quote'],
                                pages=[p['page'] for p in cite['pages']],start=cite['start'],end=cite['end']))
        observations.append(dict(status=result['status'],answer=answer.get('answer'),bd03_ranks=ranks,
                                 contexts=len(side['contexts']),citations=checked,identity=provider['identity_verification'],
                                 elapsed_ms=provider['elapsed_ms'],usage=provider['usage']))
    ledger=read(rt.LEDGER)
    need(len(ledger['requests'])==1 and ledger['requests'][0]['body_hash']==inputs['expected_recursive_body_sha256'],'dispatch_count_or_body')
    resources=[json.loads(line) for line in (private/'resources.jsonl').read_text().splitlines()]
    report=dict(question=pair['runs'][0]['question'],quote=quote,observations=observations,
                comparison_model_calls=pair['comparison_model_calls'],interpretation=pair['interpretation'],
                ledger=ledger,peak_observed_rss_bytes=max(x['rss_bytes'] for x in resources),
                observed_pressure_levels=sorted({x['pressure'] for x in resources}),
                server_closed=read(private/'server-closed.json'),cleanup=read(private/'first-observation.json'))
    for name,data in [('comparison.json',pair),('observations.json',report)]:
        wire=json.dumps(data,ensure_ascii=False)
        need(not any(s in wire for s in ('/Users/','/private/var/','/private/tmp/','Bearer ')),'nonportable_output')
        write(E/name,data)
    print(json.dumps(observations,ensure_ascii=False))
