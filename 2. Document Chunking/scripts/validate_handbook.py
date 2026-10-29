#!/usr/bin/env python3
"""Validate immutable v4 hashes, continuous spans, whole text and all policy mappings."""
import argparse
from pathlib import Path
from document_common import STAGE,read_json,verify_file,cli_error
from handbook_model import require,DID
from handbook_artifacts import derive

ROOT=STAGE/'data/source-v4'

def validate(root,frozen=True):
    if frozen:
        m=read_json(root/'handoff-manifest.json')
        require(m['document_id']==DID and m['corpus_version']==4 and m['model_calls']==0 and m['retrieval_runs']==0,'handoff','wrong corpus scope')
        require(m['p007_requires_new_readiness'] and not m['old_p007_budgets_adopted'],'handoff','P007 must be re-prepared')
        files={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name!='handoff-manifest.json'}
        require(files==set(m['files']),'handoff','missing or unexpected frozen file')
        for path,digest in m['files'].items():verify_file(root,path,digest)
    expected=derive(root)
    for name,value in expected.items():require(read_json(root/name)==value,'derived_mismatch',name+' differs from recomputation')
    p=expected['corpus-profile.json']
    return dict(status='PASS',documents=1,pages=p['pages'],body_chars=p['body_chars'],articles=p['article_count'],paragraphs=p['paragraph_count'],classifications=p['classification_counts'],page_crossing_paragraphs=len(p['page_crossing_paragraphs']))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,default=ROOT);p.add_argument('--unfrozen',action='store_true');a=p.parse_args()
    try:print(validate(a.source_root,not a.unfrozen))
    except (ValueError,OSError,KeyError,TypeError) as e:return cli_error(e)
    return 0
if __name__=='__main__':raise SystemExit(main())
