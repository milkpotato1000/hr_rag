#!/usr/bin/env python3
"""Create source-v4 maps and freeze a handoff in a NEW directory."""
import argparse
from pathlib import Path
from document_common import STAGE, atomic_directory, write_json, read_json, file_hash, cli_error
from handbook_artifacts import derive
from handbook_model import require,DID

ROOT=STAGE/'data/source-v4'
ARTIFACTS=('section-map.json','length-accounting.json','corpus-profile.json','policy-inventory.json','policy-map.json')

def create(root,output):
    result=derive(root)
    with atomic_directory(output) as dest:
        for name,value in result.items():write_json(dest/name,value)
    return result['corpus-profile.json']

def freeze(root,output,source_commit):
    require(len(source_commit)==40 and all(c in '0123456789abcdef' for c in source_commit),'provenance','full source commit required')
    expected=derive(root)
    for name,value in expected.items():require(read_json(root/name)==value,'derived_mismatch',name)
    files={str(p.relative_to(root)):file_hash(p) for p in sorted(root.rglob('*')) if p.is_file() and p.name!='handoff-manifest.json'}
    require(not (root/'handoff-manifest.json').exists(),'output_exists','freeze requires an unfrozen source')
    manifest=dict(schema_version=1,document_id=DID,corpus_version=4,effective_date=None,files=files,
      plan_commit='96ebe9d612bb4a1aae4f52fa25ee650139b5114f',source_commit=source_commit,
      source_commit_scope='Frozen authoring, implementation and source artifacts commit. External P016 completion record connects final verification and this manifest hash, avoiding self hashing.',
      completion_record='docs/verification/p016/completion.json',
      only_collected_input='output/pdf/hr-handbook.pdf',p007_requires_new_readiness=True,
      p007_reconsider=['five methods and overlap','long-article subdivision and section metadata','new claims/questions, multi-article questions, tuning/holdout separation','full document coverage and actual windows','model compatibility and request/time/vector budget','TOC/chapter/section/page navigation and long chunk lists','minimum three repetitions unless plan explicitly amends'],
      old_p007_budgets_adopted=False,model_calls=0,retrieval_runs=0,
      warnings=['Fictional operating handbook, not real company rules or legal guidance.','Preservation and narrative review by Codex is not human-approved GT.','Page footers stay in canonical; section map records their spans, not silent cleanup.','Cross-page quotes may contain footers. Positions use Unicode codepoints [start,end), not PDF coordinates.','Corpus expansion is not evidence of improved retrieval.'])
    with atomic_directory(output) as dest:write_json(dest/'handoff-manifest.json',manifest)
    return dict(files=len(files))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,default=ROOT);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--freeze-source-commit');a=p.parse_args()
    try:print(freeze(a.source_root,a.output_dir,a.freeze_source_commit) if a.freeze_source_commit else {'pages':create(a.source_root,a.output_dir)['pages']})
    except (ValueError,OSError,KeyError,TypeError) as e:return cli_error(e)
    return 0
if __name__=='__main__':raise SystemExit(main())
