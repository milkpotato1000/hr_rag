"""Strict single-handbook authoring model. No retrieval or model runtime."""
import re
from document_common import DocumentError, normalize

DID = 'hr-v4-handbook'
TOPICS = dict(zip(('BD','AN','RM','WF','ED','TR'), ('birthday','annual','remote','welfare','training','travel')))
CATEGORIES = {'preserved','added_fictional','explanatory'}

def require(ok, kind, message):
    if not ok:
        raise DocumentError(kind, message)

def compact(text):
    return ''.join(text.split())

def parse(source):
    require(source == normalize(source), 'normalization', 'authoring must already be NFC/LF')
    blocks, nodes, paragraphs, included = [], [], [], []
    stack = {}; kind = None; cursor = 0; article = None
    for raw in source.splitlines(keepends=True):
        line = raw.rstrip('\n'); start = cursor; cursor += len(raw)
        if not line:
            continue
        marker = re.fullmatch(r'<!-- kind: ([a-z_]+) -->', line)
        if marker:
            require(article is not None and marker[1] in CATEGORIES, 'classification', 'invalid kind marker')
            kind = marker[1]; continue
        h = re.fullmatch(r'(#{1,4}) (.+)', line)
        if h:
            level, title = len(h[1]), h[2]
            if level == 1:
                require(not nodes, 'hierarchy', 'only one document title')
                nid = DID
            elif level == 2 and title == '통합 목차':
                require(not article, 'hierarchy', 'TOC must precede body')
                blocks.append(dict(type='toc_heading', text=title, start=start+3, end=start+len(line)))
                continue
            elif level in (2,3):
                m = re.search(r'\[([A-Z]{2}(?:-S[1-9][0-9]*)?)\]$', title)
                require(m is not None, 'hierarchy', 'missing chapter/section ID')
                nid = m[1]
                require((level==2 and nid in TOPICS) or (level==3 and '-S' in nid), 'hierarchy', 'wrong ID level')
            else:
                m = re.match(r'([A-Z]{2}-[0-9]{2}) ', title)
                require(m is not None, 'hierarchy', 'missing article ID'); nid=m[1]
            require(nid not in {n['id'] for n in nodes}, 'duplicate_id', nid)
            require(level==1 or level-1 in stack, 'hierarchy', 'skipped parent level')
            parent=stack.get(level-1)
            if level>2:
                require(nid[:2]==stack[2], 'hierarchy', 'chapter ID mismatch')
            for k in list(stack):
                if k>=level: del stack[k]
            node=dict(id=nid, level=level, title=title, parent_id=parent,
                      heading_start=start+level+1, heading_end=start+len(line), paragraphs=[])
            nodes.append(node); stack[level]=nid
            node['title_path']=[next(n['title'] for n in nodes if n['id']==stack[k]) for k in sorted(stack)]
            blocks.append(dict(type='heading',text=title,start=node['heading_start'],end=node['heading_end'],id=nid,level=level))
            article=node if level==4 else None; kind=None
        elif article:
            require(kind in CATEGORIES, 'classification', 'unclassified body in '+article['id'])
            require(not line.startswith(('#','<!--','- ')), 'markup', 'unsupported body markup')
            pid=article['id']+'-P'+str(len(article['paragraphs'])+1).zfill(2)
            p=dict(id=pid,article_id=article['id'],kind=kind,text=line,start=start,end=start+len(line))
            paragraphs.append(p);article['paragraphs'].append(pid)
            blocks.append(dict(type='body',text=line,start=start,end=p['end'],id=pid))
        else:
            require(len(nodes)==1,'hierarchy','body outside article')
            blocks.append(dict(type='frontmatter',text=line,start=start,end=start+len(line)))
    require(len([n for n in nodes if n['level']==1])==1, 'hierarchy', 'one title required')
    for n in nodes:
        if n['level']!=4: continue
        ps=[p for p in paragraphs if p['article_id']==n['id']]
        require(bool(ps),'hierarchy','empty article')
        n['body_chars']=sum(len(p['text']) for p in ps)+2*(len(ps)-1)
        for i,p in enumerate(ps):
            included.append(dict(start=p['start'],end=p['end'],reason='body',paragraph_id=p['id']))
            if i<len(ps)-1:
                require(source[p['end']:p['end']+2]=='\n\n','markup','paragraph separator must be blank line')
                included.append(dict(start=p['end'],end=p['end']+2,reason='body paragraph separator',paragraph_id=p['id']))
    included.sort(key=lambda x:x['start']); excluded=[];cur=0
    for p in included:
        if cur<p['start']:excluded.append(dict(start=cur,end=p['start'],reason='heading/frontmatter/TOC/classification markup/outer whitespace'))
        cur=p['end']
    if cur<len(source): excluded.append(dict(start=cur,end=len(source),reason='nonbody trailing whitespace'))
    refs=[]
    ids={n['id'] for n in nodes if n['level']==4}
    for p in paragraphs:
        for m in re.finditer(r'([A-Z]{2}-[0-9]{2})@v(\d+)',p['text']):
            require(m[1] in ids and m[2]=='4' and m[1]!=p['article_id'], 'reference', 'invalid/self reference '+m[0])
            refs.append(dict(source=p['article_id'],target=m[1],paragraph_id=p['id'],start=p['start']+m.start(),end=p['start']+m.end(),version=4))
    graph={i:set() for i in ids}
    for r in refs:graph[r['source']].add(r['target'])
    visited=set();active=set()
    def visit(i):
        require(i not in active,'reference','cyclic article dependency')
        if i in visited:return
        active.add(i)
        for j in graph[i]:visit(j)
        active.remove(i);visited.add(i)
    for i in graph:visit(i)
    return dict(document_id=DID,blocks=blocks,nodes=nodes,paragraphs=paragraphs,references=refs,
                length_accounting=dict(included=included,excluded=excluded,body_chars=sum(s['end']-s['start'] for s in included),source_chars=len(source)))

