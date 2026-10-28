"""Symmetric external observer; the baseline product files are never modified."""
import time
START=time.perf_counter()
import json,sys,resource,hashlib
from pathlib import Path
stage=Path(sys.argv[1]).resolve();impl=sys.argv[2];args=json.loads(sys.argv[3]);sys.path.insert(0,str(stage/'scripts'))
import runtime_common as rc
import rag
if impl=='langchain':
 import rag_langchain as pipeline
else:pipeline=rag
IMPORT_MS=(time.perf_counter()-START)*1000
http=[];wire=[];original=rc.LocalAPI.call;init=rc.LocalAPI.__init__
def observed_init(self,*a,**kw):
 init(self,*a,**kw);opener=self.opener.open
 def observed_open(req,*a,**kw):
  wire.append({'url':req.full_url,'data':req.data.decode() if req.data else None})
  return opener(req,*a,**kw)
 self.opener.open=observed_open
rc.LocalAPI.__init__=observed_init
def call(self,route,body=None):
 start=time.perf_counter();row={'route':route,'body':body};http.append(row)
 try:
  v=original(self,route,body);row['observations']={k:v[k] for k in ('total_duration','load_duration','prompt_eval_duration','eval_duration','prompt_eval_count','eval_count') if k in v}
  if route=='/api/embed':row['embeddings_sha256']=hashlib.sha256(json.dumps(v['embeddings']).encode()).hexdigest()
  return v
 except Exception as e:row['error']=repr(e);raise
 finally:row['wall_ms']=(time.perf_counter()-start)*1000
rc.LocalAPI.call=call
corpus=args.pop('corpus');idx='index-v1' if corpus=='synthetic15' else 'index-source-v2-fixed-400-80';chunks='data/synthetic/chunks.jsonl' if corpus=='synthetic15' else 'data/source-v2/fixed-400-80/chunks.jsonl'
result=pipeline.ask(**args,index_dir=stage/'.runtime'/idx,chunks_path=stage/chunks)
print(json.dumps({'implementation':impl,'stage':str(stage),'result':result,'http':http,'wire':wire,'import_ms':IMPORT_MS,'worker_total_ms':(time.perf_counter()-START)*1000,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},ensure_ascii=False))
