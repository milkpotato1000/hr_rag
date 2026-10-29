"""Read the frozen dev commit; emit planning profiles, never chunk/index products."""
import hashlib, json, re, subprocess
from pathlib import Path
REF='4cdee6f9583c899d76e95237af8b5de8d77d8012'
BASE='2. Document Chunking/data/source-v4/'
OUT=Path(__file__).resolve().parent

def read(path): return subprocess.check_output(['git','show',f'{REF}:{path}'])
def sha(b): return hashlib.sha256(b).hexdigest()
def save(name,d): (OUT/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
manifest=json.loads(read(BASE+'handoff-manifest.json'))
for path,digest in manifest['files'].items(): assert sha(read(BASE+path))==digest,path
completion=json.loads(read('docs/verification/p016/completion.json'))
for row in completion['committed_evidence']: assert sha(read(row['path']))==row['sha256'],row['path']
raw=read(BASE+'extracted/canonical/hr-v4-handbook.txt');text=raw.decode()
sections=json.loads(read(BASE+'section-map.json'))
for node in sections['nodes']:
 for k in ['heading','extent','body']:
  if k in node:
   s=node[k];assert text[s['start']:s['end']]==s['quote'],(node['id'],k)
# Sentences/paragraphs/verified headings; PDF visual wraps alone are not boundaries.
ends={len(text):'document_end'}
for m in re.finditer(r'\n\s*\n',text):ends[m.end()]='paragraph'
for m in re.finditer(r'[.?!。！？](?=\s|$)',text):
 p=m.end()
 while p<len(text) and text[p].isspace():p+=1
 ends.setdefault(p,'sentence')
for n in sections['nodes']:
 p=n['heading']['end']
 while p<len(text) and text[p].isspace():p+=1
 ends[p]='heading'
units=[];start=0
for end,kind in sorted(ends.items()):
 if end<=start:continue
 while end-start>400:
  units.append({'id':f'u{len(units):05d}','start':start,'end':start+400,'kind':'forced_atom_split'});start+=400
 units.append({'id':f'u{len(units):05d}','start':start,'end':end,'kind':kind});start=end
assert units[0]['start']==0 and units[-1]['end']==len(text)
assert all(a['end']==b['start'] for a,b in zip(units,units[1:]))
windows=[];current=[]
for unit in units:
 if current and (unit['end']-current[0]['start']>1200 or len(current)==20):windows.append(current);current=[]
 current.append(unit)
if current:windows.append(current)
fixed=[]
for size in [200,400,800]:
 for overlap in [0,size//5]:
  spans=[];s=0
  while s<len(text):
   e=min(s+size,len(text));spans.append((s,e))
   if e==len(text):break
   s+=size-overlap
  fixed.append({'size':size,'overlap':overlap,'chunks':len(spans),'emitted_chars':sum(e-s for s,e in spans)})
profile={'p016_completion_commit':REF,'source_base':BASE,'canonical_sha256':sha(raw),'canonical_chars':len(text),'verified_handoff_entries':len(manifest['files']),'verified_completion_evidence':len(completion['committed_evidence']),'input_manifest_sha256':sha(read(BASE+'handoff-manifest.json')),'section_map_sha256':sha(read(BASE+'section-map.json')),'pages':23,'heading_nodes':len(sections['nodes']),'body_chars':completion['body_chars'],'unit_count':len(units),'forced_atom_splits':sum(u['kind']=='forced_atom_split' for u in units),'window_chars':1200,'window_max_units':20,'window_count':len(windows),'windows':[{'id':f'w{i:03d}','start':w[0]['start'],'end':w[-1]['end'],'unit_ids':[u['id'] for u in w]} for i,w in enumerate(windows)],'fixed_count_profile':fixed,'model_calls':0,'retrieval_runs':0,'note':'Planning dry profile only. Implementation must independently reproduce boundary map; semantic/LLM chunks not generated.'}
save('source-profile.json',profile);save('boundary-map.json',{'version':'boundary-map-v1','canonical_sha256':sha(raw),'units':units})
print(json.dumps({k:v for k,v in profile.items() if k not in ['windows','fixed_count_profile']},ensure_ascii=False))
print('fixed:',fixed)
