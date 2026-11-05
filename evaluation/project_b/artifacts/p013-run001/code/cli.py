"""Offline commands never instantiate the model runner or call its transport."""
import argparse
import shutil
from pathlib import Path
from evaluator import read, write, sha
from execution import verify, replay, run
from reporting import render


def export_bundle(run_dir,output):
    verify(run_dir/'manifest.json')
    if output.exists(): raise ValueError('bundle destination exists')
    # Excludes process-local lock files; keeps frozen inputs/code and every result.
    shutil.copytree(run_dir,output,ignore=shutil.ignore_patterns('.runner.lock','__pycache__','*.tmp'))
    write(output/'bundle-manifest.json',dict(schema_version='p013-bundle-v1',files={str(p.relative_to(output)):sha(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file()},
        replay_command='python3 -B code/cli.py replay --run-dir . --output replay.json',live_reexecution='Requires locked Ollama and original P007 indexes; offline replay does not.'))
    return output


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('validate');p.add_argument('--manifest',type=Path,required=True)
    p=sub.add_parser('run');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--stage',choices=['extraction','judge','e2e'],required=True)
    for name in ['replay','report','export-bundle']:
        p=sub.add_parser(name);p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='validate': print('PASS',verify(args.manifest)['manifest_sha256'])
    elif args.command=='run':
        result=run(args.manifest,args.stage);write(args.manifest.parent/(args.stage+'-report.json'),result)
    elif args.command=='replay': write(args.output,replay(args.run_dir));print(args.output)
    elif args.command=='report':
        content=render(replay(args.run_dir))
        if args.output.exists() and args.output.read_text()!=content: raise ValueError('report exists; use new version path')
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(content);print(args.output)
    else: print(export_bundle(args.run_dir,args.output))


if __name__=='__main__': main()