def check_structure(model,spec):
    ns=model['nodes'];ps=model['paragraphs'];rules=spec['per_topic_chapter'];profiles=[]
    chapters=[n for n in ns if n['level']==2]
    require([n['id'] for n in chapters]==list(TOPICS),'hierarchy','six ordered chapters required')
    for chapter,bounds in zip(chapters,spec['topic_chapters']):
        cid=chapter['id'];arts=[n for n in ns if n['level']==4 and n['id'].startswith(cid+'-')]
        paras=[p for p in ps if p['article_id'].startswith(cid+'-')]
        lengths=[n['body_chars'] for n in arts]
        count=sum(lengths)
        sections=[n for n in ns if n['parent_id']==cid]
        require(bounds['min_body_chars']<=count<=bounds['max_body_chars'],'length',cid+' body length '+str(count))
        require(len(arts)>=rules['min_articles'] and len(sections)>=rules['min_sections'],'hierarchy',cid+' counts')
        short=[a['id'] for a in arts if rules['short_article_chars'][0]<=a['body_chars']<=rules['short_article_chars'][1]]
        long=[a['id'] for a in arts if rules['long_article_chars'][0]<=a['body_chars']<=rules['long_article_chars'][1]]
        lp=[p['id'] for p in paras if rules['long_paragraph_chars'][0]<=len(p['text'])<=rules['long_paragraph_chars'][1]]
        require(len(short)>=rules['min_short_articles'] and len(long)>=rules['min_long_articles'] and len(lp)>=rules['min_long_paragraphs'],'length',cid+' short/long distribution')
        refs=[r for r in model['references'] if r['source'].startswith(cid+'-')]
        require(len(refs)>=rules['min_article_references'],'reference',cid+' references')
        profiles.append(dict(chapter_id=cid,topic=TOPICS[cid],body_chars=count,sections=len(sections),articles=len(arts),article_lengths=lengths,paragraph_lengths=[len(p['text']) for p in paras],short_articles=short,long_articles=long,long_paragraphs=lp,references=len(refs)))
    total=sum(p['body_chars'] for p in profiles)
    require(spec['total_body_chars'][0]<=total<=spec['total_body_chars'][1],'length','whole body')
    cross=[r for r in model['references'] if r['source'][:2]!=r['target'][:2]]
    require(len(cross)>=spec['whole_corpus']['min_cross_chapter_references'],'reference','cross chapter references')
    return dict(document_id=DID,body_chars=total,chapters=profiles,cross_chapter_references=cross)
