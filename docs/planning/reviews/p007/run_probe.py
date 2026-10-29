"""Bounded readiness probes authorized by preflight-scope.md; no sweep/index."""
import json,time,urllib.request,math
from pathlib import Path
P=Path(__file__).resolve().parent
assert not (P/'probe-results.json').exists(),'Never overwrite probe evidence'
assert json.loads((P/'input-budget.json').read_text())['all_fit']
rows=json.loads((P/'probe-requests.json').read_text())['requests'];assert len(rows)==3
units={u['id']:u for u in json.loads((P/'boundary-map.json').read_text())['units']}
windows={w['id']:w for w in json.loads((P/'source-profile.json').read_text())['windows']}
result={'generation':[],'embedding':None,'limits':{'generation_requests':3,'embedding_requests':1,'embedding_items':2,'generation_timeout_seconds':90,'total_seconds':300},'retrieval_runs':0}
def save(): (P/'probe-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
def call(path,payload,timeout):
 req=urllib.request.Request('http://127.0.0.1:11434'+path,data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def unique(pairs):
 d={}
 for k,v in pairs:
  if k in d:raise ValueError('duplicate key')
  d[k]=v
 return d
started=time.monotonic()
for row in rows:
 if time.monotonic()-started>=240:result['stopped']='probe total deadline';break
 t=time.monotonic();record={'window_id':row['window_id']}
 try:
  response=call('/api/chat',row['payload'],min(90,240-(time.monotonic()-started)))
  record['response']=response
  assert response.get('done') is True and response.get('done_reason')=='stop','incomplete response'
  parsed=json.loads(response['message']['content'],object_pairs_hook=unique)
  assert set(parsed)=={'end_unit_ids'}
  ids=parsed['end_unit_ids'];w=windows[row['window_id']];allowed=w['unit_ids']
  assert isinstance(ids,list) and ids and all(isinstance(x,str) and x in allowed for x in ids)
  positions=[allowed.index(x) for x in ids];assert positions==sorted(set(positions))
  assert ids[-1]==allowed[-1]
  lengths=[];s=w['start']
  for uid in ids:
   e=units[uid]['end'];assert 0<e-s<=800;lengths.append(e-s);s=e
  assert s==w['end']
  record.update(status='PASS',chunk_lengths=lengths,selected_end_ids=ids)
 except Exception as e:record.update(status='FAIL',error=str(e))
 record['wall_seconds']=round(time.monotonic()-t,4);result['generation'].append(record);save()
 print('probe',len(result['generation']),record['window_id'],record['status'],record['wall_seconds'],flush=True)
if time.monotonic()-started<300:
 t=time.monotonic()
 try:
  response=call('/api/embed',{'model':'bge-m3:567m','input':['신청한 날짜와 승인 내역을 확인한다.','시스템 장애 시 임시 접수 기록을 남긴다.'],'truncate':False},min(60,300-(time.monotonic()-started)))
  vectors=response.pop('embeddings');assert len(vectors)==2 and all(len(v)==1024 and all(math.isfinite(x) for x in v) and sum(x*x for x in v)>0 for v in vectors)
  result['embedding']={'status':'PASS','response_metadata':response,'items':2,'dimension':1024,'norms':[sum(x*x for x in v)**.5 for v in vectors]}
 except Exception as e:result['embedding']={'status':'FAIL','error':str(e)}
 result['embedding']['wall_seconds']=round(time.monotonic()-t,4)
result['total_wall_seconds']=round(time.monotonic()-started,4);save();print('embedding',result['embedding'],flush=True)
