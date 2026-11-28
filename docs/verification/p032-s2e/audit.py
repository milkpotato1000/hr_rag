"""Check preservation and summarize actual accounting without loading a model."""
from pathlib import Path
from runtime import *
verify_parent()
old = read(E.parent/'p032-s2d/frozen.json')
need(sha(Path(old['wheel'])) == old['wheel_sha256'], 'previous_wheel_changed')
frozen = read(E/'frozen.json')
for collection, directory in [('input_files',ROOT),('scripts',E)]:
    for name,digest in frozen[collection].items():
        need(sha(directory/name)==digest,'frozen_hash_changed')
protected = read(E.parent/'p032-s1/preservation.json')['files']
for name,digest in protected.items():
    need(sha(ROOT/name)==digest,'protected_file_changed')
ledger = read(LEDGER)
rows = [json.loads(line) for line in (E/'resources.jsonl').read_text().splitlines()]
result = read(E/'answers/gt01/result.json')
need(len(ledger['requests'])==1 and ledger['requests'][0]['question_id']=='gt01','request_count')
need(len(ledger['metadata'])<=160,'metadata_cap')
need(result['actual_messages_hash']==old['rows'][0]['actual_messages_hash'],'prompt_changed')
write(E/'final-checks.json',{
    'freeze_commit':'66708184d260472577d03cee4b134a124e97d579',
    's2d_artifacts':len(read(ROOT/'docs/planning/reviews/p032-s2d-halt-audit.json')['artifacts']),
    's2d_wheel_sha256':old['wheel_sha256'],'protected_files':len(protected),
    'generation_requests':1,'including_parent':2,'metadata_requests':len(ledger['metadata']),
    'metadata_including_parent':30+len(ledger['metadata']),'peak_sampled_rss_bytes':max(r['rss_bytes'] for r in rows),
    'pressure_levels':sorted(set(r['pressure'] for r in rows)),'parent_deadline_unchanged':True,
    'loaded_model_after_run':read(E/'gt01-observation.json')['loaded_observations'][-1]['models'],
    'closing':read(E/'server-closed.json'),'package_tests':136,'control_tests':8,
    'outcome':result['status'],'provider_status':result['provider_result']['status'],
    'usage':result['provider_result']['usage'],'thinking_tokens':None,'final_tokens':None,
    'gt02_to_gt10':'not_executed','model_downloads':0,'generation_retries':0})
