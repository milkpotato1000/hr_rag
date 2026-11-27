"""General explicit-file snapshots with page provenance and strict consumers."""
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata
from .llm.config import fields, read_json as input_json, string, ValidationError
from .storage import RagError, require, digest, fingerprint, write_json, read_json, staging, seal, verify, safe_path

MAX_BYTES=20*1024*1024

def normalize(text):return unicodedata.normalize('NFC',text.replace('\r\n','\n').replace('\r','\n'))
def safe_id(value):return isinstance(value,str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',value))


def parse_pdf(path,target):
    try:
        subprocess.run([sys.executable,'-m','rag_package.pdf_worker',str(path),str(target)],cwd=Path(__file__).resolve().parent.parent,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,check=True)
        return read_json(target)
    except subprocess.TimeoutExpired:return {'status':'needs_review','reason':'pdf_timeout','pages':[]}
    except (subprocess.SubprocessError,OSError,RagError):return {'status':'needs_review','reason':'pdf_parse_failed','pages':[]}
    finally:
        if target.exists():target.unlink()


def snapshot(sources,out):
    started=time.monotonic();sources=Path(sources)
    try:
        cfg=input_json(sources);fields(cfg,{'schema_version','documents'},set(),'sources')
        require(type(cfg['schema_version']) is int and cfg['schema_version']==1,'invalid_schema','snapshot')
        docs=cfg['documents'];require(isinstance(docs,list) and 1<=len(docs)<=20,'document_limit','snapshot')
        ids=set()
        for d in docs:
            fields(d,{'document_id','title','path','format','synthetic'},set(),'document')
            require(safe_id(d['document_id']) and d['document_id'] not in ids,'duplicate_or_invalid_id','snapshot');ids.add(d['document_id'])
            string(d['title'],'document.title');string(d['path'],'document.path')
            require(d['format'] in ('pdf','txt','md') and type(d['synthetic']) is bool,'unsupported_source','snapshot')
    except ValidationError:raise RagError('invalid_sources','snapshot') from None
    with staging(out) as tmp:
        records=[];total=0
        for d in docs:
            source=Path(d['path']);source=source if source.is_absolute() else sources.parent/source
            try:
                with source.open('rb') as f:raw=f.read(MAX_BYTES+1)
            except OSError:raise RagError('source_unreadable','snapshot') from None
            require(len(raw)<=MAX_BYTES,'source_too_large','snapshot')
            folder=tmp/d['document_id'];folder.mkdir()
            original=folder/('original.'+d['format']);original.write_bytes(raw)
            if d['format']=='pdf':
                result=parse_pdf(original,tmp/'pdf-result.json');parser={'name':'pypdf','version':result.get('parser_version'),'required_version':'6.21.2'}
            else:
                try:text=raw.decode('utf-8')
                except UnicodeError:raise RagError('invalid_utf8','snapshot') from None
                require(len(text)<=1_000_000,'canonical_limit','snapshot')
                result={'status':'ready' if text.strip() else 'needs_review','reason':None if text.strip() else 'empty_text','pages':[text]}
                parser={'name':'utf8','version':'1'}
            pages=[];pieces=[];offset=0
            for n,raw_text in enumerate(result['pages'],1):
                text=normalize(raw_text)
                if n>1:offset+=2
                page={'page':n,'start':offset,'end':offset+len(text),'raw_path':f'{d["document_id"]}/page-{n}-raw.txt','text_path':f'{d["document_id"]}/page-{n}.txt','raw_sha256':digest(raw_text.encode()),'text_sha256':digest(text.encode())}
                (tmp/page['raw_path']).write_text(raw_text,encoding='utf-8',newline='')
                (tmp/page['text_path']).write_text(text,encoding='utf-8',newline='')
                pieces.append(text);pages.append(page);offset+=len(text)
            canonical='\n\n'.join(pieces);require(len(canonical)<=1_000_000,'canonical_limit','snapshot')
            total+=len(canonical);require(total<=2_000_000,'corpus_limit','snapshot')
            (folder/'canonical.txt').write_text(canonical,encoding='utf-8',newline='')
            records.append({k:d[k] for k in ('document_id','title','format','synthetic')}|{
                'original_path':str(original.relative_to(tmp)),'original_sha256':digest(raw),'bytes':len(raw),'parser':parser,
                'normalization':'NFC/LF','pages':pages,'canonical_path':d['document_id']+'/canonical.txt','canonical_sha256':digest(canonical.encode()),
                'status':result['status'],'reason':result['reason']})
        status='ready' if all(d['status']=='ready' for d in records) else 'needs_review'
        return seal(tmp,{'schema_version':1,'kind':'snapshot','status':status,'normalization':'NFC/LF','page_separator':'\n\n','offset_unit':'Unicode code point [start,end)','documents':records},round((time.monotonic()-started)*1000,3))


def load_snapshot(root,ready=True):
    root=Path(root);m=verify(root,'snapshot');i=m['identity']
    if ready:require(i.get('status')=='ready','source_needs_review','snapshot')
    docs=[];seen=set();total=0
    require(isinstance(i.get('documents'),list) and 1<=len(i['documents'])<=20,'invalid_manifest','snapshot')
    for d in i['documents']:
        require(safe_id(d['document_id']) and d['document_id'] not in seen,'invalid_document_id','snapshot');seen.add(d['document_id'])
        def data(name):
            require(name in i['files'],'unlisted_file','snapshot')
            return safe_path(root,name).read_bytes()
        original=data(d['original_path'])
        require(len(original)==d['bytes'] and digest(original)==d['original_sha256'] and len(original)<=MAX_BYTES,'stale_source','snapshot')
        canonical=data(d['canonical_path']).decode('utf-8');pieces=[];offset=0
        for n,p in enumerate(d['pages'],1):
            raw=data(p['raw_path']).decode('utf-8');text=data(p['text_path']).decode('utf-8')
            if n>1:offset+=2
            require(p['page']==n and p['start']==offset and p['end']==offset+len(text),'invalid_page_offset','snapshot')
            require(digest(raw.encode())==p['raw_sha256'] and digest(text.encode())==p['text_sha256'] and normalize(raw)==text,'stale_page','snapshot')
            pieces.append(text);offset+=len(text)
        require(canonical=='\n\n'.join(pieces) and digest(canonical.encode())==d['canonical_sha256'],'stale_canonical','snapshot')
        require(len(canonical)<=1_000_000 and len(d['pages'])<=100,'canonical_limit','snapshot')
        if ready:require(d['status']=='ready' and pieces and all(p.strip() for p in pieces),'source_needs_review','snapshot')
        total+=len(canonical);require(total<=2_000_000,'corpus_limit','snapshot')
        docs.append(dict(d,text=canonical))
    return m,docs


def intersections(pages,start,end):
    return [{'page':p['page'],'canonical_start':max(start,p['start']),'canonical_end':min(end,p['end']),
             'page_start':max(start,p['start'])-p['start'],'page_end':min(end,p['end'])-p['start']} for p in pages if start<p['end'] and end>p['start']]
