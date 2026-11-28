"""P030 independent boundary expectations and model-free artifact replay."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from rag_package import chunk_policy as p,chunk_artifact as a,embedding,llm,candidates
from rag_package.storage import read_json,write_json,RagError,fingerprint,seal
from rag_package.workspace import init
from rag_package.documents import snapshot,load_snapshot
from rag_package import retrieval,rag,fact_metrics
from test_llm import config,envelope,DIGEST,KEY

class ChunkTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.ws=Path(self.tmp.name).resolve()/'ws';init(self.ws)
  snapshot(self.ws/'sources.json',self.ws/'snapshot');self.sm,self.docs=load_snapshot(self.ws/'snapshot');self.calls=[]
  self.ep={'schema_version':1,'model_id':'intfloat/multilingual-e5-small','revision':'a'*40,'local_path':'/SYNTHETIC_NOT_LOADED','file_manifest':{'config.json':'b'*64},'device':'cpu','dtype':'float32','max_input_tokens':512,'batch_size':1,'timeout_seconds':2,'max_chunks':5000}
  write_json(self.ws/'ep.json',self.ep)
 def cfg(self,method,**kwargs):
  c={'schema_version':1,'method':method,'size_chars':200,'overlap_chars':20}
  if method=='semantic':c.update(embedding_config='ep.json',distance_threshold=.5,minimum_chars=40,unit_max_chars=40)
  if method=='llm':c.update(llm_config='lc.json',unit_max_chars=40,window_max_chars=120)
  c.update(kwargs);path=self.ws/(method+'.json');write_json(path,c);return path
 def enc(self,profile,texts,ids,kind):
  self.calls.append((kind,ids));return {'vectors':[[1.0]+[float(n%2)]+[0.0]*382 for n in range(len(texts))],'sdk_versions':{'synthetic':'1'}}
 def lc(self,provider='openai_chat'):
  c=config(provider,'json_object');c['schema_version']=2;c['roles']['chunking']=c['roles']['generation'];write_json(self.ws/'lc.json',c);return c
 def send(self,provider):
  def fn(method,url,headers,body,timeout):
   if method=='GET':return {'models':[{'name':'fixture-model','digest':DIGEST}]}
   self.calls.append(body);units=json.loads(body['messages'][-1]['content'])['units']
   return envelope(provider,json.dumps({'end_unit_ids':[u['id'] for u in units]}))
  return fn
 def reseal(self,path):
  r=read_json(path/'chunk.json');r['chunk_fingerprint']=fingerprint({k:v for k,v in r.items() if k!='chunk_fingerprint'});write_json(path/'chunk.json',r)
  seal(path,{'schema_version':1,'kind':'chunks','status':'ready','source_fingerprint':r['source_fingerprint'],'chunk_fingerprint':r['chunk_fingerprint']})
 def test_independent_boundaries_overlap_fact(self):
  us=[{'id':f'u{n}','document_id':'d','start':n*4,'end':(n+1)*4,'reason':'sentence'} for n in range(3)];vs=[[1,0],[1,0],[0,1]]
  b,d=p.semantic(us,vs,12,4,.5);self.assertEqual([x['distance'] for x in d],[0,1]);self.assertEqual([(x['start'],x['end']) for x in b],[(0,8),(8,12)])
  self.assertEqual([(x['start'],x['end']) for x in p.semantic(us,vs,12,4,1.5)[0]],[(0,12)])
  self.assertEqual([(x['start'],x['end']) for x in p.semantic(us,vs,8,4,1.5)[0]],[(0,8),(8,12)])
  self.assertEqual([(x['start'],x['end']) for x in p.parse({'end_unit_ids':['u1','u2']},us,12)],[(0,8),(8,12)])
  docs=[{'document_id':'d','text':'abcdefghijkl','pages':[{'page':1,'start':0,'end':12}]}]
  cs,m=p.emit(docs,'s',{'size_chars':12,'overlap_chars':2},b);self.assertEqual([(c['start'],c['end']) for c in cs],[(0,8),(6,12)])
  self.assertEqual(a.stats(cs,m,us)['duplicate_chars'],2)
  facts=[{'fact_id':'f','alternatives':[{'spans':[{'document_id':'d','start':7,'end':9}]}]}]
  self.assertEqual(fact_metrics.coverage(cs[:1],facts)['fact_recall'],0);self.assertEqual(fact_metrics.coverage(cs[1:],facts)['fact_recall'],1)
  for ids in [['u2','u1'],['u0','u0','u2'],['missing'],['u1']]:
   with self.assertRaises(RagError):p.parse({'end_unit_ids':ids},us,12)
 def test_rules_v3_candidate_replay(self):
  for method in ('fixed','recursive','structure'):
   target=self.ws/('chunks-'+method);r=a.build(self.ws/'snapshot',self.cfg(method),target);self.assertEqual(r['status'],'ready',r)
   c={'schema_version':3,'chunk_artifact':str(target),'retrieval':{'method':'bm25','top_k':3,'candidate_k':20,'rrf_k':60,'context_budget_chars':2000},'embedding_config':None,'llm_config':'llm-local.json'};cp=self.ws/'rag3.json';write_json(cp,c)
   with patch.object(embedding,'encode',side_effect=AssertionError('model')),patch.object(llm,'invoke',side_effect=AssertionError('model')):
    a.replay(target);retrieval.build(self.ws/'snapshot',cp,self.ws/('build-'+method));rag.ask(self.ws/('build-'+method),cp,'생일',self.ws/('answer-'+method));candidates.freeze(self.ws/('build-'+method),self.ws/('answer-'+method),'q',10,self.ws/('cand-'+method));candidates.load(self.ws/('cand-'+method))
 def test_semantic_derive_and_preflight_counts(self):
  cp=self.cfg('semantic');r=a.build(self.ws/'snapshot',cp,self.ws/'sem',execute=True,embedding_backend=self.enc);self.assertEqual(r['status'],'ready',r);self.assertEqual(len(self.calls),1)
  with patch.object(embedding,'encode',side_effect=AssertionError('model')):
   a.replay(self.ws/'sem');a.derive(self.ws/'sem',self.cfg('semantic',distance_threshold=1.5),self.ws/'derived');a.replay(self.ws/'derived')
  r=a.build(self.ws/'snapshot',cp,self.ws/'fail',execute=True);self.assertEqual(r['status'],'failed');self.assertEqual(r['work']['boundary_model_jobs'],0);self.assertEqual(r['work']['unit_observation']['workers_started'],0);self.assertFalse((self.ws/'fail').exists())
 def test_compact_ids_reset_and_replay(self):
  self.lc();target=self.ws/'numbered';cfg=self.cfg('llm',id_representation='window_number')
  result=a.build(self.ws/'snapshot',cfg,target,execute=True,transport=self.send('openai_chat'),key_resolver=lambda _:KEY)
  self.assertEqual(result['status'],'ready',result)
  data=a.load(target)[0];windows=data['details']['windows']
  self.assertGreater(len(windows),1)
  self.assertNotEqual(windows[0]['unit_ids'][0],windows[1]['unit_ids'][0])
  for body,w in zip(self.calls,windows):
   units=json.loads(body['messages'][-1]['content'])['units']
   self.assertEqual([u['id'] for u in units],[str(i+1) for i in range(len(units))])
   self.assertEqual(w['selected_end_ids'],w['unit_ids'])
  with patch.object(llm,'invoke',side_effect=AssertionError('model')):a.replay(target)
  self.calls.clear()
  def wrong(*args):
   self.calls.append(1)
   return envelope('openai_chat',json.dumps({'end_unit_ids':['01']}))
  failed=a.build(self.ws/'snapshot',cfg,self.ws/'bad',execute=True,transport=wrong,key_resolver=lambda _:KEY)
  self.assertEqual(failed['status'],'failed');self.assertEqual(self.calls,[1])
 def test_candidate_choice_partition_and_failures(self):
  self.lc()
  cfg=self.cfg('llm',size_chars=100,overlap_chars=20,unit_max_chars=19,window_max_chars=140,partition_mode='candidate_choice')
  def run(name,choice='1',finish='stop'):
   def send(*args):
    self.calls.append(args[3])
    return envelope('openai_chat',json.dumps({'candidate_id':choice}),finish)
   return a.build(self.ws/'snapshot',cfg,self.ws/name,execute=True,transport=send,key_resolver=lambda _:KEY)
  target=self.ws/'choice'
  self.assertEqual(run('choice')['status'],'ready')
  saved,docs,chunks,maps=a.load(target)
  windows=saved['details']['windows']
  self.assertGreater(len(windows),1)
  self.assertTrue(saved['statistics']['forced_units'])
  self.assertEqual(len(self.calls),sum(len(w['candidates'])>1 for w in windows))
  self.assertGreater(len(self.calls),0)
  for w in windows:
   for candidate in w['candidates']:
    parts=candidate['pieces']
    self.assertTrue(all(len(i['text'])==i['end']-i['start']<=80 for i in parts))
    self.assertEqual([i['end'] for i in parts[:-1]],[i['start'] for i in parts[1:]])
  with patch.object(llm,'invoke',side_effect=AssertionError('model')):a.replay(target)
  from rag_package import pipeline
  search=read_json(self.ws/'fixed.json')
  search['llm_config']='lc.json'
  write_json(self.ws/'search.json',search)
  integrated=pipeline.run(self.ws/'sources.json',cfg,self.ws/'search.json','unmatchedwordxyz',self.ws/'pipeline',
      execute=True,transport=lambda *args:envelope('openai_chat','{"candidate_id":"1"}'),key_resolver=lambda _:KEY)
  self.assertEqual(integrated['status'],'abstained',integrated)
  saved_pipeline=a.load(self.ws/'pipeline/chunks')[0]
  self.assertEqual(saved_pipeline['details']['windows'],windows)
  self.assertEqual(saved_pipeline['base'],saved['base'])
  for name,choice,finish in [('bad-choice','invalid','stop'),('truncated','1','length')]:
   self.calls.clear()
   self.assertEqual(run(name,choice,finish)['status'],'failed')
   self.assertEqual(len(self.calls),1)
   self.assertFalse((self.ws/name).exists())
  cfg=self.cfg('llm',window_max_units=1,partition_mode='candidate_choice')
  with patch.object(llm,'invoke',side_effect=AssertionError('model')):
   single=run('single')
  self.assertEqual(single['status'],'ready')
  self.assertEqual(single['work']['dispatches'],0)
  self.assertTrue(all(w['selection_reason']=='single_candidate' for w in a.load(self.ws/'single')[0]['details']['windows']))
  saved['details']['windows'][0]['candidates'][0]['pieces'][0]['text']='changed'
  write_json(target/'chunk.json',saved);self.reseal(target)
  with self.assertRaisesRegex(RagError,'stale_partition_candidates'):a.load(target)
 def test_ollama_partition_enum(self):
  from rag_package import pipeline
  self.lc('ollama')
  args=dict(size_chars=100,overlap_chars=20,unit_max_chars=19,window_max_chars=140,partition_mode='candidate_choice',candidate_format='ollama_enum')
  cfg=self.cfg('llm',**args)
  windows=a.preflight(self.ws/'snapshot',cfg)[-1]
  active=[w for w in windows if w['selection_reason']=='model_choice']
  expected=[w['request']['body'] for w in active]
  self.assertTrue(active)
  for w in windows:
   self.assertEqual(w['request']['body']['format'],{'type':'object','required':['candidate_id'],'additionalProperties':False,
       'properties':{'candidate_id':{'type':'string','enum':[c['id'] for c in w['candidates']]}}})
  def transport(value,finish='stop'):
   def send(method,url,headers,body,timeout):
    if method=='GET':return {'models':[{'name':'fixture-model','digest':DIGEST}]}
    self.calls.append(body)
    return envelope('ollama',json.dumps(value),finish)
   return send
  send=transport({'candidate_id':'2'})
  result=a.build(self.ws/'snapshot',cfg,self.ws/'solo',execute=True,transport=send)
  self.assertEqual(result['status'],'ready',result)
  self.assertEqual(self.calls,expected)
  self.calls.clear()
  search=read_json(self.ws/'fixed.json');search['llm_config']='lc.json';write_json(self.ws/'search.json',search)
  run=pipeline.run(self.ws/'sources.json',cfg,self.ws/'search.json','unmatchedwordxyz',self.ws/'pipeline',execute=True,transport=send)
  self.assertEqual(run['status'],'abstained',run)
  self.assertEqual(self.calls,expected)
  for out in [self.ws/'solo',self.ws/'pipeline/chunks']:
   saved=a.load(out)[0]['details']['windows']
   self.assertEqual([w['request_fingerprint'] for w in saved],[w['request']['request_fingerprint'] for w in windows])
  for n,(value,finish) in enumerate([({'candidate_id':'3'},'stop'),({'candidate_id':'1','extra':1},'stop'),({'candidate_id':'1'},'length')]):
   self.calls.clear()
   self.assertEqual(a.build(self.ws/'snapshot',cfg,self.ws/str(n),execute=True,transport=transport(value,finish))['status'],'failed')
   self.assertEqual(len(self.calls),1)
  single=self.cfg('llm',**dict(args,window_max_units=1,unit_max_chars=60))
  with patch.object(llm,'invoke',side_effect=AssertionError('model')):
   self.assertEqual(a.build(self.ws/'snapshot',single,self.ws/'single',execute=True)['work']['dispatches'],0)
  for provider in ['openai_chat','anthropic_messages']:
   self.lc(provider)
   with self.assertRaisesRegex(RagError,'unsupported_candidate_provider'):a.preflight(self.ws/'snapshot',cfg)
  with self.assertRaisesRegex(RagError,'unsupported_candidate_format'):p.config(dict(read_json(cfg),partition_mode='direct'))
 def test_three_llm_providers_and_tamper(self):
  for provider in ('ollama','openai_chat','anthropic_messages'):
   self.lc(provider);out=self.ws/provider;r=a.build(self.ws/'snapshot',self.cfg('llm'),out,execute=True,transport=self.send(provider),key_resolver=lambda _:KEY);self.assertEqual(r['status'],'ready',r)
   with patch.object(llm,'invoke',side_effect=AssertionError('model')):a.replay(out)
   data=read_json(out/'chunk.json');data['details']['windows'][0]['actual_messages_hash']='a'*64;write_json(out/'chunk.json',data);self.reseal(out)
   with self.assertRaisesRegex(RagError,'stale_window_request'):a.load(out)
 def test_journal_failure_before_and_after_publication(self):
  self.lc();cfg=self.cfg('llm');original=a.atomic_json
  def broken(path,value):
   if any(r['status']=='dispatch_prepared' for r in value['windows']):raise OSError('write')
   return original(path,value)
  with patch.object(a,'atomic_json',side_effect=broken):r=a.build(self.ws/'snapshot',cfg,self.ws/'bad',execute=True,transport=self.send('openai_chat'),key_resolver=lambda _:KEY)
  self.assertEqual(r['status'],'failed');self.assertEqual(self.calls,[]);self.assertEqual(r['work']['dispatches'],0);self.assertFalse(r['outcome_unknown']);self.assertFalse((self.ws/'bad').exists())
  def finalfail(path,value):
   if value['status']=='complete':raise OSError('acknowledgement')
   return original(path,value)
  with patch.object(a,'atomic_json',side_effect=finalfail):r=a.build(self.ws/'snapshot',cfg,self.ws/'ok',execute=True,transport=self.send('openai_chat'),key_resolver=lambda _:KEY)
  self.assertEqual(r['status'],'ready',r);a.replay(self.ws/'ok');self.assertIn('diagnostic_status',r)
 def test_windows_second_failure_unknown_no_resume(self):
  from rag_package.llm.transport import TransportError
  self.lc();cfg=self.cfg('llm');send=self.send('openai_chat');n=[0]
  def bad(*args):
   n[0]+=1
   if n[0]==2:raise TransportError('timeout',outcome_unknown=True)
   return send(*args)
  r=a.build(self.ws/'snapshot',cfg,self.ws/'bad',execute=True,transport=bad,key_resolver=lambda _:KEY);self.assertEqual(r['status'],'failed');self.assertEqual(n[0],2);self.assertTrue(r['outcome_unknown']);self.assertEqual(r['work']['successful_windows'],1);self.assertFalse((self.ws/'bad').exists())
  diag=read_json(Path(r['invocation_path'])/'invocation.json');self.assertEqual(diag['status'],'failed');self.assertEqual(diag['work']['dispatches'],2)
 def test_compare_facts_replay_and_mapping_tamper(self):
  from rag_package import chunk_compare
  qs=[{'id':'q1','question':'생일'},{'id':'q2','question':'연차'}];write_json(self.ws/'questions-new.json',qs)
  d=self.docs[0];facts={'schema_version':1,'source_fingerprint':self.sm['fingerprint'],'questions_hash':fingerprint(qs),'offset_unit':'unicode_codepoint','questions':[{'question_id':q['id'],'required_facts':[{'fact_id':'f1','alternatives':[{'spans':[{'document_id':d['document_id'],'start':0,'end':len(d['text']),'quote':d['text']}]}]}]} for q in qs]}
  paths=[]
  for method in ('fixed','recursive'):
   target=self.ws/('chunks-'+method);a.build(self.ws/'snapshot',self.cfg(method),target)
   path=self.ws/(method+'-rag.json');write_json(path,{'schema_version':3,'chunk_artifact':str(target),'retrieval':{'method':'bm25','top_k':5,'candidate_k':20,'rrf_k':60,'context_budget_chars':2000},'embedding_config':None,'llm_config':'llm-local.json'});paths.append(path)
  with patch.object(embedding,'encode',side_effect=AssertionError('model')),patch.object(llm,'invoke',side_effect=AssertionError('model')):
   s=rag.compare(self.ws/'snapshot',paths,self.ws/'questions-new.json',self.ws/'cmp',facts=facts);self.assertTrue(all(r['status']!='failed' for r in s['rows']),s['rows']);chunk_compare.load(self.ws/'cmp');chunk_compare.report(self.ws/'cmp',self.ws/'report')
  self.assertEqual(s['boundary_inference_calls'],0);self.assertEqual(s['fact_aggregates']['config-1']['contexts']['questions'],2)
  s['rows'][0]['question_id']='q2';s['rows'][1]['question_id']='q1';write_json(self.ws/'cmp/comparison.json',s);m=read_json(self.ws/'cmp/manifest.json');seal(self.ws/'cmp',{k:v for k,v in m['identity'].items() if k!='files'})
  with self.assertRaisesRegex(RagError,'comparison_result_mismatch'):chunk_compare.load(self.ws/'cmp')
 def test_ui_registered_chunking_and_role_clone(self):
  import uuid
  from rag_package.ui_registry import Registry
  from rag_package.ui_jobs import Jobs
  from rag_package.ui_server import UI
  lc=self.lc();reg=Registry(self.ws,[self.ws/'lc.json'],chunk_configs=[self.cfg('fixed'),self.cfg('recursive'),self.cfg('llm')]);jobs=Jobs(reg);model=next(iter(reg.data['configs']));ui=UI(reg,jobs)
  clone=reg.clone_model({'base_config_id':model,'model':'changed-model','max_output_tokens':200,'temperature':0});new=reg.llm(clone['id']);self.assertEqual(new['profiles'][new['roles']['chunking']],lc['profiles'][lc['roles']['chunking']])
  sid=reg.add_artifact(self.ws/'snapshot','snapshot');keys=list(reg.chunk_configs);chunk_ids=[]
  def job(kind,**kw):
   value={'kind':kind,'request_id':str(uuid.uuid4()),**kw};j,_=jobs.submit(value);jobs.thread.join(10);j=jobs.get(j['id']);self.assertEqual(j['status'],'completed',j);self.assertFalse(jobs.submit(value)[1]);return j
  for key in keys[:2]:
   j=job('chunk',snapshot_id=sid,chunk_config_id=key);id=j['artifact_ids'][0];chunk_ids.append(id);self.assertEqual(ui.artifact(id)['kind'],'chunks')
  j=job('chunk',snapshot_id=sid,chunk_config_id=keys[2]);self.assertEqual(ui.artifact(j['artifact_ids'][0])['kind'],'chunk-preview')
  with self.assertRaisesRegex(RagError,'chunking_execution_disabled'):jobs.prepare({'kind':'chunk','request_id':'x','snapshot_id':sid,'chunk_config_id':keys[2],'execute_chunking':True})
  retrieval={'method':'bm25','top_k':5,'candidate_k':20,'rrf_k':60,'context_budget_chars':4000}
  b=job('chunk_build',chunk_id=chunk_ids[0],retrieval=retrieval,llm_config_id=model)['artifact_ids'][0]
  job('ask',build_id=b,llm_config_id=model,question='생일',top_k=5,context_budget_chars=4000,retrieval=retrieval,execute=False)
  j=job('chunk_compare',chunk_ids=chunk_ids,retrieval=retrieval,llm_config_id=model,questions=[{'id':'q1','question':'생일'}],execute=False)
  result=ui.artifact(j['artifact_ids'][0]);self.assertEqual(len(result['result']['rows']),2)
 def test_preflight_all_windows_and_limits(self):
  self.lc();cfg=self.cfg('llm',max_windows=1)
  with self.assertRaisesRegex(RagError,'window_limit'):a.build(self.ws/'snapshot',cfg,self.ws/'no',execute=True,transport=self.send('openai_chat'))
  self.assertFalse(self.calls);self.assertFalse(list(self.ws.glob('no.invocation*')))
  for field,value in [('size_chars',99),('overlap_chars',True),('distance_threshold',float('nan')),('minimum_chars',0)]:
   c={'schema_version':1,'method':'semantic','size_chars':200,'overlap_chars':20,'embedding_config':'x','minimum_chars':40,'distance_threshold':.5};c[field]=value
   with self.assertRaises(RagError):p.config(c)
  cfg=self.cfg('semantic');ep=dict(self.ep,max_chunks=1);write_json(self.ws/'ep.json',ep)
  with self.assertRaisesRegex(RagError,'embedding_chunk_limit'):a.build(self.ws/'snapshot',cfg,self.ws/'cap',execute=True,embedding_backend=self.enc)
  self.assertFalse(self.calls)
 def test_unit_unicode_whitespace_and_llm_bad_output(self):
  docs=[{'document_id':'d','text':'# 제목\n\n😀. \n\n   \n끝?','pages':[]},{'document_id':'e','text':'two!   ','pages':[]}];us=p.units(docs,'s',4)
  for d in docs:self.assertEqual(''.join(u['text'] for u in us if u['document_id']==d['document_id']),d['text'])
  self.assertEqual(us[0]['start'],0);self.assertTrue(any(u['reason']=='forced_unit_split' for u in us))
  self.lc();cfg=self.cfg('llm')
  for n,text in enumerate(['bad json','{"end_unit_ids":["unknown"]}','{"end_unit_ids":[],"rewrite":"new"}']):
   calls=[]
   def send(*args):calls.append(1);return envelope('openai_chat',text)
   r=a.build(self.ws/'snapshot',cfg,self.ws/f'bad{n}',execute=True,transport=send,key_resolver=lambda _:KEY);self.assertEqual(r['status'],'failed');self.assertEqual(len(calls),1);self.assertFalse((self.ws/f'bad{n}').exists())
 def test_prepublication_failure_and_identity_mutations(self):
  self.lc();cfg=self.cfg('llm');old=a.atomic_json
  def broken(path,value):
   if value['status']=='publication_prepared':raise OSError('before publish')
   old(path,value)
  with patch.object(a,'atomic_json',side_effect=broken):r=a.build(self.ws/'snapshot',cfg,self.ws/'fail',execute=True,transport=self.send('openai_chat'),key_resolver=lambda _:KEY)
  self.assertEqual(r['status'],'failed');self.assertFalse((self.ws/'fail').exists());self.assertTrue(r['dispatch_attempted'])
  for n,key in enumerate(('schema_version','unit_policy','base_policy','model','window')):
   out=self.ws/f'tamper{n}';r=a.build(self.ws/'snapshot',cfg,out,execute=True,transport=self.send('openai_chat'),key_resolver=lambda _:KEY);self.assertEqual(r['status'],'ready',r);data=read_json(out/'chunk.json')
   if key=='schema_version':data[key]=2
   elif key=='unit_policy':data[key]['version']='bad'
   elif key=='base_policy':data[key]['window_max_chars']=121
   elif key=='model':data['config']['model']['prompt_version']='other'
   else:data['details']['windows'][0]['unit_ids'].reverse()
   write_json(out/'chunk.json',data);self.reseal(out)
   with self.assertRaises(RagError):a.load(out)
 def test_llm_deadline_transport_timeout_and_hidden_thinking(self):
  from rag_package.llm.transport import TransportError
  self.lc();cfg=self.cfg('llm',total_timeout_seconds=1);timeouts=[]
  def timeout(method,url,headers,body,seconds):timeouts.append(seconds);raise TransportError('timeout',outcome_unknown=True)
  r=a.build(self.ws/'snapshot',cfg,self.ws/'deadline',execute=True,transport=timeout,key_resolver=lambda _:KEY);self.assertTrue(r['outcome_unknown']);self.assertEqual(len(timeouts),1);self.assertLessEqual(timeouts[0],1)
  self.lc('ollama')
  def thinking(method,url,headers,body,seconds):
   if method=='GET':return {'models':[{'name':'fixture-model','digest':DIGEST}]}
   v=envelope('ollama','<think>DO_NOT_STORE</think>{"end_unit_ids":[]}');return v
  r=a.build(self.ws/'snapshot',cfg,self.ws/'think',execute=True,transport=thinking);self.assertEqual(r['status'],'failed');self.assertNotIn('DO_NOT_STORE',(Path(r['invocation_path'])/'invocation.json').read_text())
 def test_fixture_provenance_through_derived_candidates(self):
  from rag_package import reranking
  cfg=self.cfg('semantic');self.assertEqual(a.build(self.ws/'snapshot',cfg,self.ws/'chunks',execute=True,embedding_backend=self.enc)['status'],'ready')
  a.derive(self.ws/'chunks',cfg,self.ws/'derived');a.derive(self.ws/'derived',cfg,self.ws/'derived2')
  c={'schema_version':3,'chunk_artifact':'derived2','retrieval':{'method':'bm25','top_k':5,'candidate_k':20,'rrf_k':60,'context_budget_chars':4000},'embedding_config':None,'llm_config':'llm-local.json'};write_json(self.ws/'r.json',c)
  retrieval.build(self.ws/'snapshot',self.ws/'r.json',self.ws/'b');r=rag.ask(self.ws/'b',self.ws/'r.json','생일',self.ws/'ans');self.assertEqual(r['execution_kind'],'test_fixture')
  c=candidates.freeze(self.ws/'b',self.ws/'ans','q1',20,self.ws/'c');self.assertEqual(c['execution_kind'],'test_fixture');self.assertEqual(c['chunking_provenance']['work']['origin_execution_kind'],'test_fixture')
  n=reranking.run(self.ws/'c','none',self.ws/'none');self.assertEqual(n['candidate_execution_kind'],'test_fixture');self.assertEqual(n['work']['execution_kind'],'none')
 def test_derive_size_model_source_and_vector_errors(self):
  cfg=self.cfg('semantic',overlap_chars=0,size_chars=200,distance_threshold=2,minimum_chars=40);a.build(self.ws/'snapshot',cfg,self.ws/'s',execute=True,embedding_backend=self.enc)
  with self.assertRaisesRegex(RagError,'derived_size_exceeded'):a.derive(self.ws/'s',self.cfg('semantic',overlap_chars=80,size_chars=200,distance_threshold=2,minimum_chars=40),self.ws/'no')
  ep=dict(self.ep,revision='c'*40);write_json(self.ws/'ep.json',ep)
  with self.assertRaisesRegex(RagError,'derive_requires_new_execution'):a.derive(self.ws/'s',cfg,self.ws/'other')
  write_json(self.ws/'ep.json',self.ep)
  data=bytearray((self.ws/'s/unit-vectors.f32').read_bytes());data[0]=data[0]^1;(self.ws/'s/unit-vectors.f32').write_bytes(data);self.reseal(self.ws/'s')
  with self.assertRaisesRegex(RagError,'stale_unit_vectors'):a.load(self.ws/'s')
 def test_restarted_ui_job_never_dispatches(self):
  from rag_package.ui_registry import Registry
  from rag_package.ui_jobs import Jobs
  import uuid
  reg=Registry(self.ws,[self.ws/'llm-local.json']);id=uuid.uuid4().hex;rid=str(uuid.uuid4());write_json(reg.root/'jobs'/(id+'.json'),{'id':id,'request_id':rid,'kind':'chunk','status':'running','payload_hash':'x','request':{},'artifact_ids':[]})
  with patch.object(llm,'invoke',side_effect=AssertionError('resume forbidden')):jobs=Jobs(reg)
  self.assertEqual(jobs.get(id)['status'],'interrupted');self.assertIsNone(jobs.thread)
 def test_deadline_consumed_by_journal_prevents_post(self):
  self.lc();cfg=self.cfg('llm',total_timeout_seconds=1);clock=[100.0];original=a.atomic_json
  def slow(path,value):
   if any(r['status']=='dispatch_prepared' for r in value['windows']):clock[0]+=2
   return original(path,value)
  with patch.object(a.time,'monotonic',side_effect=lambda:clock[0]),patch.object(a,'atomic_json',side_effect=slow):
   r=a.build(self.ws/'snapshot',cfg,self.ws/'expired',execute=True,transport=self.send('openai_chat'),key_resolver=lambda _:KEY)
  self.assertEqual(r['status'],'failed');self.assertEqual(r['work']['dispatches'],0);self.assertFalse(self.calls);self.assertFalse(r['outcome_unknown'])
 def test_sdk_preflight_no_worker_and_owned_timeout(self):
  import subprocess
  from rag_package.reranker import SDK_VERSIONS
  cfg=self.cfg('semantic')
  with patch.object(embedding,'check_files'),patch.object(embedding,'versions',return_value={'wrong':'version'}),patch.object(embedding.subprocess,'Popen',side_effect=AssertionError('no worker')):
   r=a.build(self.ws/'snapshot',cfg,self.ws/'sdk',execute=True)
  self.assertEqual(r['error']['code'],'embedding_sdk_mismatch');self.assertEqual(r['work']['boundary_model_jobs'],0)
  class Process:
   returncode=None
   def communicate(self,*args,**kwargs):
    if self.returncode is None:raise subprocess.TimeoutExpired('owned',1)
    return '',''
   def poll(self):return self.returncode
   def wait(self,**kwargs):return self.returncode
   pid=123
   def kill(self):self.returncode=-9
  proc=Process()
  with patch.object(embedding,'check_files'),patch.object(embedding,'versions',return_value=SDK_VERSIONS),patch.object(embedding.subprocess,'Popen',return_value=proc),patch('rag_package.owned_worker.pressure',return_value={'pressure':'normal'}),patch('rag_package.owned_worker.rss',return_value=1):
   r=a.build(self.ws/'snapshot',cfg,self.ws/'timeout',execute=True)
  self.assertEqual(r['error']['code'],'embedding_timeout');self.assertEqual(r['work']['boundary_model_jobs'],1);self.assertTrue(r['work']['unit_observation']['worker_exited']);self.assertIsNone(r['work']['unit_observation']['completed_items'])
 def test_rule_chunk_cap_before_large_materialization(self):
  from rag_package.chunks import make_chunks
  docs=[{'document_id':'d','text':'a'*11000,'pages':[{'page':1,'start':0,'end':11000}]}]
  for method in ('fixed','recursive','structure'):
   with self.assertRaisesRegex(RagError,'chunk_limit'):make_chunks(docs,'s',{'method':method,'size_chars':100,'overlap_chars':99},max_chunks=10000)
  for method in ('fixed','recursive','structure'):
   cfg={'method':method,'size_chars':100,'overlap_chars':20};self.assertEqual(make_chunks(docs,'s',cfg,max_chunks=10000),make_chunks(docs,'s',cfg))
