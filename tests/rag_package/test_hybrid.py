"""Independent arithmetic + real package artifact/HTTP contracts, no pretrained weights."""
import copy,json,math,tempfile,unittest,struct,time,threading
from pathlib import Path
from unittest.mock import patch
from rag_package import embedding
from rag_package.retrieval import build,load_build,select,rrf,cosine,config
from rag_package.rag import ask,compare
from rag_package.search_metrics import metrics,aggregate
from rag_package.storage import fingerprint,read_json,write_json,RagError,seal,digest
from rag_package.workspace import init
from rag_package.documents import snapshot

class HybridTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.ws=self.root/'ws';init(self.ws);self.calls=[]
  self.p={'schema_version':1,'model_id':'intfloat/multilingual-e5-small','revision':'a'*40,'local_path':'/SYNTHETIC_NOT_LOADED','file_manifest':{'config.json':'b'*64},'device':'cpu','dtype':'float32','max_input_tokens':512,'batch_size':1,'timeout_seconds':1,'max_chunks':2000}
  write_json(self.ws/'embedding.json',self.p);c=read_json(self.ws/'fixed.json');c.update(schema_version=2,embedding_config='embedding.json');c['retrieval'].update(method='hybrid',candidate_k=20,rrf_k=60);self.c=c;write_json(self.ws/'hybrid.json',c);snapshot(self.ws/'sources.json',self.ws/'snapshot')
 def backend(self,p,texts,ids,kind):
  self.calls.append((kind,list(ids)));dim=embedding.CATALOG[p['model_id']]['dimension'];rows=[]
  for n,t in enumerate(texts):
   row=[0.0]*dim;row[0]=1 if kind=='query' or '생일' in t else -1;row[1]=.1*n;rows.append(row)
  return {'vectors':rows,'sdk_versions':{'synthetic':'1'}}
 def test_arithmetic(self):
  make=lambda xs:[{'chunk_id':x,'score':10-n} for n,x in enumerate(xs)]
  r=rrf(make('abc'),make('bda'),60);self.assertEqual([x['chunk_id'] for x in r],list('badc'));self.assertAlmostEqual(r[0]['score'],1/62+1/61)
  with self.assertRaises(RagError):rrf(make('aa'),[],60)
  r=cosine([{'chunk_id':x} for x in 'cba'],[[0,1],[1,0],[-1,0]],[1,0],3);self.assertEqual([x['chunk_id'] for x in r],list('bca'));self.assertEqual(r[-1]['score'],-1)
  self.assertEqual(embedding.normalize([[3,4]],1,2),[[.6,.8]])
  for v in ([[0,0]],[[float('nan'),1]],[[1]],[]):
   with self.assertRaises(RagError):embedding.normalize(v,1,2)
 def test_flags_reuse_and_identity(self):
  with self.assertRaisesRegex(RagError,'retrieval_execution_required'):build(self.ws/'snapshot',self.ws/'hybrid.json',self.ws/'no')
  self.assertEqual(self.calls,[])
  bm=build(self.ws/'snapshot',self.ws/'hybrid.json',self.ws/'build',execute_retrieval=True,embedding_backend=self.backend)
  c,lc=config(self.ws/'hybrid.json');m,docs,chunks=load_build(self.ws/'build',c)
  index=read_json(self.ws/'build/index.json');self.assertEqual(index['identity']['vectors_hash'],digest((self.ws/'build/vectors.f32').read_bytes()))
  c['retrieval'].update(top_k=2,candidate_k=10,rrf_k=5,context_budget_chars=400);write_json(self.ws/'query.json',c)
  with self.assertRaisesRegex(RagError,'retrieval_execution_required'):ask(self.ws/'build',self.ws/'query.json','생일 휴가',self.ws/'missing')
  r=ask(self.ws/'build',self.ws/'query.json','생일 휴가',self.ws/'answer',execute_retrieval=True,embedding_backend=self.backend);self.assertFalse(r['dispatch_attempted']);self.assertEqual([x[0] for x in self.calls],['document','query']);self.assertIn('components',r['candidates'][0]);self.assertEqual(r['execution_kind'],'test_fixture')
  build(self.ws/'snapshot',self.ws/'query.json',self.ws/'reuse',execute_retrieval=True,embedding_backend=self.backend,reuse=self.ws/'build');self.assertEqual(len(self.calls),2)
  # Resealing outer manifest alone must not make different vector bytes the same index.
  raw=bytearray((self.ws/'build/vectors.f32').read_bytes());raw[:4]=struct.pack('<f',-1);(self.ws/'build/vectors.f32').write_bytes(raw);seal(self.ws/'build',{k:v for k,v in m['identity'].items() if k!='files'})
  with self.assertRaisesRegex(RagError,'stale_index'):load_build(self.ws/'build',c)
 def test_sdk_and_model_mismatch(self):
  build(self.ws/'snapshot',self.ws/'hybrid.json',self.ws/'build',execute_retrieval=True,embedding_backend=self.backend)
  def different(*a):r=self.backend(*a);r['sdk_versions']={'synthetic':'2'};return r
  with self.assertRaisesRegex(RagError,'stale_embedding_sdk'):ask(self.ws/'build',self.ws/'hybrid.json','query',self.ws/'a',execute_retrieval=True,embedding_backend=different)
  p=dict(self.p,model_id='BAAI/bge-m3');write_json(self.ws/'embedding.json',p)
  with self.assertRaises(RagError):load_build(self.ws/'build',config(self.ws/'hybrid.json')[0])
  build(self.ws/'snapshot',self.ws/'hybrid.json',self.ws/'bge',execute_retrieval=True,embedding_backend=self.backend)
 def test_metrics_and_compare_replay(self):
  m=metrics([{'chunk_id':'b'},{'chunk_id':'a'}],{'a':2,'b':0,'c':1},3,True);self.assertAlmostEqual(m['values']['precision'],1/3);self.assertEqual(m['values']['recall'],.5);self.assertEqual(m['values']['mrr'],.5);self.assertAlmostEqual(m['values']['ndcg'],(3/math.log2(3))/(3+1/math.log2(3)))
  self.assertIsNone(metrics([],{},3,True)['values']['recall']);self.assertEqual(metrics([],{},3,True)['values']['precision'],0);self.assertEqual(metrics([],{},3,False)['reason'],'judgments_incomplete')
  bm=build(self.ws/'snapshot',self.ws/'hybrid.json',self.ws/'build',execute_retrieval=True,embedding_backend=self.backend);chunks=read_json(self.ws/'build/chunks.json');qs=[{'id':'q1','question':'생일 휴가'}];write_json(self.ws/'qs.json',qs)
  qr={'schema_version':1,'source_fingerprint':bm['identity']['source_fingerprint'],'chunk_fingerprint':bm['identity']['chunk_fingerprint'],'questions_hash':fingerprint(qs),'judgments_complete':True,'judgments':{'q1':{chunks[0]['chunk_id']:2}}}
  self.calls=[];r=compare(self.ws/'snapshot',[self.ws/'hybrid.json']*2,self.ws/'qs.json',self.ws/'comparison',execute_retrieval=True,embedding_backend=self.backend,qrels=qr)
  self.assertEqual([x[0] for x in self.calls],['document','query','query']);self.assertEqual(r['embedding_work']['documents'],len(chunks))
  for row in r['rows']:self.assertEqual(row['metrics'],read_json(self.ws/'comparison'/row['result_path'])['metrics'])
  self.assertEqual(r['search_metrics']['config-1']['precision']['valid'],1)
  qr['judgments']['q1']['unknown']=1
  bad=compare(self.ws/'snapshot',[self.ws/'hybrid.json']*2,self.ws/'qs.json',self.ws/'bad',execute_retrieval=True,embedding_backend=self.backend,qrels=qr);self.assertTrue(all(x['status']=='failed' for x in bad['rows']));self.assertEqual(bad['search_metrics']['config-1']['precision']['valid'],0)
 def test_manifest_and_worker_timeout(self):
  p=copy.deepcopy(self.p);p['file_manifest']={'../escape':'b'*64}
  with self.assertRaises(RagError):embedding.profile(p)
  p=copy.deepcopy(self.p);p['revision']='0'*40;self.assertFalse(embedding.configured(p))
  with self.assertRaisesRegex(RagError,'embedding_configuration_required'):embedding.check_files(p)
  import subprocess
  class FakeProcess:
   def __init__(self):self.killed=False;self.returncode=None
   def communicate(self,*a,**kw):
    if not self.killed:raise subprocess.TimeoutExpired('owned fixture',1)
    return ('','')
   def kill(self):self.killed=True;self.returncode=-9
   def poll(self):return self.returncode
   def wait(self,**kwargs):return self.returncode
   pid=123
  proc=FakeProcess()
  with patch.object(embedding,'check_files'),patch.object(embedding,'versions',return_value={}),patch.object(embedding.subprocess,'Popen',return_value=proc),patch('rag_package.owned_worker.pressure',return_value={'pressure':'normal'}),patch('rag_package.owned_worker.rss',return_value=1):
   with self.assertRaisesRegex(RagError,'embedding_timeout'):embedding.encode(self.p,['x'],['a'],'document',execute=True)
  self.assertTrue(proc.killed)
 def test_single_worker_and_bm25_zero_embeddings(self):
  active=[0,0]
  def backend(*args):
   active[0]+=1;active[1]=max(active);time.sleep(.02);r=self.backend(*args);active[0]-=1;return r
  ts=[threading.Thread(target=lambda:embedding.encode(self.p,['x'],['x'],'query',execute=True,backend=backend)) for _ in range(2)]
  for t in ts:t.start()
  for t in ts:t.join()
  self.assertEqual(active[1],1);self.calls=[]
  build(self.ws/'snapshot',self.ws/'fixed.json',self.ws/'bm',embedding_backend=self.backend);ask(self.ws/'bm',self.ws/'fixed.json','생일',self.ws/'bma',embedding_backend=self.backend);self.assertEqual(self.calls,[])
 def test_ui_registry_jobs_and_stale(self):
  from rag_package.ui_registry import Registry
  from rag_package.ui_jobs import Jobs
  import uuid
  registry=Registry(self.ws,[self.ws/'llm-local.json'],self.ws/'sources.json',embedding_configs=[self.ws/'embedding.json']);model=next(iter(registry.data['configs']));eid=next(iter(registry.embeddings))
  jobs=Jobs(registry,allow_retrieval=True,embedding_backend=self.backend)
  def run(kind,**kw):
   job,new=jobs.submit({'request_id':str(uuid.uuid4()),'kind':kind,**kw});jobs.thread.join(5);return jobs.get(job['id'])
  sn=run('snapshot',input_ids=list(registry.inputs));self.assertEqual(sn['status'],'completed');sid=sn['artifact_ids'][0]
  b=run('build',snapshot_id=sid,chunking=self.c['chunking'],retrieval=self.c['retrieval'],llm_config_id=model,embedding_config_id=eid,execute_retrieval=True);self.assertEqual(b['status'],'completed')
  a=run('ask',build_id=b['artifact_ids'][0],llm_config_id=model,question='birthday',top_k=5,context_budget_chars=4000,retrieval=self.c['retrieval'],embedding_config_id=eid,execute_retrieval=True);self.assertEqual(a['status'],'completed');self.assertEqual(a['execution_kind'],'test_fixture');self.assertFalse(a['dispatch_attempted'])
  bad={'request_id':str(uuid.uuid4()),'kind':'build','snapshot_id':sid,'chunking':self.c['chunking'],'retrieval':self.c['retrieval'],'llm_config_id':model,'embedding_config_id':eid}
  with self.assertRaisesRegex(RagError,'retrieval_execution_required'):jobs.submit(bad)
  write_json(self.ws/'embedding.json',dict(self.p,revision='c'*40))
  with self.assertRaisesRegex(RagError,'stale_embedding_config'):registry.embedding(eid)
 def test_no_answer_groups_and_write_failure(self):
  from rag_package import rag
  rows=[{'config_id':'c','status':'preview','metrics':{'retrieval':metrics([],{},2,True)}},{'config_id':'c','status':'failed','metrics':{}}]
  summary=aggregate(rows);self.assertEqual(summary['c']['groups']['no_answer']['precision']['value'],0);self.assertEqual(summary['c']['recall']['exclusion_reasons'],{'no_relevant':1,'failed':1})
  build(self.ws/'snapshot',self.ws/'hybrid.json',self.ws/'build',execute_retrieval=True,embedding_backend=self.backend)
  real=rag.write_json
  def failing(path,value):
   if Path(path).name=='result.json':raise OSError('synthetic write failure')
   return real(path,value)
  with patch.object(rag,'write_json',side_effect=failing):
   with self.assertRaises(RagError) as err:ask(self.ws/'build',self.ws/'hybrid.json','birthday',self.ws/'fail',execute_retrieval=True,embedding_backend=self.backend)
  self.assertFalse(err.exception.dispatch_attempted);self.assertEqual([x[0] for x in self.calls],['document','query'])
