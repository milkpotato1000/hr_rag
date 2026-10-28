"""Matrix of deterministic index replay and independent error expectations."""
import copy,json,sys,tempfile,unittest,hashlib,random
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import rag,rag_langchain as lc
from generation import Generator,load_generation_lock,MODEL
from dense_retrieval import DenseIndex
from runtime_common import load_lock

def norm(r):
 r=copy.deepcopy(r);t=r['trace'];t.pop('timings_ms',None)
 if 'retrieval' in t:
  t['retrieval']={k:v for k,v in t['retrieval'].items() if not k.endswith('_ms')}
 return r

class Parity(unittest.TestCase):
 def test_matrix(self):
  stage=Path(__file__).resolve().parents[1]
  qs=[json.loads(l)['question'] for l in (stage/'data/synthetic/queries.jsonl').read_text().splitlines()]+['교육 휴가는 누가 신청할 수 있고 연 며칠이며, 연차·생일 휴가와 어떻게 관리되나요?','등록한 자택에서 이사했다면 재택 시작 전에 무엇을 누구에게 요청하나요?','출장은 언제까지 누구의 승인을 받아야 하고, 승인받으면 재택이나 휴가도 승인되나요?','회사 주택자금 대출의 한도와 금리는 얼마인가요?']
  for corpus,index,questions,ks,bs in [('data/synthetic/chunks.jsonl','index-v1',qs,[1,5,100],[1,8000,24000]),('data/source-v2/fixed-400-80/chunks.jsonl','index-source-v2-fixed-400-80',[qs[5]],[5],[8000])]:
   path=stage/corpus;rows,h=rag.evaluation.read_jsonl(path);chunks=rag.evaluation.validate_chunks(rows)
   for q in questions:
    rng=random.Random(hashlib.sha256(q.encode()).hexdigest());vector=[rng.uniform(-1,1) for _ in range(1024)]
    with DenseIndex(stage/'.runtime'/index,chunks,h,load_lock()) as db: dense_rows=db.search(vector,100)
    for ret in ['bm25','dense']:
     for k in ks:
      for budget in bs:
       sent=[]
       def search(question,chunks,corpus_hash,retriever,top_k,index_dir,timeout_seconds):
        if retriever=='bm25':return rag.retrieve(question,chunks,corpus_hash,retriever,top_k,index_dir,timeout_seconds)
        return dense_rows[:top_k],{'replay':'fixed vector through real Qdrant'}
       class API:
        def call(self,route,body):
         self_outer.assertEqual(route,'/api/chat');sent.append(copy.deepcopy(body))
         return {'model':MODEL,'done':True,'message':{'role':'assistant','content':json.dumps({'status':'abstained','answer':'fixture','citations':[]})}}
       self_outer=self
       answers=[]
       for pipeline in [rag,lc]:
        provider=Generator(api=API(),lock=load_generation_lock());provider.check=lambda:None
        answers.append(pipeline.ask(q,retriever=ret,top_k=k,max_context_chars=budget,chunks_path=path,retrieve_fn=search,generator=provider))
       self.assertEqual(norm(answers[0]),norm(answers[1]))
       self.assertIn(len(sent),(0,2))
       if sent:self.assertEqual(sent[0],sent[1])
       self.assertEqual(answers[1]['trace']['generation_calls'],len(sent)//2)

 def test_preflight_and_stale_no_dispatch(self):
  def retrieval(*a):return [{'chunk_id':'birthday-eligibility','score':1}],{}
  for pipeline in [rag,lc]:
   g=Generator();g.check=lambda:(_ for _ in ()).throw(ValueError('model digest changed'))
   r=pipeline.ask('q',retrieve_fn=retrieval,generator=g)
   self.assertEqual((r['status'],r['reason']),('error','provider'));self.assertFalse(r['trace']['generation']['request_dispatched'])
   r=pipeline.ask('q',index_dir=Path('/nonexistent-stale-index'))
   self.assertEqual((r['status'],r['reason'],r['trace']['generation_calls']),('error','execution',0))

if __name__=='__main__':unittest.main()
