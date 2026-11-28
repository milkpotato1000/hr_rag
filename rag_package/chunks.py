"""Source-slice rule chunking. See provenance.json for selected P007 algorithms."""
from bisect import bisect_right
import re
from .documents import intersections
from .storage import fingerprint, require

ALGORITHM='general-rules-v1'


def recursive(text,start,end,maximum,max_spans=None):
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
        if max_spans is not None:require(len(spans)<max_spans,'chunk_limit','chunking')
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


HANDBOOK_PROFILE = 'handbook-v1'
_CHAPTER = re.compile(r'^제[ ]*\d+[ ]*장[ \t]+[^\n]+?[ \t]+\[([A-Z]{2,8})\][ \t]*$', re.M)
_SECTION = re.compile(r'^제[ ]*(\d+)[ ]*절[ \t]+[^\n]+?[ \t]+\[([A-Z]{2,8})-S(\d+)\][ \t]*$', re.M)
_ARTICLE = re.compile(r'^([A-Z]{2,8})-\d{2,3}[ \t]+[가-힣A-Za-z0-9][가-힣A-Za-z0-9 ·/()\-]{0,95}$', re.M)


def handbook_headings(text):
    """Tagged body headings only. Untagged chapter listings are front matter."""
    chapters = list(_CHAPTER.finditer(text))
    if not chapters:
        return []
    first = chapters[0]
    contents = re.search(r'^(?:통합 )?목차[ \t]*$', text[:first.start()], re.M)
    if contents:
        # Some contents lists repeat the tagged first chapter verbatim.
        first = next((m for m in chapters[1:] if m[0].strip() == first[0].strip()), first)
    matches = [(m.start(), level, m) for level, pattern in
               enumerate((_CHAPTER, _SECTION, _ARTICLE), 1)
               for m in pattern.finditer(text, first.start())]
    path = []
    nodes = []
    chapter_code = None
    for offset, level, match in sorted(matches, key=lambda item: item[0]):
        title = match[0].strip()
        if level == 1:
            chapter_code = match[1]
        elif level == 2:
            if match[2] != chapter_code or match[1] != match[3]:
                continue
        elif len(path) < 2 or match[1] != chapter_code or title.endswith('다'):
            continue
        path = path[:level-1] + [title]
        nodes.append({'start':offset, 'level':level, 'heading_path':path})
    return nodes


def rule_settings(config):
    keys = ('method', 'size_chars', 'overlap_chars', 'heading_profile')
    return {key:config[key] for key in keys if key in config}


def validate_heading_profile(config):
    if 'heading_profile' in config:
        require(config.get('method') == 'structure' and config['heading_profile'] == HANDBOOK_PROFILE,
                'invalid_heading_profile', 'chunking')


def make_chunks(docs,source_fp,cfg,*,max_chunks=None):
    emitted=[];coverage=[];details=[]
    size,overlap=cfg['size_chars'],cfg['overlap_chars']
    for d in docs:
        text=d['text'];method=cfg['method']
        validate_heading_profile(cfg)
        nodes=handbook_headings(text) if 'heading_profile' in cfg else headings(text)
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
                    if max_chunks is not None:require(len(coverage)+len(spans)<max_chunks,'chunk_limit','chunking')
                    stop=min(start+size,end);spans.append((start,stop,start,stop,path))
                    if stop==end:break
                    start=stop-overlap
            else:
                for a,b in recursive(text,begin,end,size-overlap,None if max_chunks is None else max_chunks-len(coverage)-len(spans)):
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
