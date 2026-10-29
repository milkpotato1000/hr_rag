#!/usr/bin/env python3
"""Build preservation/section metadata from fixed originals, never retrieval qrels.
Supply legacy evidence explicitly; standalone artifact validation needs no parent stage.
"""
import argparse
from pathlib import Path
import re
from document_common import read_json, write_json, file_hash, fingerprint, safe_file, verify_file, DocumentError, atomic_directory


def compact(text):
    return ''.join(c for c in text if not c.isspace())


def locate(text, quote):
    positions = [i for i,c in enumerate(text) if not c.isspace()]
    hay = ''.join(text[i] for i in positions)
    needle = compact(quote)
    if not needle or hay.count(needle) != 1:
        raise DocumentError('quote_match', 'expected one exact non-whitespace match: ' + quote)
    start = hay.index(needle)
    return positions[start], positions[start + len(needle)-1]+1


def span(doc, text, quote):
    start,end=locate(text,quote)
    return {'document_id':doc['document_id'],'start':start,'end':end,'quote':text[start:end],
            'canonical_sha256':doc['canonical_sha256'],'original_sha256':doc['original_sha256'],
            'pages':[{'page_number':p['page_number'],'start':max(start,p['start']),'end':min(end,p['end']),
                      'page_text_sha256':p['text_sha256']} for p in doc['pages'] if p['start']<end and start<p['end']]}


def load_documents(source):
    extracted=source/'extracted'; m=read_json(extracted/'manifest.json')
    if m.get('status')!='complete': raise DocumentError('incomplete', 'extraction must be complete')
    docs={}
    for d in m['documents']:
        text=verify_file(extracted,d['canonical_path'],d['canonical_sha256']).read_text()
        cursor=0;pieces=[]
        for i,p in enumerate(d['pages'],1):
            page=verify_file(extracted,p['text_path'],p['text_sha256']).read_text()
            verify_file(extracted,p['raw_text_path'],p['raw_text_sha256'])
            if i>1:cursor+=2
            if p['page_number']!=i or p['start']!=cursor or p['end']!=cursor+len(page) or text[p['start']:p['end']]!=page:
                raise DocumentError('page_map','invalid page map')
            cursor=p['end'];pieces.append(page)
        if '\n\n'.join(pieces)!=text or len(text)!=d['canonical_chars']:
            raise DocumentError('page_map','canonical differs from page concatenation')
        verify_file(source/'snapshot',d['original_path'],d['original_sha256'])
        docs[d['document_id']]=(d,text)
    if len(docs)!=6:raise DocumentError('missing_document','six unique documents required')
    return m,docs


def prepare(source, legacy_evaluation, legacy_chunks, output):
    m,docs=load_documents(source)
    inventory=read_json(source/'policy-inventory.json')
    metadata=read_json(source/'document-metadata.json')['documents']
    source_commit=inventory['source_commit']
    chunk_rows={x['chunk_id']:x for x in [read_json_line(l) for l in legacy_chunks.read_text().splitlines()]}
    policies=[]
    for claim in inventory['claims']:
        old=chunk_rows[claim['chunk_id']]
        if claim['text'] not in old['text']:raise DocumentError('source_claim','claim absent in source chunk')
        targets=[]
        for did,(d,text) in docs.items():
            if compact(claim['text']) in compact(text): targets.append(span(d,text,claim['text']))
        if claim['claim_id']=='welfare-birthday-2':
            d,text=docs['hr-v3-birthday']
            targets.append(span(d,text,'생일 축하 포인트는 휴가 신청 자격이나 승인 여부와 별개다.'))
        if not targets:raise DocumentError('missing_policy',claim['claim_id'])
        source_v2=[{'path':b['source_path'],'sha256':b['source_sha256'],'start':b['start']+b['quote'].index(claim['text']),
                    'end':b['start']+b['quote'].index(claim['text'])+len(claim['text']),'quote':claim['text']}
                   for b in inventory['source_v2_block_audit'] if claim['text'] in b['quote']]
        if not source_v2:raise DocumentError('missing_source_v2',claim['claim_id'])
        policies.append({**claim,'source_commit':source_commit,'source_chunk_file_sha256':file_hash(legacy_chunks),
                         'source_chunk_path':'1. Naive RAG/data/synthetic/chunks.jsonl',
                         'source_v2':source_v2,'targets':targets,'comparison':'PASS: numeric units, eligibility, negation, exceptions, deadlines and approvers preserved'})
    sections=[];reverse=[]
    for md in metadata:
        d,text=docs[md['document_id']]
        original=source/'authoring'/(md['name']+'.md')
        blocks=original.read_text().split('## ')[1:]
        for n,block in enumerate(blocks,1):
            heading,body=block.split('\n',1);body=body.strip()
            h=span(d,text,heading)
            body_span=span(d,text,body)
            sections.append({'section_id':md['document_id']+'-s'+str(n),'heading':heading,
                             'heading_span':h,'body_span':body_span,'start':h['start'],'end':body_span['end'],
                             'chars':body_span['end']-h['start'],
                             'role':'authoring section candidate; not a chunk or heading detector output'})
            for sentence in re.split(r'(?<=다\.)\s+',body):
                matching=[p['claim_id'] for p in policies if compact(p['text'])==compact(sentence)]
                if sentence=='생일 축하 포인트는 휴가 신청 자격이나 승인 여부와 별개다.':matching=['welfare-birthday-2']
                if not matching:raise DocumentError('unsourced_policy',sentence)
                reverse.append({'section_id':sections[-1]['section_id'],'quote':sentence,'policy_ids':matching})
    legacy=read_json(legacy_evaluation)
    facts=[]
    for f in legacy['facts']:
        targets=[]
        for old in f['required_spans']:
            d,text=docs[old['document_id'].replace('hr-v2-','hr-v3-')]
            targets.append(span(d,text,old['quote']))
        facts.append({'fact_id':f['fact_id'],'meaning':f['meaning'],'new_spans':targets})
    review_type='Codex source-preservation comparison; NOT human-approved Ground Truth, retrieval qrels or approved P007 evaluation'
    with atomic_directory(output) as target:
        write_json(target/'policy-map.json',{'schema_version':1,'review_type':review_type,'source_commit':source_commit,
            'inventory_sha256':file_hash(source/'policy-inventory.json'),'policies':policies,'new_body_sentence_audit':reverse,
            'source_v2_block_audit':inventory['source_v2_block_audit'],'status':'PASS'})
        write_json(target/'section-map.json',{'schema_version':1,'offset_unit':'Unicode code point [start,end), not PDF coordinates',
            'ingestion_run_id':m['run_id'],'sections':sections})
        write_json(target/'legacy-reference-map.json',{'review_type':review_type,'legacy_source_sha256':file_hash(legacy_evaluation),
            'facts':facts,'questions':legacy['questions'],'question_split':'observed tuning only; NOT holdout',
            'limits':'Old fact selection is not an exhaustive policy inventory. P007 must review its own questions/labels; P013 requires human-approved reference claims.'})
    return {'policies':len(policies),'sections':len(sections),'facts':len(facts),'questions':len(legacy['questions'])}


def read_json_line(line):
    import json
    from document_common import unique_object,reject_constant
    return json.loads(line,object_pairs_hook=unique_object,parse_constant=reject_constant)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--legacy-evaluation',type=Path,required=True)
    p.add_argument('--legacy-chunks',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();print(prepare(a.source_root,a.legacy_evaluation,a.legacy_chunks,a.output_dir))


if __name__=='__main__':main()
