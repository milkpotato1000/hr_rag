import sys,json,random,hashlib,copy
from pathlib import Path
stage=Path(sys.argv[1]).resolve();impl=sys.argv[2];protocol=json.loads(Path(sys.argv[3]).read_text());sys.path.insert(0,str(stage/'scripts'))
import rag
from generation import Generator,load_generation_lock,MODEL
from dense_retrieval import DenseIndex
from runtime_common import load_lock
if impl=='langchain':import rag_langchain as pipeline
else:pipeline=rag
results=[]
qs=[c for c in protocol['cases'] if c['id'] not in ('meal-bm25','pdf-q06')];pdf=next(c for c in protocol['cases'] if c['id']=='pdf-q06')
for case in qs+[pdf]:
 pdfcase=case['id']=='pdf-q06';chunks_path=stage/('data/source-v2/fixed-400-80/chunks.jsonl' if pdfcase else 'data/synthetic/chunks.jsonl');idx=stage/'.runtime'/('index-source-v2-fixed-400-80' if pdfcase else 'index-v1')
 rows,h=rag.evaluation.read_jsonl(chunks_path);chunks=rag.evaluation.validate_chunks(rows);rng=random.Random(hashlib.sha256(case['question'].encode()).hexdigest());vector=[rng.uniform(-1,1) for _ in range(1024)]
 with DenseIndex(idx,chunks,h,load_lock()) as db:ranking=db.search(vector,100)
 for ret in ['bm25','dense']:
  for k in ([5] if pdfcase else [1,5,100]):
   for budget in ([8000] if pdfcase else [1,8000,24000]):
    sent=[]
    def retrieve(q,chunks,h,retriever,top_k,index_dir,timeout_seconds):
     if retriever=='bm25':return rag.retrieve(q,chunks,h,retriever,top_k,index_dir,timeout_seconds)
     return ranking[:top_k],{'vector_sha256':hashlib.sha256(json.dumps(vector).encode()).hexdigest()}
    class API:
     def call(self,route,body):
      assert route=='/api/chat';sent.append(body)
      return {'model':MODEL,'done':True,'message':{'role':'assistant','content':'{"status":"abstained","answer":"fixture","citations":[]}'}}
    provider=Generator(api=API(),lock=load_generation_lock());provider.check=lambda:None
    r=pipeline.ask(case['question'],retriever=ret,top_k=k,max_context_chars=budget,chunks_path=chunks_path,retrieve_fn=retrieve,generator=provider)
    r['trace'].pop('timings_ms');r['trace']['retrieval'].pop('search_ms',None)
    results.append(dict(case_id=case['id'],retriever=ret,k=k,budget=budget,result=r,payload=sent))
print(json.dumps(results,ensure_ascii=False))
