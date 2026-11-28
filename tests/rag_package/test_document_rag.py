"""P026 synthetic fixtures; no real model, API, key or external socket access."""
import contextlib
import copy
import io
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from rag_package.documents import snapshot,load_snapshot,parse_pdf
from rag_package.retrieval import build,load_build,config,select
from rag_package.rag import ask,compare
from rag_package.chunks import make_chunks
from rag_package.bm25 import BM25Index
from rag_package.storage import RagError,read_json,write_json,fingerprint,staging,seal,verify
from rag_package.__main__ import main
from test_llm import config as llm_config, envelope, DIGEST, KEY
import test_llm as provider_tests

ROOT=Path(__file__).resolve().parents[2]

class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.d=Path(self.temp.name)
        self.connect=patch.object(socket.socket,'connect',side_effect=AssertionError('external network forbidden'));self.connect.start()
        self.dns=patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS forbidden'));self.dns.start()
    def tearDown(self):
        self.dns.stop();self.connect.stop();self.temp.cleanup()

    def sources(self,documents=None):
        docs=documents or [('one','md','# 자격\r\n생일 휴가 자격은 입사 후 3개월입니다.\r\n\r\n## 제외\r\n수습 직원은 제외합니다.\r\n'),('two','txt','생일 휴가 일수는 매년 1일입니다.\nCafe\u0301 원문입니다.')]
        records=[]
        for ident,fmt,text in docs:
            p=self.d/(ident+'.'+fmt)
            p.write_bytes(text.encode() if isinstance(text,str) else text)
            records.append({'document_id':ident,'title':'표시용제목검색금지','path':p.name,'format':fmt,'synthetic':True})
        write_json(self.d/'sources.json',{'schema_version':1,'documents':records})
        return self.d/'sources.json'

    def cfg(self,method='fixed',size=100,overlap=0,provider='openai_chat',name='rag',budget=1000):
        lc=llm_config(provider,'json_object');write_json(self.d/(name+'-llm.json'),lc)
        c={'schema_version':1,'chunking':{'method':method,'size_chars':size,'overlap_chars':overlap},'retrieval':{'method':'bm25','top_k':10,'context_budget_chars':budget},'llm_config':name+'-llm.json'}
        write_json(self.d/(name+'.json'),c);return self.d/(name+'.json')

    def ready(self,provider='openai_chat'):
        snapshot(self.sources(),self.d/'snapshot');cp=self.cfg(provider=provider);build(self.d/'snapshot',cp,self.d/'build');return cp

    def fake(self,provider,mode='ok'):
        calls=[]
        def send(method,url,headers,body,timeout):
            calls.append((method,url,body))
            if method=='GET':return {'models':[{'name':'fixture-model','digest':DIGEST}]}
            data=json.loads(body['messages'][-1]['content']);ids=[c['chunk_id'] for c in data['contexts']]
            v={'status':'answered','answer':'가상 답변: 자격과 일수를 확인하세요.','citations':[{'chunk_id':cid} for cid in ids]}
            if mode=='unknown':v['citations']=[{'chunk_id':'not-dispatched'}]
            elif mode=='duplicate':v['citations']*=2
            elif mode=='extra':v['quote']=KEY
            elif mode=='empty':v['citations']=[]
            elif mode=='abstained_refs':v['status']='abstained'
            elif mode=='abstained':v={'status':'abstained','answer':'근거 부족','citations':[]}
            if mode=='invalid_json':content='{"status":'+KEY
            else:content=json.dumps(v,ensure_ascii=False)
            return envelope(provider,content,'length' if mode=='truncated' else 'tool_use' if mode=='tools' else 'refusal' if mode=='refused' else None)
        return send,calls

    def test_snapshot_normalization_identity_and_original_copy(self):
        src=self.sources();a=snapshot(src,self.d/'s1');b=snapshot(src,self.d/'s2')
        self.assertEqual(a['fingerprint'],b['fingerprint'])
        m,docs=load_snapshot(self.d/'s1')
        self.assertIn('Café',docs[1]['text']);self.assertNotIn('\r',docs[0]['text'])
        self.assertNotIn(str(self.d),json.dumps(m));self.assertTrue(all(d['synthetic'] for d in docs))
        self.assertEqual((self.d/'one.md').read_bytes(),(self.d/'s1/one/original.md').read_bytes())
        r=read_json(src);r['documents'][0]['synthetic']=False;write_json(src,r)
        c=snapshot(src,self.d/'s3');self.assertNotEqual(a['fingerprint'],c['fingerprint'])
        (self.d/'one.md').write_text('changed');d=snapshot(src,self.d/'s4');self.assertNotEqual(c['fingerprint'],d['fingerprint'])

    def test_chunks_long_coverage_overlap_and_heading_scope(self):
        text='# 규정\n\n'+'대상 조건입니다. 예외 조건도 보존합니다.\n'*1000+'\n## 끝\n마지막 조건입니다.'
        self.assertGreater(len(text),20000)
        snapshot(self.sources([('long','md',text),('plain','txt','heading 없음. '*50)]),self.d/'s')
        m,docs=load_snapshot(self.d/'s')
        for method in ('fixed','recursive','structure'):
            for overlap in (0,99):
                chunks,maps=make_chunks(docs,m['fingerprint'],{'method':method,'size_chars':100,'overlap_chars':overlap})
                for d in docs:
                    coverage=sorted((r['start'],r['end']) for r in maps['coverage'] if r['document_id']==d['document_id']);cursor=0
                    for a,b in coverage:self.assertLessEqual(a,cursor);cursor=max(cursor,b)
                    self.assertEqual(cursor,len(d['text']))
                for c in chunks:
                    d=next(x for x in docs if x['document_id']==c['document_id']);self.assertEqual(c['text'],d['text'][c['start']:c['end']]);self.assertLessEqual(len(c['text']),100)
                    if method=='structure' and c['heading_path']==['규정','끝']:self.assertGreaterEqual(c['start'],text.index('## 끝'))
                if method=='structure':self.assertEqual(maps['detection'][1]['fallback'],'recursive_no_heading_detected')
        korean='제1장 총칙\n대상\n제1조 자격\n조건'
        d=copy.deepcopy(docs[0]);d['text']=korean;d['pages']=[{'page':1,'start':0,'end':len(korean)}]
        rows,_=make_chunks([d],'fp',{'method':'structure','size_chars':100,'overlap_chars':20})
        self.assertEqual(rows[-1]['heading_path'],['제1장 총칙','제1조 자격'])

    def test_whitespace_coverage(self):
        text='a'+(' '*250)+'b'
        snapshot(self.sources([('spaced','txt',text)]),self.d/'s');m,docs=load_snapshot(self.d/'s')
        chunks,maps=make_chunks(docs,m['fingerprint'],{'method':'fixed','size_chars':100,'overlap_chars':0})
        self.assertEqual(len(chunks),2);self.assertTrue(any(x['excluded']=='whitespace_only' for x in maps['coverage']))

    def test_bm25_manual_order_ties_and_budget_skip(self):
        chunks={'a':{'text':'apple apple'},'b':{'text':'apple apple'},'c':{'text':'banana'}}
        hits=BM25Index(chunks).search('APPLE',3)[1];self.assertEqual([r['chunk_id'] for r in hits],['a','b'])
        self.assertGreater(hits[0]['score'],0);self.assertEqual(BM25Index(chunks).search('missing',3)[1],[])
        rows=[{'chunk_id':'a','text':'apple '*30},{'chunk_id':'b','text':'apple'}]
        candidates,ctx,excluded=select(rows,'apple',{'top_k':2,'context_budget_chars':10})
        self.assertEqual([x['chunk_id'] for x in ctx],['b']);self.assertEqual(excluded[0]['reason'],'budget')
        with self.assertRaises(RagError):select(rows,' ',{'top_k':1,'context_budget_chars':10})
        cp=self.ready();r=ask(self.d/'build',cp,'표시용제목검색금지',self.d/'no-title')
        self.assertEqual(r['status'],'abstained')

    def test_build_identity_llm_and_query_settings(self):
        cp=self.ready();first=verify(self.d/'build','build')
        other=self.cfg(name='other',provider='anthropic_messages',budget=1)
        m=build(self.d/'snapshot',other,self.d/'other-build')
        self.assertEqual(m['identity']['index_fingerprint'],first['identity']['index_fingerprint'])
        self.assertEqual(m['identity']['chunk_fingerprint'],first['identity']['chunk_fingerprint'])
        ask(self.d/'build',other,'생일',self.d/'other-answer')
        changed=self.cfg(method='recursive',name='changed')
        with self.assertRaises(RagError):ask(self.d/'build',changed,'생일',self.d/'stale')

    def test_three_provider_e2e_exact_citations(self):
        for provider in ('ollama','openai_chat','anthropic_messages'):
            with self.subTest(provider=provider):
                folder=self.d/provider;folder.mkdir();old=self.d;self.d=folder
                try:
                    cp=self.ready(provider);send,calls=self.fake(provider)
                    r=ask(self.d/'build',cp,'생일 휴가',self.d/'answer',execute=True,transport=send,key_resolver=lambda _:KEY)
                    self.assertEqual(r['status'],'answered');self.assertEqual(r['execution_kind'],'test_fixture');self.assertTrue(r['dispatch_attempted'])
                    self.assertEqual(sum(m=='POST' for m,_,_ in calls),1)
                    sent=next(body for method,_,body in calls if method=='POST')
                    self.assertEqual(sent,r['preview']['body'])
                    if provider=='ollama':
                        schema=sent['format']
                        self.assertEqual(schema['required'],['status','answer','citations'])
                        self.assertFalse(schema['additionalProperties'])
                        citation=schema['properties']['citations']['items']
                        self.assertFalse(citation['additionalProperties'])
                        self.assertEqual(citation['properties']['chunk_id']['enum'],[c['chunk_id'] for c in r['contexts']])
                    _,docs=load_snapshot(self.d/'build/snapshot')
                    self.assertEqual({c['document_id'] for c in r['answer']['citations']},{'one','two'})
                    for c in r['answer']['citations']:
                        d=next(d for d in docs if d['document_id']==c['document_id']);self.assertEqual(c['quote'],d['text'][c['start']:c['end']]);self.assertEqual(c['pages'][0]['page'],1)
                    self.assertIsNone(r['metrics']['faithfulness']['value']);self.assertNotIn(KEY,(self.d/'answer/result.json').read_text())
                finally:self.d=old

    def test_preview_and_no_context_no_key_or_network(self):
        cp=self.ready()
        def forbidden(*a,**kw):raise AssertionError('must not invoke')
        with patch('rag_package.llm.invoke',side_effect=forbidden),patch('os.environ.get',side_effect=forbidden):
            a=ask(self.d/'build',cp,'생일',self.d/'preview')
            b=ask(self.d/'build',cp,'absentword',self.d/'empty',execute=True,transport=forbidden,key_resolver=forbidden)
        self.assertEqual(a['status'],'preview');self.assertEqual(b['status'],'abstained');self.assertFalse(b['dispatch_attempted'])
        self.assertEqual(b['generation_request_upper_bound'],0)

    def test_business_and_provider_failures_not_answers(self):
        cp=self.ready()
        for mode in ('unknown','duplicate','extra','empty','abstained_refs','invalid_json','truncated','tools','refused'):
            send,calls=self.fake('openai_chat',mode)
            r=ask(self.d/'build',cp,'생일',self.d/mode,execute=True,transport=send,key_resolver=lambda _:KEY)
            self.assertEqual(r['status'],'failed');self.assertIsNone(r['answer']);self.assertEqual(len(calls),1)
            self.assertNotIn(KEY,(self.d/mode/'result.json').read_text())
            self.assertNotIn('content',r['provider_result']);self.assertNotIn('parsed_json',r['provider_result'])
        send,_=self.fake('openai_chat','abstained');r=ask(self.d/'build',cp,'생일',self.d/'abstain',execute=True,transport=send,key_resolver=lambda _:KEY)
        self.assertEqual(r['status'],'abstained')

    def test_compare_all_rows_failures_axes_and_labels(self):
        cp=self.ready();other=self.cfg(name='other',method='recursive')
        write_json(self.d/'qs.json',[{'id':'build','question':'생일'},{'id':'q2','question':'absentword'}])
        send,calls=self.fake('openai_chat','unknown')
        r=compare(self.d/'snapshot',[cp,other],self.d/'qs.json',self.d/'compare',execute=True,transport=send,key_resolver=lambda _:KEY)
        self.assertEqual(len(r['rows']),4);self.assertEqual(r['status_counts'],{'abstained':2,'failed':2});self.assertEqual(len(calls),2)
        self.assertEqual(r['configs'][1]['changed_axes_vs_first'],['chunking.method']);self.assertEqual(r['generation_request_upper_bound'],4)
        self.assertTrue(all(x['source_fingerprint']==r['source_fingerprint'] for x in r['rows']));self.assertEqual(r['execution_kind'],'test_fixture')
        self.assertIsNone(r['cost']);self.assertEqual(r['metrics']['correctness']['reason'],'ground_truth_not_configured')
        self.assertTrue((self.d/'compare/comparison.md').is_file())

    def test_unknown_options_and_invalid_sources(self):
        cp=self.cfg()
        for part,key,value in [('chunking','method','semantic'),('chunking','method','llm'),('retrieval','method','dense'),('retrieval','method','hybrid'),('chunking','size_chars',True),('chunking','overlap_chars',100),('retrieval','top_k',101),('retrieval','context_budget_chars',0)]:
            c=read_json(cp);c[part][key]=value;write_json(self.d/'bad.json',c)
            with self.assertRaises(RagError):config(self.d/'bad.json')
        c=read_json(cp);c['reranker']={};write_json(self.d/'bad.json',c)
        with self.assertRaises(RagError):config(self.d/'bad.json')
        src=self.sources();v=read_json(src);v['documents'].append(v['documents'][0]);write_json(src,v)
        with self.assertRaises(RagError):snapshot(src,self.d/'dupe')
        for fmt,data in [('txt',b'\xff'),('html','text')]:
            with self.assertRaises(RagError):snapshot(self.sources([('bad',fmt,data)]),self.d/(fmt+'-bad'))
        src=self.sources();(self.d/'one.md').unlink()
        with self.assertRaises(RagError):snapshot(src,self.d/'missing')
        src=self.sources([('big','txt','small')])
        with (self.d/'big.txt').open('wb') as f:f.truncate(20*1024*1024+1)
        with self.assertRaises(RagError):snapshot(src,self.d/'oversize')

    def test_tamper_paths_and_no_clobber(self):
        cp=self.ready()
        with self.assertRaises(RagError):build(self.d/'snapshot',cp,self.d/'build')
        with staging(self.d/'empty') as tmp:(tmp/'x').write_text('original')
        with self.assertRaises(RagError):
            with staging(self.d/'raced') as tmp:
                (tmp/'x').write_text('staged');(self.d/'raced').mkdir()
        self.assertTrue((self.d/'raced').is_dir());self.assertEqual(list((self.d/'raced').iterdir()),[])
        (self.d/'build/chunks.json').write_text('[]')
        with self.assertRaises(RagError):ask(self.d/'build',cp,'생일',self.d/'tamper')
        m=read_json(self.d/'snapshot/manifest.json');m['identity']['files']['../outside']='0'*64;m['fingerprint']=fingerprint(m['identity']);write_json(self.d/'snapshot/manifest.json',m)
        with self.assertRaises(RagError):load_snapshot(self.d/'snapshot')

    def pdf(self,name='sample',pages=('leave eligibility three months','leave one day annually'),encrypted=False):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        writer=PdfWriter()
        for text in pages:
            page=writer.add_blank_page(600,800)
            if text:
                font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
                page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
                stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 30 750 Td ('+text+') Tj ET').encode())
                page[NameObject('/Contents')]=writer._add_object(stream)
        if encrypted:writer.encrypt('synthetic-password')
        p=self.d/(name+'.pdf');writer.write(p);return p

    def test_pdf_physical_pages_and_cross_page_citations(self):
        pdf=self.pdf();source=self.sources([('pdf','pdf',pdf.read_bytes()),('other','txt','leave probation exclusion')])
        snapshot(source,self.d/'snapshot');m,docs=load_snapshot(self.d/'snapshot')
        d=docs[0];self.assertEqual([p['page'] for p in d['pages']],[1,2])
        self.assertEqual(d['text'],'leave eligibility three months\n\nleave one day annually')
        self.assertEqual(d['pages'][1]['start'],len('leave eligibility three months')+2)
        cp=self.cfg(size=100);build(self.d/'snapshot',cp,self.d/'build');send,_=self.fake('openai_chat')
        r=ask(self.d/'build',cp,'leave',self.d/'answer',execute=True,transport=send,key_resolver=lambda _:KEY)
        citation=next(x for x in r['answer']['citations'] if x['document_id']=='pdf')
        self.assertEqual([p['page'] for p in citation['pages']],[1,2]);self.assertEqual(citation['quote'],d['text'])
        self.assertEqual(sum(p['canonical_end']-p['canonical_start'] for p in citation['pages']),len(citation['quote'])-2)

    def test_existing_synthetic_handbook_pdf(self):
        p=ROOT/'2. Document Chunking/data/source-v4/output/pdf/hr-handbook.pdf'
        write_json(self.d/'sources.json',{'schema_version':1,'documents':[{'document_id':'handbook','title':'가상 규정집','path':str(p),'format':'pdf','synthetic':True}]})
        m=snapshot(self.d/'sources.json',self.d/'snapshot');self.assertEqual(m['identity']['status'],'ready')
        _,docs=load_snapshot(self.d/'snapshot');self.assertEqual(len(docs[0]['pages']),23)
        cp=self.cfg(method='structure',size=400);build(self.d/'snapshot',cp,self.d/'build');send,_=self.fake('openai_chat')
        r=ask(self.d/'build',cp,'생일',self.d/'answer',execute=True,transport=send,key_resolver=lambda _:KEY)
        self.assertEqual(r['status'],'answered')
        for c in r['answer']['citations']:self.assertEqual(c['quote'],docs[0]['text'][c['start']:c['end']])

    def test_pdf_failures_and_optional_dependency(self):
        cases=[('blank',self.pdf('blank',('',)).read_bytes(),'empty_or_scanned_page_ocr_not_supported'),
               ('encrypted',self.pdf('encrypted',encrypted=True).read_bytes(),'encrypted_pdf_unsupported'),
               ('corrupt',b'%PDF-corrupt','pdf_parse_failed'),
               ('many',self.pdf('many',('',)*101).read_bytes(),'pdf_page_limit')]
        for name,data,reason in cases:
            m=snapshot(self.sources([(name,'pdf',data)]),self.d/(name+'-snapshot'))
            self.assertEqual(m['identity']['status'],'needs_review');self.assertEqual(m['identity']['documents'][0]['reason'],reason)
            with self.assertRaises(RagError):build(self.d/(name+'-snapshot'),self.cfg(name=name+'-cfg'),self.d/(name+'-build'))
        with patch('rag_package.documents.subprocess.run',side_effect=subprocess.TimeoutExpired('pdf',30)):
            self.assertEqual(parse_pdf(self.d/'fake',self.d/'parse-result')['reason'],'pdf_timeout')
        from rag_package.pdf_worker import extract
        with patch('rag_package.pdf_worker.importlib.import_module',side_effect=ImportError):
            self.assertEqual(extract(self.d/'fake')['reason'],'pypdf_missing')
        # Text path still succeeds when PDF extraction is unavailable.
        with patch('rag_package.documents.parse_pdf',side_effect=AssertionError('PDF not needed')):
            self.assertEqual(snapshot(self.sources(),self.d/'text-only')['identity']['status'],'ready')

    def test_snapshot_page_metadata_and_index_tamper(self):
        cp=self.ready();p=self.d/'snapshot/manifest.json';m=read_json(p)
        m['identity']['documents'][0]['pages'][0]['end']+=1;m['fingerprint']=fingerprint(m['identity']);write_json(p,m)
        with self.assertRaises(RagError):load_snapshot(self.d/'snapshot')
        (self.d/'build/index.json').write_text('{}')
        with self.assertRaises(RagError):load_build(self.d/'build',config(cp)[0])

    def test_post_dispatch_write_failure_preserves_attempt_without_retry(self):
        cp=self.ready()
        import rag_package.rag as module
        original=module.write_json
        for n,exc in enumerate((OSError(KEY),UnicodeError(KEY))):
            send,calls=self.fake('openai_chat')
            def fail(path,value):
                if Path(path).name=='result.json':raise exc
                return original(path,value)
            with patch.object(module,'write_json',side_effect=fail),self.assertRaises(RagError) as caught:
                ask(self.d/'build',cp,'생일',self.d/f'failed-{n}',execute=True,transport=send,key_resolver=lambda _:KEY)
            self.assertTrue(caught.exception.dispatch_attempted);self.assertEqual(caught.exception.code,'output_write_failed');self.assertEqual(len(calls),1)
            self.assertNotIn(KEY,str(caught.exception));self.assertFalse((self.d/f'failed-{n}').exists())
        send,calls=self.fake('openai_chat')
        def fail_result(path,value):
            if Path(path).name=='result.json':raise OSError(KEY)
            return original(path,value)
        write_json(self.d/'qs.json',[{'id':'q1','question':'생일'}])
        with patch.object(module,'write_json',side_effect=fail_result):
            r=compare(self.d/'snapshot',[cp,cp],self.d/'qs.json',self.d/'failed-compare',execute=True,transport=send,key_resolver=lambda _:KEY)
        self.assertEqual(len(calls),2);self.assertTrue(all(row['dispatch_attempted'] for row in r['rows']));self.assertTrue(all(row['failed_stage']=='publish' for row in r['rows']))
        send,calls=self.fake('openai_chat')
        def routed(*args,**kwargs):return ask(*args,**kwargs,transport=send,key_resolver=lambda _:KEY)
        with patch('rag_package.__main__.ask',side_effect=routed),patch.object(module,'write_json',side_effect=fail_result),contextlib.redirect_stdout(io.StringIO()) as out:
            code=main(['ask','--run',str(self.d/'build'),'--config',str(cp),'--question','생일','--out',str(self.d/'cli-fail'),'--execute'])
        self.assertEqual(code,2);self.assertTrue(json.loads(out.getvalue())['dispatch_attempted']);self.assertEqual(len(calls),1);self.assertNotIn(KEY,out.getvalue())

    def test_cli_preview_and_duplicate_questions(self):
        src=self.sources();cp=self.cfg()
        for args in (['snapshot','--sources',str(src),'--out',str(self.d/'s')],['build','--snapshot',str(self.d/'s'),'--config',str(cp),'--out',str(self.d/'b')],['ask','--run',str(self.d/'b'),'--config',str(cp),'--question','생일','--out',str(self.d/'a')]):
            with contextlib.redirect_stdout(io.StringIO()) as out:self.assertEqual(main(args),0)
            self.assertNotIn('입사',out.getvalue())
        write_json(self.d/'q.json',[{'id':'same','question':'생일'},{'id':'same','question':'휴가'}])
        with self.assertRaises(RagError):compare(self.d/'s',[cp,cp],self.d/'q.json',self.d/'bad-qs')

