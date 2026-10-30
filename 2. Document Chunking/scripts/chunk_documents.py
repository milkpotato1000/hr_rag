#!/usr/bin/env python3
"""Run a frozen P007 configuration over the registered canonical source."""
import argparse,json
from pathlib import Path
from document_common import read_json,cli_error,atomic_directory,write_json
from chunk_core import build

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--documents',type=Path,required=True);p.add_argument('--config',required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--parent',type=Path);a=p.parse_args()
    try:
        cfg=read_json(a.config) if Path(a.config).is_file() else a.config
        print(json.dumps(build(cfg,a.output_dir,parent=a.parent,documents=a.documents),ensure_ascii=False))
    except (ValueError,OSError,KeyError,TypeError) as e:
        if not a.output_dir.exists():
            with atomic_directory(a.output_dir) as target:
                write_json(target/'manifest.json',dict(schema_version=1,run_id=a.output_dir.name,status='failed',reason=getattr(e,'kind','execution'),message=str(e),config=a.config))
        return cli_error(e)
    return 0
if __name__=='__main__':raise SystemExit(main())
