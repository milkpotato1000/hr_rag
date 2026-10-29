"""Derive verifiable maps from a single PDF and its complete authored text."""
from collections import Counter
from difflib import SequenceMatcher
import re
from document_common import (read_json, file_hash, verify_file, normalize, fingerprint,
                             validate_snapshot, DocumentError, SEPARATOR)
from handbook_model import DID, parse, check_structure, compact, require


def single(rows):
    require(isinstance(rows,list) and len(rows)==1 and rows[0].get('document_id')==DID,
            'document_count','one hr-v4-handbook input required')
    return rows[0]


def load_document(root):
    catalog=read_json(root/'drive-fixture-catalog.json');c=single(catalog['documents'])
    require(c['format']=='pdf' and c['path']=='output/pdf/hr-handbook.pdf','input_scope','only handbook PDF is collected')
    verify_file(root,c['path'],c['sha256'])
    snap=read_json(root/'snapshot/manifest.json');s=single(validate_snapshot(snap))
    verify_file(root/'snapshot',s['path'],s['sha256'])
    require(s['sha256']==c['sha256'],'hash_mismatch','catalog and snapshot differ')
    manifest=read_json(root/'extracted/manifest.json');doc=single(manifest['documents'])
    require(manifest['status']=='complete' and not manifest['review_pages'],'missing_page','not complete')
    require(manifest['snapshot_manifest_sha256']==file_hash(root/'snapshot/manifest.json'),'hash_mismatch','snapshot changed')
    basis={k:manifest[k] for k in ('schema_version','snapshot_manifest_sha256','normalization_version','page_separator','ingestion_lock_sha256','documents')}
    require(fingerprint(basis)==manifest['run_id'],'hash_mismatch','ingestion identity changed')
    require(doc['original_sha256']==c['sha256'] and doc['parser']=={'name':'pypdf','version':'6.21.2','mode':'plain'},'provenance','parser or source differs')
    text=verify_file(root/'extracted',doc['canonical_path'],doc['canonical_sha256']).read_text()
    require(text==normalize(text) and len(text)==doc['canonical_chars'],'normalization','canonical differs')
    pages=doc['pages'];require(2<=len(pages)<=48,'missing_page','page count')
    require([p['page_number'] for p in pages]==list(range(1,len(pages)+1)),'missing_page','page order/count')
    pieces=[];cursor=0
    for page in pages:
        raw=verify_file(root/'extracted',page['raw_text_path'],page['raw_text_sha256']).read_text()
        value=verify_file(root/'extracted',page['text_path'],page['text_sha256']).read_text()
        require(value==normalize(raw) and page['classification']=='text' and value.strip(),'missing_page','blank/nontext/mismatching page')
        if pieces:cursor+=len(SEPARATOR)
        require((page['start'],page['end'])==(cursor,cursor+len(value)),'offset','page offset')
        pieces.append(value);cursor+=len(value)
    require(SEPARATOR.join(pieces)==text,'offset','canonical/page contents differ')
    return doc,text


def span(text,doc,start,end):
    require(type(start)==int and type(end)==int and 0<=start<end<=len(text),'offset','invalid span')
    return dict(document_id=DID,start=start,end=end,quote=text[start:end],
      pages=[p['page_number'] for p in doc['pages'] if start<p['end'] and end>p['start']],canonical_sha256=doc['canonical_sha256'])


def check_span(value,text,doc):
    expected=span(text,doc,value['start'],value['end'])
    require(all(value.get(k)==v for k,v in expected.items()),'offset','quote/page/hash mismatch')


def align(model,text,doc):
    ignored=[]
    for p in doc['pages']:
        value=text[p['start']:p['end']]
        m=re.search(r'HR-V4-HANDBOOK / v4\n'+str(p['page_number'])+r'\s*$',value)
        require(m is not None,'footer','missing continuous page footer')
        ignored.append(dict(start=p['start']+m.start(),end=p['end'],reason='PDF footer',page=p['page_number']))
    ignore=set(i for r in ignored for i in range(r['start'],r['end']))
    positions=[i for i,c in enumerate(text) if not c.isspace() and i not in ignore]
    actual=''.join(text[i] for i in positions)
    expected=''.join(compact(b['text']) for b in model['blocks'])
    require(actual==expected,'full_text','entire authored text/order differs from PDF (whitespace/footer only excluded)')
    mapped={};source_to_canonical={};cursor=0;front=[]
    for block in model['blocks']:
        inds=[i for i,c in enumerate(block['text']) if not c.isspace()]
        target=positions[cursor:cursor+len(inds)];cursor+=len(inds)
        for a,b in zip(inds,target):source_to_canonical[block['start']+a]=b
        s=span(text,doc,target[0],target[-1]+1)
        if 'id' in block:mapped[block['id']]=s
        else:front.append(dict(type=block['type'],**s))
    return mapped,source_to_canonical,ignored,front


