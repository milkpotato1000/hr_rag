"""Independently verify boundaries against source offsets and count dispatched POSTs."""
from runtime import *
verify_parent()
f=read(E/'frozen.json')
for entries,base in [(f['scripts'],E),(f['input_files'],ROOT),(f['installed_files'],Path('/'))]:
    for n,h in entries.items():need(sha(base/n)==h,'frozen_file_changed')
need(sha(Path(f['wheel']))==f['wheel_sha256'],'wheel_changed')
l=read(LEDGER);need([x['question_id'] for x in l['requests']]==['w000'],'wrong_dispatch')
w=read(E/'window.json');r=read(E/'window-result.json')
need(r['actual_messages_hash']==f['rows'][0]['actual_messages_hash'],'messages_changed')
selected=r['selected_end_ids']
if r['status']=='valid_window':
    units=w['units'];ends={u['id']:u['end'] for u in units}
    boundaries=[ends[i] for i in selected]
    need(boundaries==sorted(set(boundaries)) and boundaries[-1]==len(w['source_text']),'invalid_order')
    ranges=list(zip([0]+boundaries[:-1],boundaries))
    need(all(0<b-a<=192 for a,b in ranges) and ranges==[(s['start'],s['end']) for s in r['spans']],'invalid_spans')
else:need(selected is None and r['spans'] is None,'published_failed_selection')
provider=r['provider_result'];elapsed=provider['elapsed_ms']/1000
samples=[json.loads(s) for s in (E/'resources.jsonl').read_text().splitlines()]
write(E/'final-checks.json',dict(status=r['status'],error=r['error'],provider_status=provider['status'],finish_reason=provider['finish_reason'],usage=provider['usage'],elapsed_seconds=elapsed,estimated_remaining_minutes=elapsed*33/60,peak_rss_bytes=max(s['rss_bytes'] for s in samples),pressure_levels=sorted({s['pressure'] for s in samples}),metadata_requests=len(l['metadata']),chunking_posts=1,retries=0,windows_executed=1,remaining_unexecuted=33,source_chars=len(w['source_text']),units=len(w['units']),validated_segments=len(r['spans'] or []),server_cleanup=read(E/'server-closed.json'),partial_window_only=True,search_index_created=False))
