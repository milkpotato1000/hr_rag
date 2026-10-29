"""Observe real query embedding wire bytes/output independently of generation."""
import json,sys,hashlib,time
from pathlib import Path
stage=Path(sys.argv[1]).resolve();protocol=json.loads(Path(sys.argv[2]).read_text());sys.path.insert(0,str(stage/'scripts'))
from runtime_common import LocalAPI,load_lock
api=LocalAPI();lock=load_lock();api.check(lock);wire=[];open_=api.opener.open

def observe(req,*a,**kw):
 if req.full_url.endswith('/api/embed'):wire.append(req.data.decode())
 return open_(req,*a,**kw)
api.opener.open=observe
rows={}
for c in protocol['cases']:
 if c['id'] in ('meal-bm25','pdf-q06'):continue
 vector=api.embed([c['question']],lock['model']['dimension'])[0];rows[c['id']]={'question':c['question'],'vector':vector,'wire':wire[-1]}
api.check(lock)
print(json.dumps(rows,ensure_ascii=False))
