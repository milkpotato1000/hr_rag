#!/usr/bin/env python3
"""Validate a frozen P015 handoff offline without parent-stage imports."""
import argparse
from pathlib import Path
import re
from document_common import read_json,verify_file,file_hash,fingerprint,DocumentError,cli_error
from prepare_handoff import load_documents,compact


def check_span(s, docs):
    if s['document_id'] not in docs:raise DocumentError('span','unknown document')
    d,text=docs[s['document_id']]
    a,b=s['start'],s['end']
    if type(a)!=int or type(b)!=int or not 0<=a<b<=len(text) or text[a:b]!=s['quote'] or s['canonical_sha256']!=d['canonical_sha256'] or s['original_sha256']!=d['original_sha256']:
        raise DocumentError('span','offset/quote/hash mismatch')
    expected=[{'page_number':p['page_number'],'start':max(a,p['start']),'end':min(b,p['end']),'page_text_sha256':p['text_sha256']} for p in d['pages'] if p['start']<b and a<p['end']]
    if expected!=s['pages']:raise DocumentError('span','page intersection mismatch')


def validate(source):
    handoff=read_json(source/'handoff-manifest.json')
    if handoff['manifest_id']!=fingerprint({k:v for k,v in handoff.items() if k!='manifest_id'}):
        raise DocumentError('handoff','handoff identity mismatch')
    for f in handoff['files']:verify_file(source,f['path'],f['sha256'])
    m,docs=load_documents(source)
    metadata=read_json(source/'document-metadata.json')['documents']
    catalog=read_json(source/'drive-fixture-catalog.json')
    if len(catalog['documents'])!=6 or {d['document_id'] for d in catalog['documents']}!=set(docs) or any(d['format']!='pdf' for d in catalog['documents']):
        raise DocumentError('catalog','exact six PDF-only inputs required')
    for row in catalog['documents']:verify_file(source,row['path'],row['sha256'])
    for md in metadata:
        d,text=docs[md['document_id']]
        authored=(source/'authoring'/(md['name']+'.md')).read_text()
        # Whole document check catches silent dropped words, new content and reading-order changes.
        body='\n'.join(line.lstrip('# ') if line.startswith('#') else line for line in authored.splitlines())
        footer=md['document_id'].upper()+' / v3\n1'
        if len(d['pages'])!=1 or compact(body+footer)!=compact(text):
            raise DocumentError('authoring_roundtrip','source-v3 PDF text differs from authored text/footer')
        if text.count('가상 HR 규정')!=1 or md['effective_date'] is not None:
            raise DocumentError('metadata','warning or unknown effective date differs')
        if any(t in text for t in ['답변을 작성할 때는','원문 읽기 연습','페이지를 넘는 읽기','청킹','검색 문맥']):
            raise DocumentError('editorial_leak','learning commentary entered corpus')
    policies=read_json(source/'policy-map.json')
    if 'NOT human-approved' not in policies['review_type']:raise DocumentError('review_type','must distinguish preservation from GT')
    for p in policies['policies']:
        if not p['source_v2'] or not p['targets']:raise DocumentError('policy','missing provenance or target')
        for s in p['targets']:check_span(s,docs)
    for s in read_json(source/'section-map.json')['sections']:
        check_span(s['heading_span'],docs);check_span(s['body_span'],docs)
    legacy=read_json(source/'legacy-reference-map.json')
    for f in legacy['facts']:
        for s in f['new_spans']:check_span(s,docs)
    return {'status':'PASS','documents':len(docs),'pages':sum(len(d['pages']) for d,t in docs.values()),
            'policy_sentences':len(policies['policies']),'source_v2_blocks':len(policies['source_v2_block_audit']),
            'sections':len(read_json(source/'section-map.json')['sections']),
            'legacy_facts':len(legacy['facts']),'tuning_questions':len(legacy['questions']),
            'canonical_chars':{did:len(text) for did,(d,text) in docs.items()},'manifest_id':handoff['manifest_id']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);a=p.parse_args()
    try:
        import json
        print(json.dumps(validate(a.source_root),ensure_ascii=False,indent=2))
    except (OSError,ValueError,KeyError,TypeError) as exc:return cli_error(exc)
    return 0


if __name__=='__main__':raise SystemExit(main())
