"""Source-slice rule chunking. See provenance.json for selected P007 algorithms."""
from bisect import bisect_right
import re
from .documents import intersections
from .storage import fingerprint, require

ALGORITHM='general-rules-v1'


def recursive(text,start,end,maximum):
    patterns=(r'\n\s*\n',r'[.?!。！？](?=\s|$)\s*',r'\s+')
    boundaries=[]
    for pattern in patterns:
        matches=[(m.start(),m.end()) for m in re.finditer(pattern,text)]
        boundaries.append((matches,[b for a,b in matches]))
    spans=[]
    while start<end:
        limit=min(start+maximum,end);stop=limit
        if limit<end:
            for matches,ends in boundaries:
                idx=bisect_right(ends,limit)-1
                if idx>=0 and matches[idx][0]>=start and matches[idx][1]>start:
                    stop=matches[idx][1];break
        spans.append((start,stop));start=stop
    return spans


def headings(text):
    nodes=[];stack=[]
    for m in re.finditer(r'(?m)^(#{1,6})[ \t]+([^\n]+)|^(제\s*\d+\s*(장|조))[^\n]*',text):
        level=len(m.group(1)) if m.group(1) else (1 if m.group(4)=='장' else 2)
        title=(m.group(2) if m.group(1) else m.group(0)).strip()
        while stack and stack[-1][0]>=level:stack.pop()
        stack.append((level,title));nodes.append({'start':m.start(),'level':level,'heading_path':[t for _,t in stack]})
    return nodes


def make_chunks(docs,source_fp,cfg):
    emitted=[];coverage=[];details=[]
    size,overlap=cfg['size_chars'],cfg['overlap_chars']
    for d in docs:
        text=d['text'];nodes=headings(text);method=cfg['method']
        sections=[(0,len(text),[])]
        if method=='structure' and nodes:
            sections=[]
            if nodes[0]['start']>0:sections.append((0,nodes[0]['start'],[]))
            for n,node in enumerate(nodes):sections.append((node['start'],nodes[n+1]['start'] if n+1<len(nodes) else len(text),node['heading_path']))
        details.append({'document_id':d['document_id'],'headings_detected':len(nodes),
                        'fallback':'recursive_no_heading_detected' if method=='structure' and not nodes else None})
        spans=[]
        for begin,end,path in sections:
            if method=='fixed':
                start=begin
                while start<end:
                    stop=min(start+size,end);spans.append((start,stop,start,stop,path))
                    if stop==end:break
                    start=stop-overlap
            else:
                for a,b in recursive(text,begin,end,size-overlap):
                    spans.append((a,b,max(begin,a-overlap),b,path))
        for a,b,start,end,path in spans:
            require(0<=start<end<=len(text) and end-start<=size,'chunk_bounds','chunking')
            if method!='structure':
                active=[n for n in nodes if n['start']<=start];path=active[-1]['heading_path'] if active else []
            body=text[start:end];skipped=not body.strip()
            coverage.append({'document_id':d['document_id'],'base_start':a,'base_end':b,'start':start,'end':end,'excluded':'whitespace_only' if skipped else None})
            if skipped:continue
            ident={'source_fingerprint':source_fp,'document_id':d['document_id'],'algorithm':ALGORITHM,'config':cfg,'start':start,'end':end}
            emitted.append({'chunk_id':'c-'+fingerprint(ident),'document_id':d['document_id'],'start':start,'end':end,'text':body,
                            'pages':intersections(d['pages'],start,end),'heading_path':path,'source_fingerprint':source_fp})
        ranges=sorted((r['start'],r['end']) for r in coverage if r['document_id']==d['document_id']);cursor=0
        for a,b in ranges:require(a<=cursor,'coverage_gap','chunking');cursor=max(cursor,b)
        require(cursor==len(text),'coverage_gap','chunking')
    return emitted,{'coverage':coverage,'detection':details,'whitespace_policy':'excluded from search but retained in coverage spans'}
