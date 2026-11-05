"""Create an immutable, approval-bound P013 experiment without model calls."""
import argparse
import gzip
import shutil
import subprocess
from pathlib import Path
from evaluator import read, write, digest, sha, payload, PACKET, POLICY, unique_ids
from tokenization import QwenTokenizer

ROOT=Path(__file__).resolve().parents[2]
PREP='evaluation/project_b/preparation/artifacts/run004'
APPROVAL='docs/planning/reviews/P013-human-approval.json'
REVIEW='docs/planning/reviews/P013-human-review-manifest.json'


def approval_check(root):
    a=read(root/APPROVAL); m=read(root/REVIEW); p=read(root/PREP/'packet.json')
    if a['status']!='APPROVED' or a['reviewer']!='human_project_owner' or not a['user_statement'].strip(): raise ValueError('human approval required')
    if a['review_manifest']!=REVIEW or sha((root/REVIEW).read_bytes())!=a['review_manifest_sha256']: raise ValueError('review manifest changed')
    if a['scope']!=m['scope'] or a['approved_files']!=m['files']: raise ValueError('approval scope mismatch')
    for path,h in a['approved_files'].items():
        if Path(path).is_absolute() or '..' in Path(path).parts or sha((root/path).read_bytes())!=h: raise ValueError('approved input changed: '+path)
    if p['packet_sha256']!=PACKET or digest({k:v for k,v in p.items() if k!='packet_sha256'})!=PACKET: raise ValueError('packet changed')
    if a['run004_packet_sha256']!=PACKET or m['run004_packet_file_sha256']!=sha((root/PREP/'packet.json').read_bytes()): raise ValueError('wrong approved packet')
    if a['scope']['questions']!=[q['id'] for q in p['questions']] or a['scope']['judge_ids']!=[q['id'] for q in p['judgements']]: raise ValueError('approved IDs mismatch')
    if p['human_approval'] is not None: raise ValueError('historical packet approval mutated')
    return a,p


def make_cases(root, packet):
    cases=[]; expectations={}
    def add(case_id,stage,role,data,expected):
        body=payload(role,data)
        for repetition in (1,2):
            cid=f'{case_id}-r{repetition}'
            cases.append(dict(id=cid,fixture_id=case_id,stage=stage,role=role,repetition=repetition,data=data,payload=body,payload_sha256=digest(body)))
            expectations[cid]=expected
    extraction=read(root/'docs/planning/specs/P013-fixed-extraction-candidates.json')
    for c in extraction['cases']:
        if sha(c['fixed_answer'])!=c['answer_sha256']: raise ValueError('fixed answer changed')
        add(c['id'],'extraction','extraction',dict(question=c['question'],answer=c['fixed_answer']),c)
    for c in packet['judgements']:
        add(c['id'],'judge','judge',dict(claims=[dict(id=c['id'],text=c['claim'])],contexts=[dict(id='ctx',text=c['premise'])]),
            dict(labels={c['id']:{'E':'entailment','N':'neutral','C':'contradiction'}[c['proposed_label']]}))
    for c in read(root/'docs/planning/specs/P013-matching-candidates.json')['cases']:
        add(c['id'],'judge','matching',dict(question=c['question'],intents=[dict(id='intent',text=c['question'],required_claim_ids=['ref'])],
            reference=[dict(id='ref',text=c['reference'],role='required')],claims=[dict(id='g',text=c['generated'])]),dict(pairs={'g:ref':c['expected_label']}))
    s=read(root/'docs/planning/specs/P013-evaluator-scenarios-draft.json')
    for c in s['cases']:
        claims=[g for g in s['generated_claim_pool'] if g['id'] in c['generated_claim_ids']]
        contexts=[v for v in s['context_pool'] if v['id'] in c['delivered_context_ids']]
        add(c['id']+'-judge','judge','judge',dict(claims=claims,contexts=contexts),dict(labels={i['claim_id']:i['label'] for i in c['expected']['claim_verdicts']},scenario=c))
        add(c['id']+'-matching','judge','matching',dict(question=s['question'],intents=[dict(id=r['id'],text=r['text'],required_claim_ids=[r['id']]) for r in s['reference_claims']],
            reference=[dict(r,role='required') for r in s['reference_claims']],claims=claims),dict(pairs={g['id']+':'+r['id']:'equivalent' if g['text']==r['text'] else 'different' for g in claims for r in s['reference_claims']},scenario=c))
    unique_ids(cases)
    if len(cases)!=84: raise ValueError('fixture request budget mismatch')
    return cases,expectations


