"""V4 single-book, boundary, preservation and tampering regressions."""
import copy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from document_common import STAGE,DocumentError,read_json,write_json,fingerprint
from handbook_model import parse,check_structure
from handbook_artifacts import single,load_document,align,derive,span,check_span
from validate_handbook import validate
from prepare_handbook import create

ROOT=STAGE/'data/source-v4'

# This small authored fixture is independent of the production handbook.
MINI='''# Fixture

## 통합 목차

제1장 같은 제목

## 제1장 같은 제목 [BD]

### 제1절 첫 절 [BD-S1]

#### BD-01 첫 조항

<!-- kind: added_fictional -->
앞 문장을 확인한다. BD-02@v4를 참조한다.

#### BD-02 둘째 조항

<!-- kind: explanatory -->
두 번째 문장이다.
'''

class HandbookTests(unittest.TestCase):
    def test_full_single_book_and_independent_original_policy_examples(self):
        r=validate(ROOT,frozen=(ROOT/'handoff-manifest.json').exists())
        self.assertEqual((r['documents'],r['pages'],r['articles'],r['paragraphs']),(1,23,57,105))
        self.assertEqual(r['body_chars'],35477)
        self.assertEqual(r['classifications'],{'preserved':31,'added_fictional':481,'explanatory':14})
        src=(ROOT/'authoring/hr-handbook.md').read_text()
        for text in ['출장은 출발 5영업일 전에 팀장의 승인을 받는다.','이월한 연차의 사용 기한은 다음 해 3월 31일이다.','수습 중인 직원은 대상에서 제외한다.']:
            self.assertIn(text,src)
        self.assertGreaterEqual(r['page_crossing_paragraphs'],3)

    def test_independent_toc_and_body_heading_are_separate(self):
        m=parse(MINI)
        self.assertEqual(len(m['nodes']),5)
        chapter=next(n for n in m['nodes'] if n['id']=='BD')
        self.assertGreater(chapter['heading_start'],MINI.index('제1장 같은 제목')+len('제1장 같은 제목'))
        self.assertEqual(m['references'][0]['target'],'BD-02')
        spans=m['length_accounting'];allsp=sorted(spans['included']+spans['excluded'],key=lambda x:x['start'])
        self.assertEqual(allsp[0]['start'],0);self.assertEqual(allsp[-1]['end'],len(MINI))
        self.assertTrue(all(a['end']==b['start'] for a,b in zip(allsp,allsp[1:])))
        self.assertEqual(spans['body_chars'],len('앞 문장을 확인한다. BD-02@v4를 참조한다.')+len('두 번째 문장이다.'))

    def test_independent_invalid_hierarchy_classification_ids_and_refs(self):
        variants=[MINI.replace('### 제1절 첫 절 [BD-S1]\n',''),MINI.replace('BD-02 둘째','BD-01 둘째'),
          MINI.replace('<!-- kind: added_fictional -->\n',''),MINI.replace('BD-02@v4','BD-99@v4'),
          MINI.replace('BD-02@v4','BD-01@v4'),MINI.replace('BD-02@v4','BD-02@v3'),
          MINI.replace('두 번째 문장이다.','BD-01@v4를 따른다.')]
        for v in variants:
            with self.subTest(v=v[-80:]),self.assertRaises(DocumentError):parse(v)

    def test_independent_unicode_halfopen_span_and_page_crossing(self):
        text='한글 앞\n\n뒤 문장';doc={'canonical_sha256':'fixture','pages':[{'page_number':1,'start':0,'end':4},{'page_number':2,'start':6,'end':10}]}
        good=span(text,doc,3,7);self.assertEqual(good['quote'],'앞\n\n뒤');self.assertEqual(good['pages'],[1,2]);check_span(good,text,doc)
        for start,end in [(-1,2),(2,2),(0,100),(True,2)]:
            with self.assertRaises(DocumentError):span(text,doc,start,end)
        for key,value in [('start',2),('pages',[1]),('canonical_sha256','wrong'),('quote','다른 문장')]:
            changed={**good,key:value}
            with self.assertRaises(DocumentError):check_span(changed,text,doc)

    def test_independent_length_profile_rejection(self):
        # A stand-alone six-chapter shape with explicit lengths: no production text.
        ids=['BD','AN','RM','WF','ED','TR'];src='# Test\n\n';spec=read_json(ROOT/'corpus-spec.json')
        for cid in ids:
            src+=f'## 제1장 제목 [{cid}]\n\n'
            for sec in [1,2]:
                src+=f'### 제{sec}절 제목 [{cid}-S{sec}]\n\n'
                for a,length in zip(range((sec-1)*3+1,sec*3+1),[100,100,1300] if sec==1 else [500,500,800]):
                    src+=f'#### {cid}-{a:02} 제목\n\n<!-- kind: added_fictional -->\n'+('가'*length)+'\n\n'
        m=parse(src)
        # References are not under test here; add two independently declared edges per chapter.
        m['references']=[{'source':c+'-03','target':c+'-01'} for c in ids for _ in range(2)]
        m['references'] += [{'source':'TR-06','target':'BD-01'}]*3
        spec['total_body_chars']=[19800,19800]
        for c in spec['topic_chapters']:c.update(min_body_chars=3300,max_body_chars=3300)
        self.assertEqual(check_structure(m,spec)['body_chars'],19800)
        for delta in [-1,1]:
            bad=copy.deepcopy(m);next(n for n in bad['nodes'] if n['id']=='BD-01')['body_chars']+=delta
            with self.assertRaises(DocumentError):check_structure(bad,spec)

    def test_single_input_rejects_duplicates_and_wrong_document(self):
        for rows in [[],[{'document_id':'wrong'}],[{'document_id':'hr-v4-handbook'}]*2]:
            with self.assertRaises(DocumentError):single(rows)

    def test_whole_text_alignment_rejects_silent_omission_and_reordering(self):
        m=parse((ROOT/'authoring/hr-handbook.md').read_text());doc,text=load_document(ROOT)
        for bad in [text.replace('3개월','4개월',1),text.replace('수습 중인 직원은','',1),text.replace('BD-01','BD-99',1)]:
            self.assertNotEqual(bad,text)
            with self.assertRaises(DocumentError):align(m,bad,doc)

    def test_policy_review_missing_and_unclassified_rejected(self):
        for kind in ('unclassified','missing_review','missing_policy'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                r=Path(tmp)/'corpus';shutil.copytree(ROOT,r)
                if kind=='unclassified':
                    p=r/'authoring/hr-handbook.md';p.write_text(p.read_text().replace('<!-- kind: preserved -->\n','',1))
                elif kind=='missing_review':
                    p=r/'authoring-review.json';d=read_json(p);del d['articles']['BD-01'];write_json(p,d)
                else:
                    p=r/'baseline-policy.json';d=read_json(p);d['policies'].append({'claim_id':'missing','text':'새로운 미보존 규칙.'});write_json(p,d)
                with self.assertRaises(DocumentError):derive(r)

    def test_page_missing_or_bad_offsets_even_after_identity_recalculation(self):
        for change in ('remove','offset'):
            with tempfile.TemporaryDirectory() as tmp:
                r=Path(tmp)/'corpus';shutil.copytree(ROOT,r);p=r/'extracted/manifest.json';d=read_json(p)
                if change=='remove':d['documents'][0]['pages'].pop(1)
                else:d['documents'][0]['pages'][1]['start']+=1
                basis={k:d[k] for k in ('schema_version','snapshot_manifest_sha256','normalization_version','page_separator','ingestion_lock_sha256','documents')};d['run_id']=fingerprint(basis);write_json(p,d)
                with self.assertRaises(DocumentError):load_document(r)

    def test_maps_reject_tampering_without_relying_on_frozen_hashes(self):
        for name in ['section-map.json','policy-inventory.json','policy-map.json','corpus-profile.json']:
            with tempfile.TemporaryDirectory() as tmp:
                r=Path(tmp)/'corpus';shutil.copytree(ROOT,r);write_json(r/name,{'tampered':True})
                with self.assertRaises(DocumentError):validate(r,frozen=False)

    def test_pdf_and_canonical_hash_tampering(self):
        for name in ['output/pdf/hr-handbook.pdf','extracted/canonical/hr-v4-handbook.txt']:
            with tempfile.TemporaryDirectory() as tmp:
                r=Path(tmp)/'corpus';shutil.copytree(ROOT,r)
                with (r/name).open('ab') as f:f.write(b'changed')
                with self.assertRaises(DocumentError):load_document(r)

    def test_no_overwrite_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);out=r/'maps';create(ROOT,out);before=(out/'section-map.json').read_bytes()
            with self.assertRaises(DocumentError):create(ROOT,out)
            self.assertEqual(before,(out/'section-map.json').read_bytes())
            with patch('prepare_handbook.write_json',side_effect=OSError('independent injected disk failure')):
                with self.assertRaises(OSError):create(ROOT,r/'failed')
            self.assertFalse((r/'failed').exists());self.assertFalse(list(r.glob('.document-stage-*')))

if __name__=='__main__':unittest.main()
