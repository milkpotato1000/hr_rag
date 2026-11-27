"""Isolated PDF reader. Called only for explicit snapshot PDF inputs."""
import importlib
import json
from pathlib import Path
import sys

def extract(path):
    try:
        pypdf=importlib.import_module('pypdf')
    except ImportError:return {'status':'needs_review','reason':'pypdf_missing','pages':[],'parser_version':None}
    if pypdf.__version__!='6.21.2':return {'status':'needs_review','reason':'pypdf_version_mismatch','pages':[],'parser_version':pypdf.__version__}
    result=extract_pages(pypdf,path)
    return dict(result,parser_version=pypdf.__version__)

def extract_pages(pypdf,path):
    try:
        reader=pypdf.PdfReader(path)
        if reader.is_encrypted:return {'status':'needs_review','reason':'encrypted_pdf_unsupported','pages':[]}
        if not 1<=len(reader.pages)<=100:return {'status':'needs_review','reason':'pdf_page_limit','pages':[]}
        pages=[];total=0
        for page in reader.pages:
            text=page.extract_text() or ''
            total+=len(text)
            if total>1_000_000:return {'status':'needs_review','reason':'canonical_limit','pages':[]}
            pages.append(text)
        return {'status':'ready' if all(p.strip() for p in pages) else 'needs_review','reason':None if all(p.strip() for p in pages) else 'empty_or_scanned_page_ocr_not_supported','pages':pages}
    except Exception:return {'status':'needs_review','reason':'pdf_parse_failed','pages':[]}

if __name__=='__main__':
    Path(sys.argv[2]).write_text(json.dumps(extract(sys.argv[1]),ensure_ascii=False),encoding='utf-8')
