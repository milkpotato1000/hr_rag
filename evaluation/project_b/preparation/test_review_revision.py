"""P021 source/meaning, offline replay and structural accessibility regressions."""
import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from core import read, write, file_hash
import report
import review_revision as revision

ROOT = Path(__file__).resolve().parent
PARENT = ROOT/'artifacts/run001'


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.quotes=0; self.details=0; self.links=[]; self.ids=set(); self.scripts=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.add(attrs['id'])
        if tag=='details':
            self.details+=1
            if 'open' in attrs:raise AssertionError('detail starts expanded')
        if tag=='blockquote' and 'details' not in self.stack:self.quotes+=1
        if tag=='a':self.links.append(attrs['href'])
        if tag=='script':self.scripts.append(attrs)
        if tag not in ('meta','br','hr','link','input','img'):self.stack.append(tag)
    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack.pop()!=tag:pass


class ReviewRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet, cls.mapping = revision.build(PARENT)
        cls.old = read(PARENT/'packet.json')

    def test_only_contracted_semantic_changes_and_stable_ids(self):
        old={c['id']:c for q in self.old['questions'] for c in q['codex_source_checked']['claims']}
        new={c['id']:c for q in self.packet['questions'] for c in q['codex_source_checked']['claims']}
        self.assertEqual(len(old),48); self.assertEqual(len(new),45)
        self.assertEqual(set(old)-set(new),{'gt01-c01','gt01-c03','gt05-c01'})
        for ident,c in new.items():
            self.assertEqual(c['source'],old[ident]['source'])
            if ident not in ('gt01-c02','gt04-c01'):self.assertEqual(c['text'],old[ident]['text'])
        self.assertEqual(new['gt01-c02']['text'], '생일 특별휴가는 입사 후 3개월이 지난 재직자를 대상으로 매년 1일 신청할 수 있으며, 수습 중인 직원은 대상에서 제외됩니다.')
        self.assertEqual(new['gt04-c01']['text'], '재택근무일에는 사무실 출근일에 지급하는 식대를 지원하지 않습니다.')
        self.assertIn('1만 원',new['gt04-c02']['text'])
        self.assertIn('직무 관련 자격시험',new['gt05-c02']['text'])
        self.assertIn('연 1일',new['gt05-c02']['text'])
        self.assertEqual(self.packet['judgements'],self.old['judgements'])
        self.assertEqual(len(self.mapping['changes']),48)
        targets={r['old']['id']:r['new']['id'] for r in self.mapping['changes']}
        for old_id,new_id in {'gt01-c01':'gt01-c02','gt01-c02':'gt01-c02','gt01-c03':'gt01-c02','gt05-c01':'gt05-c02','gt05-c02':'gt05-c02'}.items():
            self.assertEqual(targets[old_id],new_id)

    def test_exact_evidence_answer_offsets_pages_and_absence(self):
        canonical=(PARENT/'source/extracted/canonical/hr-v4-handbook.txt').read_text()
        for q in self.packet['questions']:
            self.assertIsNone(q['human_approval'])
            for c in q['codex_source_checked']['claims']:
                s=c['source'];a,b=c['answer_span']
                self.assertEqual(canonical[s['start']:s['end']],s['quote'])
                self.assertEqual(hashlib.sha256(s['quote'].encode()).hexdigest(),s['quote_sha256'])
                self.assertEqual(q['codex_source_checked']['answer'][a:b],c['text'])
        self.assertIsNone(self.packet['human_approval'])
        self.assertEqual(len(self.packet['questions']),10)
        for q,old in zip(self.packet['questions'][-2:],self.old['questions'][-2:]):
            self.assertEqual(q['codex_source_checked'],old['codex_source_checked'])
            self.assertEqual(q['source_spans'],[])
            self.assertEqual(q['model_original_attempts'],[])
        self.assertTrue(all(j['human_approval'] is None for j in self.packet['judgements']))

    def test_source_mapping_mutations_are_rejected(self):
        for field,value in [('start',0),('pages',[999]),('quote_sha256','bad'),('canonical_sha256','bad')]:
            packet=copy.deepcopy(self.packet)
            packet['questions'][0]['codex_source_checked']['claims'][0]['source'][field]=value
            with self.assertRaises(ValueError):revision.validate_claims(packet,PARENT)

    def test_default_disclosures_visible_quotes_links_and_json(self):
        text=revision.render(self.packet,self.mapping); dom=Structure();dom.feed(text)
        self.assertEqual(dom.quotes,45+18)
        self.assertEqual(dom.details,69)
        self.assertEqual(dom.scripts,[{'type':'application/json','id':'packet'}])
        self.assertLess(text.index('질문 바로가기'),text.index('id="gt01"'))
        self.assertLess(text.index('id="gt10"'),text.index('id="judgements"'))
        self.assertLess(text.index('id="judgements"'),text.index('id="experiment"'))
        for q in self.packet['questions']:
            if q['codex_source_checked']['claims']:
                self.assertEqual(text.count(q['codex_source_checked']['answer']),0)
        for link in dom.links:
            if link.startswith('#'):self.assertIn(link[1:],dom.ids)
            elif link.startswith('../run001/'):self.assertTrue((ROOT/'artifacts/run002'/link).is_file())
            else:self.assertIn(link,{'packet.json','packet-manifest.json','revision-mapping.json'})
        self.assertNotIn(' src=',text)
        self.assertIn('width=device-width',text)
        self.assertIn('summary:focus-visible',text)

    def test_html_and_embedded_json_escape_untrusted_source(self):
        packet=copy.deepcopy(self.packet)
        attack='</script><script>alert("x")</script><img src=x onerror=bad>&'
        packet['questions'][0]['codex_source_checked']['claims'][0]['source']['quote']=attack
        text=revision.render(packet,self.mapping)
        self.assertNotIn(attack,text)
        self.assertIn('&lt;img src=x onerror=bad&gt;&amp;',text)
        embedded=text.split('<script type="application/json" id="packet">')[1].split('</script>')[0]
        self.assertEqual(json.loads(embedded),packet)

    def test_offline_replay_immutability_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp)/'run001';out=Path(tmp)/'run002'
            shutil.copytree(PARENT,parent)
            before=revision.inventory(parent)
            with patch('socket.socket',side_effect=AssertionError('offline revision attempted network')):
                revision.create(parent,out)
                revision.verify(out)
                html_before=file_hash(out/'review.html')
                revision.create(parent,out)
                self.assertEqual(file_hash(out/'review.html'),html_before)
                self.assertEqual(revision.inventory(parent),before)
                self.assertEqual(report.verify_packet(parent),self.old)
            self.assertEqual(read(out/'packet.json'),self.packet)
            # Runtime lock is preserved locally but absent from a fresh Git copy.
            (parent/'.runner.lock').unlink(missing_ok=True)
            self.assertEqual(revision.verify(out),self.packet)
            (out/'review.html').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'HTML'):revision.create(parent,out)
            self.assertEqual((out/'review.html').read_text(),'tampered')
            with self.assertRaises(ValueError):revision.create(parent,parent)

    def test_cli_replay_and_model_run_rejected_on_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            shutil.copytree(PARENT,base/'run001')
            revision.create(base/'run001',base/'run002')
            for command in ['verify','report']:
                result=subprocess.run([sys.executable,'-B',str(ROOT/'prepare.py'),command,'--out',str(base/'run002')],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([sys.executable,'-B',str(ROOT/'prepare.py'),'run','--out',str(base/'run002')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('offline only',result.stderr)
            self.assertFalse((base/'run002/ledger.json').exists())


if __name__=='__main__':unittest.main()
