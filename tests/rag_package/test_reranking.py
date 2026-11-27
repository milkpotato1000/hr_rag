"""Independent P020 arithmetic, immutable replay, execution and UI boundaries."""
import copy,json,math,subprocess,tempfile,threading,time,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from rag_package import candidates,reranker,reranking,rerank_compare,fact_metrics,search_metrics
from rag_package.storage import RagError,read_json,write_json,fingerprint,seal,verify
from rag_package.workspace import init
from rag_package.documents import snapshot
from rag_package.retrieval import build
from rag_package.rag import ask

class RerankTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.ws=Path(self.tmp.name).resolve()/'ws';init(self.ws);self.calls=[]
  cfg=read_json(self.ws/'fixed.json');cfg.update(schema_version=2,embedding_config=None);cfg['retrieval'].update(candidate_k=20,rrf_k=60);write_json(self.ws/'rag.json',cfg)
  snapshot(self.ws/'sources.json',self.ws/'snapshot');build(self.ws/'snapshot',self.ws/'rag.json',self.ws/'build')
  ask(self.ws/'build',self.ws/'rag.json','생일 휴가',self.ws/'answer');self.c=candidates.freeze(self.ws/'build',self.ws/'answer','q1',20,self.ws/'candidates')
  self.p=reranker.profile({'schema_version':1,'model_id':'BAAI/bge-reranker-v2-m3','revision':'a'*40,'local_path':'/SYNTHETIC_NOT_LOADED','file_manifest':{'config.json':'b'*64}});write_json(self.ws/'profile.json',self.p)
 def backend(self,payload):
  self.calls.append(payload);return {'scores':[{'chunk_id':cid,'score':float(n)-2} for n,cid in enumerate(payload['ids'])]}
 def compare_files(self):
  write_json(self.ws/'set.json',{'schema_version':1,'candidates':[{'question_id':'q1','path':'candidates'}]})
  write_json(self.ws/'variants.json',{'schema_version':1,'variants':[{'id':name,'label':name,'method':method,'profile':profile,'top_k':2,'context_budget_chars':4000} for name,method,profile in [('none','none',None),('on','cross-encoder','profile.json')]]})
 def test_independent_arithmetic(self):
  table=read_json(Path(__file__).parents[2]/'docs/verification/p020/expected.json')
  grades={'a':2,'b':1,'c':0,'d':2}
  for order,key in [('acb','none'),('abc','reranked')]:
   m=search_metrics.metrics([{'chunk_id':c} for c in order],grades,2,True)['values']
   for metric,expected in table[key].items():self.assertAlmostEqual(m[metric],expected)
  self.assertAlmostEqual(search_metrics.metrics([{'chunk_id':c} for c in 'acb'],grades,3,True)['values']['recall'],table['candidate_recall'])
  f=[{'fact_id':'f1','alternatives':[{'spans':[{'document_id':'d','start':0,'end':5},{'document_id':'d','start':10,'end':15}]}]}, {'fact_id':'f2','alternatives':[{'spans':[{'document_id':'d','start':20,'end':25}]},{'spans':[{'document_id':'e','start':0,'end':5}]}]}]
  rows=[{'document_id':'d','start':a,'end':b} for a,b in [(0,3),(3,5),(10,15)]]
  for values,expected in [(rows,.5),(rows+rows,.5),(rows+[{'document_id':'e','start':0,'end':5}],1),(rows[:1]+rows[2:]+[{'document_id':'e','start':0,'end':5}],.5)]:self.assertEqual(fact_metrics.coverage(values,f)['fact_recall'],expected)
 def test_freeze_no_search_and_tamper(self):
  with patch('rag_package.retrieval.select',side_effect=AssertionError('search forbidden')):
   c=candidates.freeze(self.ws/'build',self.ws/'answer','q1',5,self.ws/'c2');self.assertEqual(c['rows'],self.c['rows'][:5])
  with self.assertRaisesRegex(RagError,'output_exists'):candidates.freeze(self.ws/'build',self.ws/'answer','q1',20,self.ws/'c2')
  with self.assertRaisesRegex(RagError,'insufficient_candidate_depth'):candidates.freeze(self.ws/'build',self.ws/'answer','q1',21,self.ws/'big')
  p=self.ws/'candidates/candidates.json';r=read_json(p);r['rows'][0]['text']='tampered';r['candidate_fingerprint']=fingerprint({k:v for k,v in r.items() if k!='candidate_fingerprint'});write_json(p,r);seal(p.parent,{'schema_version':1,'kind':'candidates','candidate_fingerprint':r['candidate_fingerprint']})
  with self.assertRaisesRegex(RagError,'stale_candidate_order'):candidates.load(p.parent)
 def test_none_preview_scores_budget(self):
  r=reranking.run(self.ws/'candidates','none',self.ws/'none',top_k=2,context_budget_chars=1,backend=self.backend);self.assertEqual(self.calls,[]);self.assertEqual(r['selection']['contexts'],[]);self.assertEqual(len(r['selection']['excluded']),min(2,self.c['actual_n']))
  r=reranking.run(self.ws/'candidates','cross-encoder',self.ws/'preview',profile=self.p,backend=self.backend);self.assertEqual(r['status'],'preview');self.assertIsNone(r['selection']);self.assertIsNone(r['scores']);self.assertEqual(self.calls,[])
  r=reranking.run(self.ws/'candidates','cross-encoder',self.ws/'on',profile=self.p,execute=True,backend=self.backend);self.assertEqual(r['status'],'complete');self.assertEqual(len(self.calls),1)
  self.assertEqual(set(self.calls[0]),{'profile','query','passages','ids'});self.assertEqual(r['work']['workers'],0);self.assertEqual(r['work']['fixture_calls'],1);reranking.load(self.ws/'on')
  tied=[dict(x,original_rank=n+1) for n,x in enumerate(self.c['rows'])];scores=[{'chunk_id':r['chunk_id'],'score':-.123456789} for r in tied]
  self.assertEqual([r['chunk_id'] for r in reranking.select(tied,scores,5,4000)['ranking']],[r['chunk_id'] for r in tied])
 def test_bad_scores_and_no_retry(self):
  cases=[[],[{'chunk_id':'unknown','score':0}],[{'chunk_id':self.c['rows'][0]['chunk_id'],'score':float('nan')}]]
  for n,scores in enumerate(cases):
   r=reranking.run(self.ws/'candidates','cross-encoder',self.ws/f'bad{n}',profile=self.p,execute=True,backend=lambda p:{'scores':scores});self.assertEqual(r['status'],'failed');self.assertIsNone(r['selection']);self.assertIsNone(r['work']['pairs'])
  self.calls=[]
  original=reranking.write_json
  def broken(path,v):
   if path.name=='result.json':raise OSError('injected after scoring')
   original(path,v)
  with patch.object(reranking,'write_json',side_effect=broken):
   with self.assertRaises(RagError) as cm:reranking.run(self.ws/'candidates','cross-encoder',self.ws/'write-fail',profile=self.p,execute=True,backend=self.backend)
  self.assertTrue(cm.exception.dispatch_attempted);self.assertEqual(len(self.calls),1);self.assertFalse((self.ws/'write-fail').exists())
 def test_preflight_and_timeout_observation(self):
  r=reranking.run(self.ws/'candidates','cross-encoder',self.ws/'filefail',profile=self.p,execute=True)
  self.assertEqual(r['work']['workers'],0);self.assertEqual(r['work']['pairs'],0);self.assertIsNone(r['work']['worker_exited'])
  class Process:
   returncode=None
   def communicate(self,*a,**kw):
    if self.returncode is None:raise subprocess.TimeoutExpired('owned',1)
    return ('','')
   def kill(self):self.returncode=-9
   def poll(self):return self.returncode
  proc=Process()
  with patch.object(reranker,'check_files'),patch.object(reranker,'versions'),patch.object(reranker.subprocess,'Popen',return_value=proc):
   r=reranking.run(self.ws/'candidates','cross-encoder',self.ws/'timeout',profile=self.p,execute=True)
  self.assertEqual(r['error']['code'],'reranker_timeout');self.assertEqual(r['work']['workers'],1);self.assertIsNone(r['work']['pairs']);self.assertTrue(r['work']['worker_exited'])
 def test_compare_replay_and_mapping_tamper(self):
  self.compare_files();s=rerank_compare.compare(self.ws/'set.json',self.ws/'variants.json',self.ws/'compare',execute=True,backend=self.backend)
  with patch.object(reranker,'score',side_effect=AssertionError('replay model')):
   replay=rerank_compare.report(self.ws/'compare',self.ws/'report');self.assertEqual(replay['aggregates'],s['aggregates'])
  p=self.ws/'compare/comparison.json';s['variants'][1]['profile']['revision']='c'*40;write_json(p,s);m=verify(self.ws/'report','rerank-report')
  old=read_json(p.parent/'manifest.json');seal(p.parent,{k:v for k,v in old['identity'].items() if k!='files'})
  with self.assertRaisesRegex(RagError,'unpaired_variant'):rerank_compare.load(p.parent)
 def test_qrels_facts_strict_and_metrics(self):
  _,docs,corpus=candidates.load(self.ws/'candidates');qs=[{'id':'q1','question':self.c['question']}];first=corpus[0]
  qr={'schema_version':1,'source_fingerprint':self.c['source_fingerprint'],'chunk_fingerprint':self.c['chunk_fingerprint'],'questions_hash':fingerprint(qs),'judgments_complete':True,'judgments':{'q1':{first['chunk_id']:2}}}
  fact={'schema_version':1,'source_fingerprint':self.c['source_fingerprint'],'questions_hash':fingerprint(qs),'offset_unit':'unicode_codepoint','questions':[{'question_id':'q1','required_facts':[{'fact_id':'f1','alternatives':[{'spans':[{'document_id':first['document_id'],'start':first['start'],'end':first['end'],'quote':first['text']}]}]}]}]}
  r=reranking.run(self.ws/'candidates','none',self.ws/'labels',top_k=2,qrels=qr,facts=fact);self.assertEqual(r,reranking.load(self.ws/'labels')[0])
  fact['questions'][0]['required_facts'][0]['alternatives'][0]['spans'][0]['quote']='wrong'
  with self.assertRaisesRegex(RagError,'fact_quote_mismatch'):reranking.run(self.ws/'candidates','cross-encoder',self.ws/'badlabel',profile=self.p,execute=True,backend=self.backend,qrels=qr,facts=fact)
  self.assertEqual(self.calls,[])
 def test_ui_jobs(self):
  from rag_package.ui_registry import Registry
  from rag_package.ui_jobs import Jobs
  from rag_package.ui_server import UI
  reg=Registry(self.ws,[self.ws/'llm-local.json'],reranker_configs=[self.ws/'profile.json']);cid=reg.add_artifact(self.ws/'candidates','candidates');jobs=Jobs(reg,allow_reranking=True,reranker_backend=self.backend);rid=next(iter(reg.rerankers));model=next(iter(reg.data['configs']))
  def job(kind,**kw):
   value={'request_id':str(uuid.uuid4()),'kind':kind,**kw};j,_=jobs.submit(value);jobs.thread.join(10);j=jobs.get(j['id']);self.assertEqual(j['status'],'completed',j);same,new=jobs.submit(value);self.assertFalse(new);return j
  common={'candidate_ids':[cid],'top_k':2,'context_budget_chars':4000,'execute_reranking':True,'qrels_id':None,'facts_id':None}
  j=job('rerank_compare',**common,reranker_ids=[rid]);ui=UI(reg,jobs);a=ui.artifact(j['artifact_ids'][0]);self.assertEqual(len(a['result']['rows']),2)
  on=a['rerank_ids']['model-1/q1'];ui.artifact(on);reg.snapshot_for(on)
  g=job('rerank_answer',rerank_id=on,llm_config_id=model,execute=False);self.assertEqual(ui.artifact(g['artifact_ids'][0])['result']['status'],'preview')
 def test_generation_three_providers_and_empty_invalid(self):
  from test_llm import config,envelope,DIGEST,KEY
  reranking.run(self.ws/'candidates','none',self.ws/'none',top_k=2)
  for provider in ('ollama','openai_chat','anthropic_messages'):
   cfg=config(provider,'json_object');write_json(self.ws/'provider.json',cfg);calls=[]
   def send(method,url,headers,body,timeout):
    calls.append(method)
    if method=='GET':return {'models':[{'name':'fixture-model','digest':DIGEST}]}
    data=json.loads(body['messages'][-1]['content']);v={'status':'answered','answer':'가상 답변','citations':[{'chunk_id':data['contexts'][0]['chunk_id']}]}
    return envelope(provider,json.dumps(v))
   a=reranking.answer(self.ws/'none',self.ws/'provider.json',self.ws/provider,execute=True,transport=send,key_resolver=lambda _:KEY)
   self.assertEqual(a['status'],'answered',a);self.assertEqual(a['generation_requests'],1);self.assertEqual(calls.count('POST'),1)
  cfg=config('openai_chat','json_object');write_json(self.ws/'provider.json',cfg)
  def invalid(*args):return envelope('openai_chat',json.dumps({'status':'answered','answer':'bad','citations':[{'chunk_id':'unknown'}]}))
  a=reranking.answer(self.ws/'none',self.ws/'provider.json',self.ws/'invalid',execute=True,transport=invalid,key_resolver=lambda _:KEY);self.assertEqual(a['error']['code'],'invalid_citation')
  reranking.run(self.ws/'candidates','none',self.ws/'empty',top_k=2,context_budget_chars=1)
  a=reranking.answer(self.ws/'empty',self.ws/'provider.json',self.ws/'empty-answer',execute=True,transport=lambda *a:self.fail('no context call'));self.assertEqual(a['status'],'abstained');self.assertEqual(a['generation_requests'],0)
 def test_multiple_questions_swapped_summary(self):
  ask(self.ws/'build',self.ws/'rag.json','연차',self.ws/'answer2');candidates.freeze(self.ws/'build',self.ws/'answer2','q2',20,self.ws/'candidates2')
  self.compare_files();write_json(self.ws/'set.json',{'schema_version':1,'candidates':[{'question_id':'q1','path':'candidates'},{'question_id':'q2','path':'candidates2'}]})
  s=rerank_compare.compare(self.ws/'set.json',self.ws/'variants.json',self.ws/'compare',execute=True,backend=self.backend)
  for r in s['rows']:r['question_id']='q2' if r['question_id']=='q1' else 'q1'
  s['aggregates']=rerank_compare.summarize(s['rows'],s['variants']);write_json(self.ws/'compare/comparison.json',s);old=read_json(self.ws/'compare/manifest.json');seal(self.ws/'compare',{k:v for k,v in old['identity'].items() if k!='files'})
  with self.assertRaisesRegex(RagError,'unpaired_question'):rerank_compare.load(self.ws/'compare')
 def test_profiles_types_duplicate_json_and_empty_candidates(self):
  for field,value in [('model_id','Qwen/Qwen3-Reranker'),('revision','main'),('max_pair_tokens',True),('timeout_seconds',301),('batch_size',0),('device','cuda'),('file_manifest',{'../escape':'a'*64})]:
   with self.subTest(field=field),self.assertRaises(RagError):reranker.profile(dict(self.p,**{field:value}))
  write_json(self.ws/'placeholder.json',dict(self.p,revision='0'*40));p=reranker.read_profile(self.ws/'placeholder.json');self.assertFalse(reranker.configured(p))
  r=reranking.run(self.ws/'candidates','cross-encoder',self.ws/'placeholder',profile=p,execute=True,backend=self.backend);self.assertEqual(r['reason'],'reranker_configuration_required');self.assertEqual(self.calls,[])
  (self.ws/'dup.json').write_text('{"schema_version":1,"schema_version":2}')
  with self.assertRaises(RagError):reranker.read_profile(self.ws/'dup.json')
  ask(self.ws/'build',self.ws/'rag.json','nothingmatchesuniquely',self.ws/'empty-answer');c=candidates.freeze(self.ws/'build',self.ws/'empty-answer','q0',20,self.ws/'empty-c');self.assertEqual(c['actual_n'],0)
  qr={'schema_version':1,'source_fingerprint':c['source_fingerprint'],'chunk_fingerprint':c['chunk_fingerprint'],'questions_hash':fingerprint([{'id':'q0','question':c['question']}]),'judgments_complete':True,'judgments':{'q0':{self.c['rows'][0]['chunk_id']:2}}}
  r=reranking.run(self.ws/'empty-c','cross-encoder',self.ws/'empty-run',profile=self.p,execute=True,backend=self.backend,qrels=qr);self.assertEqual(r['metrics']['retrieval']['values']['recall'],0);self.assertEqual(self.calls,[])
 def test_partial_failure_groups_and_sequential(self):
  self.compare_files();qr={'schema_version':1,'source_fingerprint':self.c['source_fingerprint'],'chunk_fingerprint':self.c['chunk_fingerprint'],'questions_hash':fingerprint([{'id':'q1','question':self.c['question']}]),'judgments_complete':True,'judgments':{'q1':{self.c['rows'][0]['chunk_id']:2}}}
  s=rerank_compare.compare(self.ws/'set.json',self.ws/'variants.json',self.ws/'failcompare',qrels=qr,execute=True,backend=lambda _: {'scores':[]})
  pair=s['aggregates']['paired']['on']['recall'];self.assertEqual(pair['total'],1);self.assertEqual(pair['paired_valid'],0);self.assertEqual(pair['exclusion_reasons'],{'failed':1})
  qr['judgments_complete']=False
  s=rerank_compare.compare(self.ws/'set.json',self.ws/'variants.json',self.ws/'incomplete',qrels=qr,execute=True,backend=self.backend);self.assertEqual(s['aggregates']['paired']['on']['recall']['exclusion_reasons'],{'judgments_incomplete':1})
  active=[0,0]
  def backend(payload):
   active[0]+=1;active[1]=max(active);time.sleep(.01);r=self.backend(payload);active[0]-=1;return r
  threads=[threading.Thread(target=lambda:reranker.score(self.p,self.c['question'],self.c['rows'],backend=backend)) for _ in range(2)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual(active[1],1)
 def test_fixture_candidate_provenance(self):
  # An injected retrieval backend marks candidate provenance even for BM25.
  ask(self.ws/'build',self.ws/'rag.json','생일',self.ws/'fixture-answer',embedding_backend=lambda *a:self.fail('bm25 embeddings'))
  c=candidates.freeze(self.ws/'build',self.ws/'fixture-answer','qf',20,self.ws/'fixture-c');self.assertEqual(c['execution_kind'],'test_fixture')
  r=reranking.run(self.ws/'fixture-c','none',self.ws/'fixture-none');self.assertEqual(r['candidate_execution_kind'],'test_fixture');self.assertEqual(r['work']['execution_kind'],'none')
  a=reranking.answer(self.ws/'fixture-none',self.ws/'llm-local.json',self.ws/'fixture-gen');self.assertEqual(a['candidate_execution_kind'],'test_fixture');self.assertEqual(a['scorer_execution_kind'],'none')
 def test_generation_failure_and_zero_recompute(self):
  from test_llm import config,envelope,KEY
  write_json(self.ws/'llm.json',config('openai_chat','json_object'));reranking.run(self.ws/'candidates','none',self.ws/'none')
  with patch.object(reranker,'score',side_effect=AssertionError('rerank forbidden')),patch('rag_package.embedding.encode',side_effect=AssertionError('embedding forbidden')):
   a=reranking.answer(self.ws/'none',self.ws/'llm.json',self.ws/'failed',execute=True,transport=lambda *a:envelope('openai_chat','bad json'),key_resolver=lambda _:KEY)
   self.assertEqual(a['status'],'failed');self.assertEqual(a['generation_requests'],1)
  before=verify(self.ws/'none','rerank')['fingerprint'];calls=[]
  def send(*args):calls.append(1);return envelope('openai_chat',json.dumps({'status':'abstained','answer':'근거 부족','citations':[]}))
  with patch.object(reranking,'write_json',side_effect=OSError('post dispatch')):
   with self.assertRaises(RagError) as cm:reranking.answer(self.ws/'none',self.ws/'llm.json',self.ws/'write-failed',execute=True,transport=send,key_resolver=lambda _:KEY)
  self.assertTrue(cm.exception.dispatch_attempted);self.assertEqual(len(calls),1);self.assertEqual(before,verify(self.ws/'none','rerank')['fingerprint'])
 def test_scores_rounding_duplicate_dimensions(self):
  rows=[dict(x,original_rank=n+1) for n,x in enumerate(self.c['rows'][:2])];ids=[r['chunk_id'] for r in rows]
  scores=[{'chunk_id':ids[0],'score':-.1234567891},{'chunk_id':ids[1],'score':-.1234567890}]
  self.assertEqual(reranking.select(rows,scores,2,4000)['ranking'][0]['chunk_id'],ids[1])
  for scores in ([{'chunk_id':x,'score':[.1]} for x in ids],[{'chunk_id':ids[0],'score':1}]*2,[{'chunk_id':x,'score':float('inf')} for x in ids]):
   with self.assertRaises(RagError):reranker.validate_scores({'scores':scores},ids)
 def test_no_relevant_zero_facts_and_report_escape(self):
  self.compare_files();qs=[{'id':'q1','question':self.c['question']}]
  qr={'schema_version':1,'source_fingerprint':self.c['source_fingerprint'],'chunk_fingerprint':self.c['chunk_fingerprint'],'questions_hash':fingerprint(qs),'judgments_complete':True,'judgments':{'q1':{}}}
  facts={'schema_version':1,'source_fingerprint':self.c['source_fingerprint'],'questions_hash':fingerprint(qs),'offset_unit':'unicode_codepoint','questions':[{'question_id':'q1','required_facts':[]}]}
  vs=read_json(self.ws/'variants.json');vs['variants'][1]['label']='<script>alert(1)</script>';write_json(self.ws/'variants.json',vs)
  s=rerank_compare.compare(self.ws/'set.json',self.ws/'variants.json',self.ws/'comparison',qrels=qr,facts=facts,execute=True,backend=self.backend)
  self.assertIsNone(s['rows'][0]['metrics']['retrieval']['values']['recall']);self.assertEqual(s['aggregates']['facts']['none']['top_k']['total_facts'],0)
  self.assertEqual(s['aggregates']['retrieval']['none']['groups']['no_answer']['precision']['value'],0)
  rerank_compare.report(self.ws/'comparison',self.ws/'report');html=(self.ws/'report/report.html').read_text();self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html);self.assertNotIn('<details open>',html)
 def test_label_preflight_all_before_workers(self):
  self.compare_files();qs=[{'id':'q1','question':self.c['question']}]
  qr={'schema_version':1,'source_fingerprint':self.c['source_fingerprint'],'chunk_fingerprint':self.c['chunk_fingerprint'],'questions_hash':fingerprint(qs),'judgments_complete':True,'judgments':{'q1':{'unknown':2}}}
  with self.assertRaisesRegex(RagError,'qrels_unknown_chunk'):rerank_compare.compare(self.ws/'set.json',self.ws/'variants.json',self.ws/'bad',qrels=qr,execute=True,backend=self.backend)
  self.assertEqual(self.calls,[])
  v=read_json(self.ws/'variants.json');v['variants'][1]['top_k']=3;write_json(self.ws/'variants.json',v)
  with self.assertRaisesRegex(RagError,'paired_settings_mismatch'):rerank_compare.compare(self.ws/'set.json',self.ws/'variants.json',self.ws/'bad',execute=True,backend=self.backend)
  self.assertEqual(self.calls,[])
 def test_freeze_dense_hybrid_no_reencoding(self):
  from rag_package import embedding
  ep={'schema_version':1,'model_id':'intfloat/multilingual-e5-small','revision':'a'*40,'local_path':'/SYNTHETIC_NOT_LOADED','file_manifest':{'config.json':'b'*64},'device':'cpu','dtype':'float32','max_input_tokens':512,'batch_size':1,'timeout_seconds':1,'max_chunks':2000}
  write_json(self.ws/'embedding.json',ep);calls=[]
  def enc(p,texts,ids,kind):
   calls.append(kind);return {'vectors':[[1.0]+[float(n)/100]+[0.0]*382 for n,_ in enumerate(texts)],'sdk_versions':{'synthetic':'1'}}
  cfg=read_json(self.ws/'rag.json');cfg['embedding_config']='embedding.json'
  for method in ('dense','hybrid'):
   cfg['retrieval']['method']=method;write_json(self.ws/'hybrid.json',cfg)
   build(self.ws/'snapshot',self.ws/'hybrid.json',self.ws/(method+'build'),execute_retrieval=True,embedding_backend=enc)
   ask(self.ws/(method+'build'),self.ws/'hybrid.json','생일',self.ws/(method+'answer'),execute_retrieval=True,embedding_backend=enc)
   before=list(calls)
   with patch.object(embedding,'encode',side_effect=AssertionError('no reembedding')):
    c=candidates.freeze(self.ws/(method+'build'),self.ws/(method+'answer'),'q1',20,self.ws/(method+'c'))
    candidates.load(self.ws/(method+'c'));self.assertEqual(c['execution_kind'],'test_fixture');self.assertEqual(before,calls)
 def test_fact_macro_and_micro_are_distinct(self):
  rows=[]
  for v in ('none','on'):
   for q,hit,total in [('q1',1,2),('q2',1,1),('q3',0,0)]:
    f={'fact_recall':hit/total if total else None,'fulfilled':hit,'total':total,'reason':None if total else 'no_required_facts'}
    rows.append({'variant_id':v,'question_id':q,'status':'complete','metrics':{'retrieval':{'values':dict.fromkeys(('precision','recall','mrr','ndcg')),'reason':'qrels_not_configured'},'candidate_recall':None,'context_recall':None,'facts':{level:f for level in ('candidate','top_k','contexts')}}})
  result=rerank_compare.summarize(rows,[{'id':'none','method':'none'},{'id':'on','method':'cross-encoder'}])['facts']['on']['contexts']
  self.assertEqual(result['macro'],.75);self.assertAlmostEqual(result['micro'],2/3);self.assertEqual(result['valid'],2);self.assertEqual(result['excluded'],1)
 def test_sdk_preflight_failure_zero_workers(self):
  with patch.object(reranker,'check_files'),patch.object(reranker,'versions',side_effect=RagError('reranker_sdk_mismatch','reranking')):
   r=reranking.run(self.ws/'candidates','cross-encoder',self.ws/'sdk-fail',profile=self.p,execute=True)
  self.assertEqual(r['work']['workers'],0);self.assertEqual(r['work']['queries'],0);self.assertEqual(r['work']['pairs'],0);self.assertEqual(r['error']['code'],'reranker_sdk_mismatch')
