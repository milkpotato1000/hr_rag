"""Validate downloaded/live results, bounded dispatch count, and frozen boundaries."""
import json,hashlib,sys,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p012';old=root/'docs/verification/p011';candidate=root/'1. Naive RAG/variants/langchain'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
reviews={r['case_id']:r for r in read(old/'manual-reviews.json')}
checks=[]
def check(r,cid,impl,label):
 assert r['trace']['comparison']['implementation']==impl,label
 assert r['trace']['generation_calls']==1,label
 assert r['trace']['generation']['request_dispatched'],label
 v={k:r[k] for k in ['status','answer','citations','reason']}
 sig=hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 assert sig==reviews[cid]['reviewed_output_sha256'],('manual review needed',label)
 ref=read(old/'runs'/f'warm-01-{cid}-langchain.json')['result']
 for field in ['candidates','contexts','excluded','prompt','corpus_sha256']:
  assert r['trace'][field]==ref['trace'][field],(label,field)
 assert r['trace']['generation']['request']==ref['trace']['generation']['request'],(label,'payload')
 contexts={c['chunk_id']:c for c in r['trace']['contexts']}
 for c in r['citations']:assert c['quote'].encode()==contexts[c['chunk_id']]['text'].encode()
 checks.append({'result':label,'case_id':cid,'implementation':impl,'payload_search_context_quote_exact':True,'output_matches_p011_review':True})
for filename,cid,impl in [('cli-default','meal-bm25','langchain'),('cli-direct','meal-bm25','direct'),('copy-cli-default','meal-bm25','langchain'),('api-default','q01','langchain')]:check(read(ev/'smokes'/f'{filename}.json'),cid,impl,filename)
for name,cid in [('browser-basic','q01'),('browser-multi','q03'),('browser-missing','q13')]:check(read(ev/f'{name}.json'),cid,'langchain',name)
pair=read(ev/'browser-pair.json');assert [x['implementation'] for x in pair['results']]==['direct','langchain'];assert [x['order'] for x in pair['results']]==[1,2]
for row in pair['results']:check(row['result'],'q03',row['implementation'],'browser-pair-'+row['implementation'])
assert read(ev/'fixture-error.json')['reason']=='timeout'
fault=read(ev/'fixture-pair-error.json');assert [r['result']['status'] for r in fault['results']]==['answered','error']
ledger=[json.loads(l) for l in (ev/'ledger.jsonl').read_text().splitlines()]
for name in ['browser-basic','browser-multi','browser-missing','browser-pair']:
 if name in [x['slot'] for x in ledger]:continue
 data=read(ev/(name+'.json'));results=[r['result'] for r in data['results']] if 'results' in data else [data]
 row={'slot':name,'dispatches':sum(r['trace']['generation_calls'] for r in results),'statuses':[r['status'] for r in results],'count_basis':'actual browser-downloaded trace'}
 ledger.append(row)
 with (ev/'ledger.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
count=sum(r['dispatches'] for r in ledger);assert count==9 and count<=16,count
# Refresh only provenance metadata written after the executable-copy smoke.
copy=Path(read(ev/'copy-location.json')['path']);shutil.copy2(candidate/'copy-manifest.json',copy/'copy-manifest.json')
copy_report=read(ev/'copy-smoke.json');copy_report['product_hashes']['copy-manifest.json']=sha(copy/'copy-manifest.json');copy_report['provenance_metadata_refreshed_after_smoke']=True
for p,h in copy_report['product_hashes'].items():assert sha(candidate/p)==h==sha(copy/p),p
(ev/'copy-smoke.json').write_text(json.dumps(copy_report,ensure_ascii=False,indent=2)+'\n')
sys.path.insert(0,str(candidate/'scripts'));from copy_indexes import logical
indexes=[]
for x in read(old/'index-preservation.json'):
 values={label:logical(stage/'.runtime'/x['index']) for label,stage in [('original',root/'1. Naive RAG'),('candidate',candidate),('copy',copy)]}
 assert set(values.values())=={x['export_sha256']}
 indexes.append({'index':x['index'],'hashes':values})
(ev/'live-check.json').write_text(json.dumps({'status':'PASS','dispatches':count,'max_dispatches':16,'checks':checks,'index_preservation':indexes,'quality_limit':'Existing q03 annual1day omission retained; no new quality claim'},ensure_ascii=False,indent=2)+'\n')
print('Live/copy/indices/dispatch budget PASS:',count)
