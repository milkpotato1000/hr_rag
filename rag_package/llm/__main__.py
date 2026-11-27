"""python3 -m rag_package.llm --help"""
import argparse
import json
import os
from pathlib import Path
import tempfile
from . import ValidationError, read_json, validate_config, preview, invoke

class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValidationError('arguments','invalid_arguments')


def atomic_result(path, result):
    target=Path(path)
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=target.parent,delete=False) as f:
            temp=f.name
            json.dump(result,f,ensure_ascii=False,allow_nan=False,indent=2)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.link(temp,target)  # Atomic no-clobber publication, including symlink targets.
    except OSError:
        raise ValidationError('output','output_write_failed') from None
    finally:
        if temp is not None:
            os.unlink(temp)


def main(argv=None):
    try:
        parser=Parser(description='Independent LLM adapters. Preview may contain private prompt text; proxies/retries/fallback are disabled.')
        subs=parser.add_subparsers(dest='command',required=True)
        for name in ('validate','preview','invoke'):
            sub=subs.add_parser(name)
            sub.add_argument('--config',required=True)
            if name!='validate':
                sub.add_argument('--role',choices=('generation','evaluation','chunking'),required=True)
                sub.add_argument('--messages',required=True)
            if name=='invoke': sub.add_argument('--output',required=True)
        a=parser.parse_args(argv)
        config=validate_config(read_json(a.config))
        if a.command=='validate': result={'schema_version':1,'status':'valid'}
        else:
            messages=read_json(a.messages)
            if a.command=='preview': result=preview(config,a.role,messages)
            else:
                target=Path(a.output)
                if target.exists() or target.is_symlink() or not target.parent.is_dir():
                    raise ValidationError('output','output_must_be_new')
                # Validate before probing output permissions; do not invoke if output cannot be created.
                preview(config,a.role,messages)
                try:
                    with tempfile.TemporaryFile(dir=target.parent): pass
                except OSError: raise ValidationError('output','output_unwritable') from None
                result=invoke(config,a.role,messages)
                atomic_result(target,result)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0 if a.command!='invoke' or result['status']=='complete' else 1
    except ValidationError as e:
        print(json.dumps({'status':'error','error':{'code':e.code,'field':e.field}}))
        return 2
    except Exception:
        print(json.dumps({'status':'error','error':{'code':'internal_error'}}))
        return 2

if __name__=='__main__':
    raise SystemExit(main())
