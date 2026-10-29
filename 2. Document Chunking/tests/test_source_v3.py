"""Independent adversarial checks for immutable source preservation and ingestion."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import document_common as common
import ingest_documents as ingest
import snapshot_drive_fixture as drive
from prepare_handoff import locate,load_documents
from validate_source import validate,check_span
from test_documents import pdf_fixture

ROOT=common.STAGE/'data/source-v3'


class SourceV3Tests(unittest.TestCase):
    def test_frozen_six_docs_full_authoring_roundtrip_and_independent_policy_examples(self):
        r=validate(ROOT)
        self.assertEqual((r['documents'],r['pages'],r['policy_sentences'],r['sections']),(6,6,31,19))
        _,docs=load_documents(ROOT)
        text=''.join(docs['hr-v3-annual'][1].split())
        for s in ['1년미만재직자는한달개근시연차1일','1년이상재직자의연차는매년15일','반차1회는연차0.5일','최대5일분을다음해로이월','다음해3월31일','긴급사유가있으면당일팀장에게알린후']:
            self.assertIn(s,text)
        birthday=''.join(docs['hr-v3-birthday'][1].split())
        for s in ['입사후3개월','매년생일특별휴가1일','수습중인직원은대상에서제외','사용3영업일전까지','팀장의승인을받아야','분할할수없다']:
            self.assertIn(s,birthday)

    def test_handoff_rejects_pdf_canonical_map_and_document_removal(self):
        for rel in ['output/pdf/annual.pdf','extracted/canonical/hr-v3-annual.txt','section-map.json','policy-map.json']:
            with self.subTest(rel=rel),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'copy';shutil.copytree(ROOT,root)
                with (root/rel).open('ab') as f:f.write(b'changed')
                with self.assertRaises(common.DocumentError):validate(root)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'copy';shutil.copytree(ROOT,root)
            (root/'output/pdf/birthday.pdf').unlink()
            with self.assertRaises(common.DocumentError):validate(root)

    def test_missing_or_reordered_pages_rejected_even_with_updated_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'copy';shutil.copytree(ROOT,root)
            p=root/'extracted/manifest.json';m=common.read_json(p)
            m['documents'][0]['pages']=[];common.write_json(p,m)
            with self.assertRaises(common.DocumentError):load_documents(root)

    def test_exact_span_and_page_hash_rejection(self):
        _,docs=load_documents(ROOT)
        s=common.read_json(ROOT/'policy-map.json')['policies'][0]['targets'][0]
        for field,val in [('start',s['start']+1),('quote','잘못된 인용'),('canonical_sha256','0'*64),('pages',[])]:
            v=copy.deepcopy(s);v[field]=val
            with self.subTest(field=field),self.assertRaises(common.DocumentError):check_span(v,docs)
        check_span(s,docs)

    def test_unique_unicode_span_mapping_not_pdf_bytes(self):
        self.assertEqual(locate('한글 기한은 3월\n31일이다.','3월 31일이다.'),(7,16))
        for text,quote in [('abc abc','abc'),('abc','absent'),('abc',' ')]:
            with self.assertRaises(common.DocumentError):locate(text,quote)

    def test_strict_json_duplicate_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json'
            for raw in ['{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}']:
                p.write_text(raw)
                with self.assertRaises(ValueError):common.read_json(p)

    def test_snapshot_hash_failure_atomic_output_and_existing_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'copy';shutil.copytree(ROOT,root)
            saved=(root/'snapshot/manifest.json').read_bytes()
            with self.assertRaises(common.DocumentError):drive.snapshot(root/'drive-fixture-catalog.json',root/'snapshot')
            self.assertEqual((root/'snapshot/manifest.json').read_bytes(),saved)
            (root/'output/pdf/annual.pdf').write_bytes(b'tampered')
            with self.assertRaises(common.DocumentError):drive.snapshot(root/'drive-fixture-catalog.json',root/'bad')
            self.assertFalse((root/'bad').exists())
            self.assertFalse(list(root.glob('.document-stage-*')))

    def test_pdf_timeout_and_worker_missing_page_result(self):
        with patch.object(ingest.subprocess,'run',side_effect=subprocess.TimeoutExpired('worker',.01)):
            with self.assertRaises(common.DocumentError) as e:ingest.pdf_pages(Path('unused.pdf'),.01)
            self.assertEqual(e.exception.kind,'pdf_timeout')
        result=subprocess.CompletedProcess([],0,json.dumps({'status':'ok','pages':[{'page_number':2}]}),'')
        with patch.object(ingest.subprocess,'run',return_value=result):
            with self.assertRaises(common.DocumentError) as e:ingest.pdf_pages(Path('unused.pdf'),1)
            self.assertEqual(e.exception.kind,'missing_page')

    def test_original_page_separator_nfc_lf_and_multi_page_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pdf=root/'test.pdf';pdf_fixture(pdf,('text','text'))
            row={'document_id':'two-pages','version':'test','title':'fixture','format':'pdf','path':'test.pdf','sha256':common.file_hash(pdf),'synthetic':True,'authored_by':'test','file_id':'fixture:test','name':'test.pdf','source_modified_time':'2026-10-29T00:00:00Z','source_version':None,'source_url':None}
            common.write_json(root/'catalog.json',{'source_provider':'google_drive','source_mode':'fixture','folder_id':'fixture:folder','timestamps_synthetic':True,'documents':[row]})
            drive.snapshot(root/'catalog.json',root/'snapshot')
            out=ingest.ingest(root/'snapshot/manifest.json',root/'extracted');d=out['documents'][0]
            self.assertEqual(len(d['pages']),2)
            self.assertEqual(d['pages'][1]['start'],d['pages'][0]['end']+2)
            text=(root/'extracted'/d['canonical_path']).read_text()
            self.assertEqual(text.count('Independent PDF text 123'),2)
        self.assertEqual(common.normalize('e\u0301\r\n한글\r끝'),'é\n한글\n끝')

    def test_notes_policy_references_are_excluded_from_pdf_catalog(self):
        rows=common.read_json(ROOT/'drive-fixture-catalog.json')['documents']
        self.assertEqual(len(rows),6)
        self.assertTrue(all(r['format']=='pdf' and r['source_url'] is None for r in rows))
        self.assertFalse(any('notes' in r['path'] or 'policy' in r['path'] or 'authoring' in r['path'] for r in rows))
        inv=common.read_json(ROOT/'policy-inventory.json');ids={c['claim_id'] for c in inv['claims']}
        self.assertEqual(len(inv['source_v2_block_audit']),51)
        for b in inv['source_v2_block_audit']:
            self.assertTrue(set(b['policy_refs'])<=ids)
            if b['classification']!='policy':self.assertIn(b['quote'],(ROOT/'authoring-notes.md').read_text())


if __name__=='__main__':unittest.main()
