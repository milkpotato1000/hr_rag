import unittest
from rag_package.chunks import make_chunks
from rag_package.chunk_policy import config
from rag_package.storage import RagError

class HandbookHierarchyTests(unittest.TestCase):
    def test_long_sections_and_reset(self):
        chapter='제1장 휴가 [BD]'
        section='제1절 기준 [BD-S1]'
        article='BD-03 신청 기한과 승인'
        section2='제2절 예외 [BD-S2]'
        second='제2장 출장 [TR]'
        first='통합 목차\n제1장 휴가\n'+chapter+'\n'+chapter+'\n'+section+'\n'+article+'\n'
        first+='가'*20000+'\nBD-03에 따라 확인한다.\n본문은 BD-04를 참조한다.\n'
        first+=section2+'\n'+'승'*50000+'\n'+second+'\nBD-04 다른 장의 참조\n'
        def doc(name,text):
            return dict(document_id=name,text=text,pages=[{'page':1,'start':0,'end':len(text)}])
        docs=[doc('long',first),doc('plain','BD-03 참조\n자료입니다.')]
        cfg=dict(method='structure',size_chars=400,overlap_chars=80,heading_profile='handbook-v1')
        chunks,coverage=make_chunks(docs,'source',cfg)
        self.assertEqual(coverage['detection'][0]['headings_detected'],5)
        self.assertEqual(coverage['detection'][1]['fallback'],'recursive_no_heading_detected')
        expected=[(0,[]),(first.rindex(chapter),[chapter]),(first.index(section),[chapter,section]),
                  (first.index(article),[chapter,section,article]),(first.index(section2),[chapter,section2]),
                  (first.index(second),[second])]
        for c in chunks:
            if c['document_id']=='plain':
                self.assertEqual(c['heading_path'],[])
                continue
            path=next(path for offset,path in reversed(expected) if offset<=c['start'])
            self.assertEqual(c['heading_path'],path)
            self.assertFalse(any(c['start']<offset<c['end'] for offset,_ in expected))
            self.assertEqual(c['text'],first[c['start']:c['end']])
            self.assertLessEqual(len(c['text']),400)
        rows=[r for r in coverage['coverage'] if r['document_id']=='long']
        end=0
        for r in rows:
            self.assertEqual(r['base_start'],end)
            self.assertLessEqual(end-r['start'],80)
            end=r['base_end']
        self.assertEqual(end,len(first))
    def test_opt_in_and_ids(self):
        text='본문입니다.'
        docs=[dict(text=text,document_id='doc',pages=[dict(page=1,start=0,end=len(text))])]
        cfg=dict(method='structure',size_chars=400,overlap_chars=80)
        plain,_=make_chunks(docs,'source',cfg)
        tagged,_=make_chunks(docs,'source',dict(cfg,heading_profile='handbook-v1'))
        self.assertEqual(plain[0]['text'],tagged[0]['text'])
        self.assertNotEqual(plain[0]['chunk_id'],tagged[0]['chunk_id'])
        for method,profile in [('fixed','handbook-v1'),('structure','unknown')]:
            with self.assertRaises(RagError):
                config(dict(cfg,schema_version=1,method=method,heading_profile=profile))