def mapped_span(start,end,positions,text,doc):
    ix=[positions[i] for i in range(start,end) if i in positions]
    require(bool(ix),'offset','empty mapped span')
    return span(text,doc,ix[0],ix[-1]+1)


def derive(root):
    source=(root/'authoring/hr-handbook.md').read_text();model=parse(source)
    spec=read_json(root/'corpus-spec.json');profile=check_structure(model,spec)
    doc,text=load_document(root);mapped,positions,ignored,front=align(model,text,doc)
    review=read_json(root/'authoring-review.json');baseline=read_json(root/'baseline-policy.json')
    require(review['authoring_sha256']==file_hash(root/'authoring/hr-handbook.md'),'review_stale','review is for another draft')
    notes=review['articles'];articles=[n for n in model['nodes'] if n['level']==4]
    require(set(notes)=={n['id'] for n in articles},'review_missing','article review coverage')
    for a in articles:
        note=notes[a['id']]
        require(note['paragraph_ids']==a['paragraphs'] and note['review'] and note['nonconflict_reason'],'review_missing','paragraph review coverage/rationale')
    for chapter in profile['chapters']:
        cid=chapter['chapter_id'];struc=review['structure'][cid]
        require(len(struc['flows'])>=1 and len(struc['exceptions'])>=2,'structure_review','flow/exception counts')
        for item in struc['flows']+struc['exceptions']:
            require(item['purpose'] and item['condition'] and item['base'] in notes and item['article'] in notes and item['article'].startswith(cid+'-'),'structure_review','invalid procedure link')
            require(item['evidence'] in source[source.index('#### '+item['article']):].split('\n#### ',1)[0].split('\n## ',1)[0],'structure_review','missing exception evidence')
        chapter['procedure_review']=struc
    nodes=[]
    for i,n in enumerate(model['nodes']):
        children=[x for x in model['nodes'][i+1:] if x['level']<=n['level']]
        stop=mapped[children[0]['id']]['start'] if children else len(text)
        own=mapped[n['id']]
        descendants=[p for p in model['paragraphs'] if own['end']<mapped[p['id']]['start']<stop]
        body=span(text,doc,mapped[descendants[0]['id']]['start'],mapped[descendants[-1]['id']]['end']) if descendants else None
        nodes.append(dict(id=n['id'],level=n['level'],parent_id=n['parent_id'],title_path=n['title_path'],heading=own,
                          extent=span(text,doc,own['start'],stop),body=body,authored_body_chars=n.get('body_chars')))
    byid={n['id']:n for n in nodes}
    for n in nodes:
        if n['parent_id']:
            p=byid[n['parent_id']]['extent'];require(p['start']<=n['extent']['start']<n['extent']['end']<=p['end'],'hierarchy','parent does not contain child')
    ps=[];inventory=[]
    old_by_text={c['text']:c for c in baseline['policies']};seen_old=set()
    for p in model['paragraphs']:
        ps.append(dict(id=p['id'],article_id=p['article_id'],classification=p['kind'],authored_span=dict(start=p['start'],end=p['end']),canonical=mapped[p['id']],body_chars=len(p['text'])))
        count=0
        for match in re.finditer(r'.+?(?:\.(?=\s|$)|$)',p['text']):
            sentence=match[0].strip()
            if not sentence:continue
            left=match.start()+len(match[0])-len(match[0].lstrip());right=match.end()-len(match[0])+len(match[0].rstrip())
            count+=1;old=old_by_text.get(sentence)
            if p['kind']=='preserved':
                require(old is not None,'policy_preservation','preserved sentence has no v3 provenance: '+sentence)
                seen_old.add(old['claim_id'])
            else:require(old is None,'classification','original policy mislabeled')
            row=dict(id=p['id']+'-S'+str(count).zfill(2),article_id=p['article_id'],paragraph_id=p['id'],classification=p['kind'],
              authored_text=sentence,authored_span=dict(start=p['start']+left,end=p['start']+right),
              canonical=mapped_span(p['start']+left,p['start']+right,positions,text,doc),
              reason=notes[p['article_id']]['review'],nonconflict_reason=notes[p['article_id']]['nonconflict_reason'],
              related_articles=sorted({r['target'] for r in model['references'] if r['paragraph_id']==p['id']}))
            if old:row['source_v3']=old
            if p['kind']=='explanatory':
                row['explains_articles']=row['related_articles'] or [p['article_id']]
            inventory.append(row)
    require(seen_old=={p['claim_id'] for p in baseline['policies']},'policy_missing','some original claims missing')
    policy_map=[]
    for c in baseline['policies']:
        targets=[dict(id=x['id'],**x['canonical']) for x in inventory if x.get('source_v3',{}).get('claim_id')==c['claim_id']]
        policy_map.append(dict(claim_id=c['claim_id'],source_v3=c,targets=targets))
    occurrences=[]
    for i,old in enumerate(baseline['body_occurrences'],1):
        targets=[x['id'] for x in inventory if x.get('source_v3',{}).get('claim_id') in old['policy_ids']]
        require(bool(targets),'policy_missing','v3 body occurrence lacks target')
        occurrences.append(dict(occurrence=i,source_v3=old,target_inventory_ids=targets,method='Same original policy ID; repeated v3 occurrences consolidated. Birthday-point paraphrase resolves to its original point/leave independence policy.'))
    duplicate=[];near=[]
    for i,p in enumerate(model['paragraphs']):
        for q in model['paragraphs'][i+1:]:
            if compact(p['text'])==compact(q['text']):duplicate.append([p['id'],q['id']])
            elif min(len(p['text']),len(q['text']))>=80:
                # Character bigram Dice is a candidate screen, not a semantic duplication verdict.
                a={p['text'][j:j+2] for j in range(len(p['text'])-1)};b={q['text'][j:j+2] for j in range(len(q['text'])-1)}
                score=2*len(a&b)/(len(a)+len(b))
                if score>=.58:near.append(dict(paragraphs=[p['id'],q['id']],bigram_dice=round(score,4)))
    require(not duplicate,'duplicate_body','exact duplicate paragraphs need removal before freeze')
    crossing=[p['id'] for p in ps if len(p['canonical']['pages'])>1]
    cross_articles=[n['id'] for n in nodes if n['level']==4 and len(n['body']['pages'])>1]
    require(len(crossing)+len(cross_articles)>=spec['whole_corpus']['min_page_crossing_articles_or_paragraphs'],'page_crossing','too few boundary cases')
    for chap in profile['chapters']:
        node=byid[chap['chapter_id']];chap['canonical_chars']=node['extent']['end']-node['extent']['start'];chap['pages']=node['extent']['pages']
    profile.update(canonical_chars=len(text),pages=len(doc['pages']),article_count=len(articles),paragraph_count=len(ps),page_crossing_paragraphs=crossing,page_crossing_articles=cross_articles,
      duplicate_paragraphs=duplicate,near_duplicate_candidates=near,near_duplicate_method='character bigram Dice >= 0.58; manual full review remains required',classification_counts=dict(Counter(x['classification'] for x in inventory)),
      authoring_sha256=file_hash(root/'authoring/hr-handbook.md'),canonical_sha256=doc['canonical_sha256'])
    refs=[dict(**r,canonical=mapped_span(r['start'],r['end'],positions,text,doc)) for r in model['references']]
    return {'section-map.json':dict(document_id=DID,canonical_sha256=doc['canonical_sha256'],nodes=nodes,paragraphs=ps,references=refs,frontmatter_and_toc=front,excluded_footer_spans=ignored),
      'length-accounting.json':model['length_accounting'], 'corpus-profile.json':profile,
      'policy-inventory.json':dict(document_id=DID,review_type='Codex fictional-source review; NOT human approved ground truth',items=inventory),
      'policy-map.json':dict(source_commit=baseline['source_commit'],original_claims=policy_map,source_v3_body_occurrences=occurrences,added_inventory_ids=[x['id'] for x in inventory if x['classification']=='added_fictional'],explanatory_inventory_ids=[x['id'] for x in inventory if x['classification']=='explanatory'])}