class RagHTTPTests(provider_tests.HTTPTests):
    test_http_invoke_cli_and_no_proxy=None
    test_real_transport_errors=None
    def test_rag_uses_real_http_transport_with_fixture_label(self):
        # The inherited server returns a plain response: schema rejection proves
        # snapshot→retrieval→P025 real HTTP path ran, without faking a successful answer.
        from rag_package.llm.transport import http_transport
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);(d/'doc.txt').write_text('leave eligibility')
            write_json(d/'sources.json',{'schema_version':1,'documents':[{'document_id':'doc','title':'sample','path':'doc.txt','format':'txt','synthetic':True}]})
            lc=llm_config('ollama','json_object');lc['profiles']['one']['base_url']=self.base;write_json(d/'llm.json',lc)
            write_json(d/'cfg.json',{'schema_version':1,'chunking':{'method':'fixed','size_chars':100,'overlap_chars':0},'retrieval':{'method':'bm25','top_k':2,'context_budget_chars':200},'llm_config':'llm.json'})
            snapshot(d/'sources.json',d/'s');build(d/'s',d/'cfg.json',d/'b')
            r=ask(d/'b',d/'cfg.json','leave',d/'a',execute=True,transport=http_transport)
            self.assertEqual(r['execution_kind'],'test_fixture');self.assertTrue(r['dispatch_attempted']);self.assertEqual(r['status'],'failed')
            self.assertEqual([x[:2] for x in self.hits],[('GET','/api/tags'),('POST','/api/chat'),('GET','/api/tags')])
