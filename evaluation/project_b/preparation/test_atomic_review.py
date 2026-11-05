"""P022 atomicity, source preservation, schema boundaries and offline replay tests."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import atomic_review as atomic
from core import digest, file_hash, read, write
from test_review_revision import Structure

ROOT=Path(__file__).resolve().parent
PARENT=ROOT/'artifacts/run002'
AUDIT=ROOT/'artifacts/run003/atomicity-audit.json'


class AtomicReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet,cls.mapping=atomic.build(PARENT,AUDIT)
        cls.old=read(PARENT/'packet.json')
        cls.audit=read(AUDIT)

    def test_all_45_parents_map_to_exact_57_proposals_in_order(self):
        claims=[c for q in self.packet['questions'] for c in q['codex_source_checked']['claims']]
        self.assertEqual(len(claims),57)
        self.assertEqual(len({c['id'] for c in claims}),57)
        self.assertEqual([len(q['codex_source_checked']['claims']) for q in self.packet['questions']],[10,3,9,6,4,7,8,10,0,0])
        self.assertEqual(self.packet['schema_version'],2)
        self.assertEqual(self.packet['review_version'],'p022-atomic-v1')
        self.assertEqual(len(self.mapping['changes']),45)
        actions={'split':0,'restore_scope':0,'keep':0}
        for row,proposal in zip(self.mapping['changes'],self.audit['items']):
            actions[row['action']]+=1
            self.assertEqual(row['old']['id'],proposal['old_claim_id'])
            self.assertEqual([c['text'] for c in row['new']],[p['text'] for p in proposal['proposed_claims']])
            expected=[row['old']['id']+'-a'+str(i) for i in range(1,len(row['new'])+1)] if row['action']=='split' else [row['old']['id']]
            self.assertEqual([c['id'] for c in row['new']],expected)
            self.assertEqual(row['proposal_id_mapping'],[dict(proposal_id=p['proposal_id'],claim_id=c['id']) for p,c in zip(proposal['proposed_claims'],row['new'])])
            if row['action']=='keep':
                for key in ['id','text','source']:self.assertEqual(row['old'][key],row['new'][0][key])
        self.assertEqual(actions,{'split':10,'restore_scope':2,'keep':33})

    def test_independent_facts_retain_conditional_scope_and_exact_deadlines(self):
        claims={c['id']:c for q in self.packet['questions'] for c in q['codex_source_checked']['claims']}
        self.assertEqual(claims['gt01-c02-a1']['text'],'생일 특별휴가의 재직 기간 요건은 입사 후 3개월 경과입니다.')
        self.assertEqual(claims['gt01-c02-a2']['text'],'생일 특별휴가 대상자는 매년 1일을 신청할 수 있습니다.')
        self.assertEqual(claims['gt01-c02-a3']['text'],'수습 중인 직원은 생일 특별휴가 대상에서 제외됩니다.')
        self.assertIn('지급 대상자',claims['gt04-c03-a2']['text'])
        self.assertIn('교육휴가 대상자',claims['gt05-c02-a2']['text'])
        self.assertEqual(claims['gt06-c01-a2']['text'],'출장 승인은 출발 5영업일 전에 받아야 합니다.')
        self.assertNotIn('전까지',claims['gt06-c01-a2']['text'])
        for n in [1,2,3]:
            self.assertIn('시스템 장애로 접수 확인되지 않으면 담당자는',claims[f'gt07-c01-a{n}']['text'])
            self.assertIn('확인할 수 없는 경우에는 담당자가', ''.join(claims[f'gt07-c01-a{n}']['source']['quote'].splitlines()))
        self.assertIn('연차 일부 날짜만 취소할 때',claims['gt08-c02']['text'])
        self.assertIn('여러 날짜의 요청 중 일부만 취소',claims['gt08-c02']['source']['quote'])
        self.assertIn('아직 확인되지 않았거나',claims['gt08-c03']['text'])
        self.assertIn('사용 여부가 아직 확인되지 않았거나',''.join(claims['gt08-c03']['source']['quote'].splitlines()))
        self.assertIn('다른 시험',claims['gt08-c07-a1']['text'])
        self.assertIn('별도로 관리되는 휴가 기록',claims['gt08-c07-a2']['text'])
        self.assertNotIn('gt01-c02',claims)

    def test_source_answer_spans_pages_and_unchanged_provenance(self):
        canonical=(ROOT/'artifacts/run001/source/extracted/canonical/hr-v4-handbook.txt').read_text()
        pages=read(ROOT/'artifacts/run001/source/extracted/manifest.json')['documents'][0]['pages']
        for q,old in zip(self.packet['questions'],self.old['questions']):
            for key in ['question','source_spans','model_original_attempts','revision','status','human_approval']:self.assertEqual(q[key],old[key])
            for c in q['codex_source_checked']['claims']:
                s=c['source'];a,b=c['answer_span']
                self.assertEqual(c['text'],q['codex_source_checked']['answer'][a:b])
                self.assertEqual(s['quote'],canonical[s['start']:s['end']])
                self.assertEqual(s['quote_sha256'],hashlib.sha256(s['quote'].encode()).hexdigest())
                self.assertEqual(s['pages'],[p['page_number'] for p in pages if p['start']<s['end'] and p['end']>s['start']])
        self.assertEqual(self.packet['judgements'],self.old['judgements'])
        self.assertIsNone(self.packet['human_approval'])
        for q in self.packet['questions']+self.packet['judgements']:self.assertIsNone(q['human_approval'])
        for q,old in zip(self.packet['questions'][-2:],self.old['questions'][-2:]):self.assertEqual(q['codex_source_checked'],old['codex_source_checked'])
        self.assertEqual(self.packet['experiment'],self.old['experiment'])
        self.assertEqual(self.packet['codex_revision_history'],self.old['codex_revision_history'])
        self.assertEqual(self.packet['new_model_requests'],0)

    def test_html_visible_quotes_collapsed_logs_links_and_escaping(self):
        text=atomic.render(self.packet,self.mapping);dom=Structure();dom.feed(text)
        self.assertEqual(dom.quotes,57+18)
        self.assertEqual(dom.details,81)
        self.assertIn('검토본 003',text);self.assertIn('정답 주장 57개',text)
        self.assertIn('../run002/review.html',dom.links)
        self.assertIn('revision-mapping.json',dom.links)
        for q in self.packet['questions']:
            for c in q['codex_source_checked']['claims']:self.assertIn(c['id'],dom.ids)
        for link in dom.links:
            if link.startswith('#'):self.assertIn(link[1:],dom.ids)
            elif link.startswith('../'):
                self.assertTrue((ROOT/'artifacts/run003'/link.split('#')[0]).is_file(),link)
        embedded=text.split('<script type="application/json" id="packet">')[1].split('</script>')[0]
        self.assertEqual(json.loads(embedded),self.packet)
        packet=copy.deepcopy(self.packet);attack='</script><img src=x onerror=alert(1)>&'
        packet['questions'][0]['codex_source_checked']['claims'][0]['source']['quote']=attack
        escaped=atomic.render(packet,self.mapping)
        self.assertNotIn(attack,escaped);self.assertIn('&lt;img src=x onerror=alert(1)&gt;&amp;',escaped)

    def test_tampered_audit_or_parent_fails_without_output_or_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            shutil.copytree(ROOT/'artifacts/run001',root/'run001')
            shutil.copytree(PARENT,root/'run002')
            audit=root/'audit.json';audit.write_bytes(AUDIT.read_bytes()+b' ')
            before=atomic.inventory(root/'run002')
            with patch('socket.socket',side_effect=AssertionError('network')):
                with self.assertRaisesRegex(ValueError,'audit'):atomic.create(root/'run002',audit,root/'run003')
                self.assertFalse((root/'run003').exists())
                audit.write_bytes(AUDIT.read_bytes())
                p=root/'run002/packet.json';x=read(p);x['questions'][0]['question']='changed';write(p,x)
                with self.assertRaises(ValueError):atomic.create(root/'run002',audit,root/'run003')
                self.assertFalse((root/'run003').exists())
            self.assertEqual(atomic.inventory(root/'run002').keys(),before.keys())

    def test_offline_replay_preserves_parent_and_rejects_existing_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['run001','run002']:shutil.copytree(ROOT/'artifacts'/name,root/name)
            before={name:atomic.inventory(root/name) for name in ['run001','run002']}
            with patch('socket.socket',side_effect=AssertionError('network')):
                atomic.create(root/'run002',AUDIT,root/'run003')
                self.assertEqual(atomic.verify(root/'run003'),self.packet)
                atomic.create(root/'run002',root/'run003/atomicity-audit.json',root/'run003')
            for name in before:self.assertEqual(atomic.inventory(root/name),before[name])
            path=root/'run003/packet.json';packet=read(path)
            packet['human_approval']=True;packet['packet_sha256']=digest({k:v for k,v in packet.items() if k!='packet_sha256'});write(path,packet)
            changed=file_hash(path)
            with self.assertRaises(ValueError):atomic.create(root/'run002',AUDIT,root/'run003')
            self.assertEqual(file_hash(path),changed)

    def test_saved_html_and_manifest_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['run001','run002','run003']:shutil.copytree(ROOT/'artifacts'/name,root/name)
            for name in ['review.html','revision-mapping.json','packet-manifest.json']:
                path=root/'run003'/name;old=path.read_bytes();path.write_text('{}' if name.endswith('json') else 'changed')
                with self.assertRaises(ValueError):atomic.verify(root/'run003')
                path.write_bytes(old)
            self.assertEqual(atomic.verify(root/'run003'),self.packet)

    def test_cli_unknown_versions_schema_mismatch_and_model_commands_fail_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run003';out.mkdir()
            write(out/'packet.json',self.packet)
            for version,schema in [('unknown',2),('p022-atomic-v1',1),(None,2)]:
                p=copy.deepcopy(self.packet);p['review_version']=version;p['schema_version']=schema;write(out/'packet.json',p)
                run=subprocess.run([sys.executable,'-B',str(ROOT/'prepare.py'),'run','--out',str(out)],capture_output=True,text=True)
                self.assertNotEqual(run.returncode,0)
                self.assertRegex(run.stderr,'review_version|schema/version')
            write(out/'packet.json',self.packet)
            for command in ['run','revise-ground']:
                run=subprocess.run([sys.executable,'-B',str(ROOT/'prepare.py'),command,'--out',str(out)],capture_output=True,text=True)
                self.assertNotEqual(run.returncode,0)
                self.assertIn('offline only',run.stderr)
                self.assertFalse((out/'ledger.json').exists())


if __name__=='__main__':unittest.main()