def create(out, root=ROOT):
    out=Path(out)
    if out.exists(): raise ValueError('use a new artifact directory; no overwrite or budget reset')
    if list(out.parent.glob('p013-*/ledger.json')): raise ValueError('existing experiment ledger; no new budget')
    a,p=approval_check(root)
    source=root/'evaluation/project_b/preparation/artifacts/run001/source/extracted/canonical'
    canonical_files=list(source.glob('*.txt'))
    if len(canonical_files)!=1: raise ValueError('ambiguous canonical')
    canonical=canonical_files[0].read_text()
    if sha(canonical)!=p['source_canonical_sha256']: raise ValueError('canonical changed')
    for q in p['questions']:
        for c in q['codex_source_checked']['claims']:
            ref=c['source']; start,end=c['answer_span']
            if canonical[ref['start']:ref['end']]!=ref['quote'] or sha(ref['quote'])!=ref['quote_sha256'] or q['codex_source_checked']['answer'][start:end]!=c['text']: raise ValueError('GT provenance changed')
    cases,expectations=make_cases(root,p)
    import json
    show=json.loads(gzip.decompress((root/'docs/verification/p019/model-show.json.gz').read_bytes()))
    tokenizer=QwenTokenizer(show['model_info'])
    lock=read(root/'docs/verification/p019/model-lock.json')
    if show['template']!=lock['template'] or not lock['single_user_template_verified']: raise ValueError('unverified template')
    history=[]
    for path in sorted((root/'evaluation/project_b/preparation/artifacts/run001/calls').glob('*.json')):
        call=read(path); observed=call.get('raw_response',{}).get('prompt_eval_count')
        calculated=tokenizer.count(call['payload']['messages'])
        if observed!=calculated: raise ValueError('tokenizer historical mismatch')
        history.append(dict(call=path.name,observed=observed,calculated=calculated))
    if len(history)!=30: raise ValueError('historical validation incomplete')
    for c in cases:
        n=tokenizer.count(c['payload']['messages']); limit=4608 if c['role']=='extraction' else 5632
        if n>limit: raise ValueError('input_limit_exceeded: '+c['id'])
        c['input_tokens']=n;c['input_limit']=limit;c['template_sha256']=lock['template_sha256']
    # All validation happens before an output directory is created.
    out.mkdir(parents=True)
    paths=set(a['approved_files'])|{APPROVAL,REVIEW,PREP+'/packet.json','docs/verification/p019/model-lock.json','docs/verification/p019/model-show.json.gz','docs/verification/p007/handoff.json'}
    for path in sorted(paths):
        target=out/'inputs'/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/path,target)
    (out/'inputs/canonical.txt').write_text(canonical)
    write(out/'cases.json',cases);write(out/'expectations.json',expectations);write(out/'tokenizer-validation.json',history)
    for path in Path(__file__).parent.glob('*.py'):
        target=out/'code'/path.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(path,target)
    manifest=dict(schema_version='p013-manifest-v1',policy=POLICY,packet_sha256=PACKET,
        code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        limits=dict(total=304,extraction=16,judge=68,e2e=220,model_8b=264,model_4b=20,embedding=20,wall_seconds=14400,retries=0,parallelism=1),
        files={str(f.relative_to(out)):sha(f.read_bytes()) for f in sorted(out.rglob('*')) if f.is_file()})
    manifest['manifest_sha256']=digest(manifest);write(out/'manifest.json',manifest)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    print(create(parser.parse_args().out)['manifest_sha256'])
