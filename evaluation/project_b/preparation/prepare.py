"""P019 preparation CLI. Freeze/read/replay only; no production scoring or approval."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from core import read, write, file_hash, digest, verify_inputs, payload, preflight, GROUND
from fixtures import smokes, judgements


def freeze(repo, out, model_lock):
    if (out / 'frozen.json').exists():
        raise ValueError('Frozen run exists; verify/replay it, do not overwrite')
    inputs_path = repo / 'docs/planning/specs/P019-review-inputs.json'
    inputs = read(inputs_path)
    src = repo / '2. Document Chunking/data/source-v4'
    canonical_path = src / 'extracted/canonical/hr-v4-handbook.txt'
    canonical = canonical_path.read_text(); sections = read(src / 'section-map.json')
    verify_inputs(inputs, canonical, sections)
    handoff = read(src / 'handoff-manifest.json')
    for rel, expected in handoff['files'].items():
        if file_hash(src / rel) != expected:
            raise ValueError('Source inventory hash mismatch: ' + rel)
    tracked_input_paths = ['extracted/canonical/hr-v4-handbook.txt', 'extracted/manifest.json', 'section-map.json', 'policy-inventory.json', 'handoff-manifest.json']
    provenance = {}
    for rel in tracked_input_paths:
        path = src / rel
        historical = subprocess.check_output(['git', 'show', inputs['source_commit'] + ':' + str(path.relative_to(repo))], cwd=repo)
        if historical != path.read_bytes():
            raise ValueError('P007 source snapshot mismatch: ' + rel)
        dest = out / 'source' / rel; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
        provenance[str(dest.relative_to(out))] = file_hash(dest)
    extracted = read(src / 'extracted/manifest.json')['documents'][0]
    pdf_hash = extracted['original_sha256']
    if not any(pdf_hash == h for h in handoff['files'].values()):
        raise ValueError('PDF not in source inventory')
    stage = repo / '2. Document Chunking'
    exp = read(stage / 'artifacts/experiment-002/manifest.json')
    selection = exp['selection']
    assert selection['baseline'] == 'fixed-400-80' and selection['candidate'] == 'structure-0'
    p007 = dict(experiment_manifest_sha256=file_hash(stage / 'artifacts/experiment-002/manifest.json'),
                source_pdf_sha256=pdf_hash, baseline='fixed-400-80', candidate='structure-0', runs={})
    for label in ['baseline', 'candidate']:
        run = selection[label + '_run_id']; path = stage / 'artifacts' / run / 'manifest.json'
        old = subprocess.check_output(['git', 'show', inputs['source_commit'] + ':' + str(path.relative_to(repo))], cwd=repo)
        assert old == path.read_bytes()
        p007['runs'][label] = dict(run_id=run, manifest_sha256=file_hash(path), manifest=read(path))
    write(out / 'p007-inputs.json', p007, immutable=True)
    write(out / 'inputs.json', inputs, immutable=True)
    lock = read(model_lock)
    write(out / 'model-lock.json', lock, immutable=True)
    cases = smokes()
    for q in inputs['questions']:
        if q['answerability'] == 'answerable':
            cases.append(dict(id=q['id'], role='ground', question=q['question'], schema=GROUND,
                              units=[dict(id=s['article_id'], text=s['text']) for s in q['source_spans']]))
    checks = []; failures = []
    for case in cases:
        case['payload'] = payload(case); case['payload_sha256'] = digest(case['payload'])
        try:
            budget = preflight(case['payload'], lock)
            checks.append(dict(id=case['id'], **budget))
        except ValueError as exc:
            failures.append(dict(id=case['id'], error=str(exc)))
    write(out / 'cases.json', cases, immutable=True)
    write(out / 'judgements.json', judgements(), immutable=True)
    write(out / 'preflight.json', dict(passed=not failures, checks=checks, failures=failures), immutable=True)
    for name in ['inputs.json', 'model-lock.json', 'cases.json', 'judgements.json', 'p007-inputs.json', 'preflight.json']:
        provenance[name] = file_hash(out / name)
    frozen = dict(version='p019-preparation-v1', human_approval=None, files=provenance,
                  prompt_version='p019-source-only-v1', schema_version='p019-strict-json-v1')
    frozen['sha256'] = digest(frozen)
    write(out / 'frozen.json', frozen, immutable=True)
    if failures:
        raise ValueError('Input budget failure preserved; no model calls allowed')
    print('Frozen:', frozen['sha256'], 'max byte bound:', max(x['upper_bound'] for x in checks))


def verify_frozen(out):
    frozen = read(out / 'frozen.json')
    if frozen['sha256'] != digest({k: v for k, v in frozen.items() if k != 'sha256'}):
        raise ValueError('frozen manifest changed')
    for name, h in frozen['files'].items():
        if file_hash(out / name) != h:
            raise ValueError('frozen artifact changed: ' + name)
    if not read(out / 'preflight.json')['passed']:
        raise ValueError('Input safety unresolved; blocked before model invocation')
    verify_inputs(read(out / 'inputs.json'), (out / 'source/extracted/canonical/hr-v4-handbook.txt').read_text(),
                  read(out / 'source/section-map.json'))
    for case in read(out / 'cases.json'):
        if case['payload_sha256'] != digest(case['payload']) or case['payload'] != payload(case):
            raise ValueError('payload mismatch or truncation')
        preflight(case['payload'], read(out / 'model-lock.json'))
    return frozen


def active_cases(out):
    cases = read(out / 'cases.json')
    revision_path = out / 'ground-prompt-v2.json'
    if not revision_path.exists():return cases
    revision = read(revision_path)
    if revision['sha256'] != digest({k:v for k,v in revision.items() if k!='sha256'}):raise ValueError('revision hash mismatch')
    ledger = read(out / 'ledger.json')
    if ledger.get('prompt_revision_sha256') != revision['sha256']:raise ValueError('revision not registered in cumulative ledger')
    revised = {c['id']:c for c in revision['cases']}
    result=[]
    for original in cases:
        c = revised.get(original['id'], original)
        if c is not original:
            for k,v in original.items():
                if k not in ('payload','payload_sha256') and c[k]!=v:raise ValueError('revision changed question/source/schema')
            if c.get('prompt_version')!='ground-v2' or c['role']!='ground':raise ValueError('invalid prompt revision')
            if c['payload']!=payload(c) or c['payload_sha256']!=digest(c['payload']):raise ValueError('revised payload mismatch')
            preflight(c['payload'],read(out/'model-lock.json'))
        result.append(c)
    if set(revised)-{c['id'] for c in cases}:raise ValueError('unexpected revision case')
    return result


def revise_ground(out):
    verify_frozen(out); ledger=read(out/'ledger.json')
    if ledger['pending'] or ledger['unresolved']:raise ValueError('request unresolved')
    cases=[]
    for c in read(out/'cases.json'):
        if c['role']!='ground':continue
        c['prompt_version']='ground-v2';c['payload']=payload(c);c['payload_sha256']=digest(c['payload'])
        preflight(c['payload'],read(out/'model-lock.json'));cases.append(c)
    revision=dict(version='ground-v2',reason='Two original smoke outputs copied question into answer; clarify answer field only. Same question/source/schema, all failures retained.',cases=cases)
    revision['sha256']=digest(revision)
    write(out/'ground-prompt-v2.json',revision,immutable=True)
    if ledger.get('prompt_revision_sha256') not in (None,revision['sha256']):raise ValueError('different revision registered')
    ledger['prompt_revision_sha256']=revision['sha256'];write(out/'ledger.json',ledger)
    print('Frozen prompt revision; cumulative calls retained:',len(ledger['calls']))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    f = sub.add_parser('freeze'); f.add_argument('--repo', type=Path, required=True); f.add_argument('--out', type=Path, required=True); f.add_argument('--model-lock', type=Path, required=True)
    for name in ['verify', 'run', 'report', 'revise-ground']:
        s = sub.add_parser(name); s.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.command == 'freeze':
        freeze(args.repo.resolve(), args.out.resolve(), args.model_lock.resolve())
    elif args.command == 'run':
        from runner import run
        run(args.out)
    elif args.command == 'report':
        from report import report
        report(args.out)
    elif args.command == 'revise-ground':
        revise_ground(args.out)
    else:
        verify_frozen(args.out)
        active_cases(args.out)
        if (args.out / 'packet.json').exists():
            from report import verify_packet
            verify_packet(args.out)
        print('Offline verification PASS')


if __name__ == '__main__':
    main()
