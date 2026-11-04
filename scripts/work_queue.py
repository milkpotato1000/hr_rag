#!/usr/bin/env python3
"""Read-only plan/dev queue. Standard library only; never fetches, merges or runs work."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_cards
import plan_intake
import workflow_control

QUEUE = 'docs/planning/work-queue.json'
PROGRESS = {'plan': 'docs/planning/queue-progress', 'dev': 'docs/progress/queue'}


def git(root, *args, required=True):
    result = subprocess.run(['git', '-C', str(root), *args], text=True, capture_output=True)
    if required and result.returncode:
        raise ValueError(result.stderr.strip() or 'Git read failed')
    return result


def safe_path(path):
    p = PurePosixPath(path)
    if not isinstance(path, str) or not path or p.is_absolute() or '..' in p.parts or '\\' in path:
        raise ValueError('Evidence/work order must be a repository-relative path: ' + str(path))
    return path


class Source:
    def __init__(self, root, ref=None):
        self.root, self.ref = Path(root), ref

    def read(self, path):
        safe_path(path)
        if self.ref:
            return git(self.root, 'show', self.ref + ':' + path).stdout
        target = self.root / path
        if not target.resolve().is_relative_to(self.root.resolve()):
            raise ValueError('Path escapes repository: ' + path)
        return target.read_text()

    def paths(self, directory):
        if self.ref:
            return git(self.root, 'ls-tree', '-r', '--name-only', self.ref, '--', directory).stdout.splitlines()
        return [str(p.relative_to(self.root)) for p in (self.root / directory).glob('*.md')]

    def records(self, directory):
        if self.ref:
            names = git(self.root, 'ls-tree', '-r', '--name-only', self.ref, '--', directory).stdout.splitlines()
        else:
            names = [str(p.relative_to(self.root)) for p in (self.root / directory).glob('*.json')]
        return {Path(p).stem: json.loads(self.read(p)) for p in names if p.endswith('.json')}


def definition_hash(task, source):
    # Priority/title are scheduling/display metadata; acceptance and work-order changes invalidate completion.
    definition = {k: task[k] for k in ('id', 'owner', 'version', 'depends_on', 'work_order', 'acceptance')}
    definition['work_order_text'] = source.read(task['work_order'])
    return hashlib.sha256(json.dumps(definition, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def evaluate(document, records, source, evidence_sources):
    if document.get('schema_version') != 1 or not isinstance(document.get('tasks'), list):
        raise ValueError('Unsupported queue schema')
    tasks = {}
    hashes = {}
    for task in document['tasks']:
        ident = task['id']
        if not re.fullmatch(r'[A-Z][A-Z0-9-]*', ident) or ident in tasks:
            raise ValueError('Invalid/duplicate task ID: ' + ident)
        if task['owner'] not in PROGRESS or task['approval'] not in ('DRAFT', 'READY', 'BLOCKED'):
            raise ValueError('Invalid owner/approval: ' + ident)
        if type(task['priority']) is not int or type(task['version']) is not int or task['version'] < 1:
            raise ValueError('Invalid priority/version: ' + ident)
        if not isinstance(task['depends_on'], list) or not isinstance(task['acceptance'], dict) or not task['acceptance']:
            raise ValueError('Dependencies and acceptance criteria required: ' + ident)
        if not all(isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in task['acceptance'].items()):
            raise ValueError('Invalid acceptance criteria: ' + ident)
        if task['approval'] == 'READY' and not task.get('review_reference', '').strip():
            raise ValueError('READY needs review/authorization reference: ' + ident)
        if task['approval'] == 'BLOCKED' and not task.get('reason', '').strip():
            raise ValueError('BLOCKED needs reason: ' + ident)
        hashes[ident] = definition_hash(task, source)
        tasks[ident] = task
    for task in tasks.values():
        if any(dep not in tasks for dep in task['depends_on']):
            raise ValueError('Unknown dependency: ' + task['id'])
    visiting, visited = set(), set()

    def visit(ident):
        if ident in visiting:
            raise ValueError('Dependency cycle: ' + ident)
        if ident in visited:
            return
        visiting.add(ident)
        for dep in tasks[ident]['depends_on']:
            visit(dep)
        visiting.remove(ident)
        visited.add(ident)
    for ident in tasks:
        visit(ident)

    progress = {}
    for owner, entries in records.items():
        for ident, record in entries.items():
            if ident not in tasks or tasks[ident]['owner'] != owner or record.get('task_id') != ident:
                raise ValueError('Unknown task or wrong progress owner: ' + ident)
            task = tasks[ident]
            state = record.get('state')
            if state not in ('IN_PROGRESS', 'BLOCKED', 'DONE'):
                raise ValueError('Invalid execution state: ' + ident)
            if record.get('definition_hash') != hashes[ident]:
                raise ValueError('STALE progress; revalidate changed work order/criteria: ' + ident)
            if task['approval'] != 'READY':
                raise ValueError('Execution record cannot approve a draft/blocked task: ' + ident)
            if not record.get('updated_at', '').strip():
                raise ValueError('Progress timestamp required: ' + ident)
            checks = record.get('checks', {})
            if not isinstance(checks, dict) or set(checks) - set(task['acceptance']):
                raise ValueError('Unknown acceptance check: ' + ident)
            for criterion, paths in checks.items():
                if not isinstance(paths, list) or not paths:
                    raise ValueError('Check requires evidence paths: ' + ident + '/' + criterion)
                for path in paths:
                    if not evidence_sources[owner].read(path).strip():
                        raise ValueError('Empty evidence: ' + path)
            if state == 'DONE' and set(checks) != set(task['acceptance']):
                raise ValueError('DONE has missing acceptance evidence: ' + ident)
            if state == 'BLOCKED' and not record.get('reason', '').strip():
                raise ValueError('Blocked execution needs reason: ' + ident)
            progress[ident] = record

    rows = {}
    def resolve(ident):
        if ident in rows:
            return rows[ident]
        task = tasks[ident]
        deps = [dep for dep in task['depends_on'] if resolve(dep)['state'] != 'DONE']
        record = progress.get(ident, {})
        state = task['approval']
        reason = task.get('reason', '')
        if state == 'READY':
            state = record.get('state', 'READY')
            reason = record.get('reason', '')
            if deps:
                if state in ('IN_PROGRESS', 'DONE'):
                    raise ValueError('Execution started/completed with unmet dependency: ' + ident)
                state, reason = 'WAITING', '선행 작업: ' + ', '.join(deps)
        rows[ident] = {**task, 'state': state, 'reason': reason, 'definition_hash': hashes[ident],
                       'checked': len(record.get('checks', {})), 'total': len(task['acceptance'])}
        return rows[ident]
    result = [resolve(ident) for ident in tasks]
    for owner in PROGRESS:
        if sum(r['owner'] == owner and r['state'] == 'IN_PROGRESS' for r in result) > 1:
            raise ValueError('Only one active task per owner: ' + owner)
    return sorted(result, key=lambda r: (r['state'] != 'IN_PROGRESS', r['priority'], r['id']))


def latest_ref(root, development_branch):
    upstream = git(root, 'rev-parse', '--abbrev-ref', development_branch + '@{upstream}', required=False)
    remote_ref = upstream.stdout.strip() if upstream.returncode == 0 else 'origin/' + development_branch
    refs = [r for r in dict.fromkeys((development_branch, remote_ref)) if git(root, 'rev-parse', '--verify', r, required=False).returncode == 0]
    if len(refs) == 2:
        for older, newer in (refs, refs[::-1]):
            if git(root, 'merge-base', '--is-ancestor', older, newer, required=False).returncode == 0:
                return newer
        raise ValueError('Local/upstream ' + development_branch + ' diverge; inspect before trusting progress')
    return refs[0] if refs else None


def dev_ref(root, development_branch='dev'):
    return latest_ref(root, development_branch)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', choices=('plan', 'dev', 'all'))
    parser.add_argument('--brief', action='store_true')
    parser.add_argument('--open', action='store_true', help='Show unfinished work; exit 1 when any remains')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--history', action='store_true', help='Include legacy task history')
    args = parser.parse_args()
    root = Path(git(Path(__file__).resolve().parent, 'rev-parse', '--show-toplevel').stdout.strip())
    branch = git(root, 'branch', '--show-current').stdout.strip()
    config = json.loads(git(root, 'show', 'HEAD:.harness/policy.json').stdout)
    roles = {config['planning_branch']: 'plan', config['development_branch']: 'dev'}
    if branch not in roles:
        raise ValueError('Run from a configured planning or development worktree')
    role = roles[branch]
    baseline_file = config['baseline_file']
    local = Source(root)
    notices = []
    if role == 'dev':
        guard = subprocess.run([sys.executable, str(root / 'scripts/contract_guard.py'), 'check'], cwd=root,
                               text=True, capture_output=True)
        if guard.returncode:
            raise ValueError('Adopted-plan guard failed; no task selected.\n' + guard.stdout + guard.stderr)
        adopted = json.loads(local.read(baseline_file))['commit']
        notices.append('dev는 채택한 plan ' + adopted[:12] + ' 기준. 이후 plan 초안은 자동 채택하지 않음.')
        dev_source = local
    else:
        ref = dev_ref(root, config['development_branch'])
        dev_source = Source(root, ref) if ref else None
        notices.append('plan은 작업 트리의 기획 + ' + (ref or '미연결 dev') + ' 커밋의 진척을 표시. dev 미커밋 기록은 표시하지 않음.')
    intake = plan_intake.collect(local, dev_source)
    pending_intake = [r for r in intake if r['state'] in ('PENDING', 'CHANGED')]
    plan_tip = latest_ref(root, config['planning_branch']) if role == 'dev' else None
    control_sources = {'plan': local if role == 'plan' else (Source(root, plan_tip) if plan_tip else None), 'dev': dev_source}
    pauses = workflow_control.paused_sessions(control_sources)
    pending = workflow_control.pending_decisions(local, dev_source, baseline_file)
    handoffs = workflow_control.handoffs(control_sources)
    if pauses: notices.append('사용자 중지 기록이 적용됩니다. 명시적 재개 전에는 해당 역할을 선택하지 않습니다.')
    if pending: notices.append('기획 결정 대기: 분류된 작업 또는 dev 전체가 차단됩니다.')
    sources = {'plan': local, 'dev': dev_source}
    records = {o: s.records(PROGRESS[o]) if s else {} for o, s in sources.items()}
    document = json.loads(local.read(QUEUE)) if (root / QUEUE).exists() else {'schema_version': 1, 'tasks': []}
    rows = evaluate(document, records, local, sources)
    cards = plan_cards.rows(local, dev_source, rows, role, baseline_file=baseline_file)
    replacements = {r['id'] for r in cards}
    for row in rows:
        if row.get('superseded_by') and row['superseded_by'] not in replacements:
            raise ValueError('Missing replacement P-card: ' + row['id'])
    legacy = [r for r in rows if not r.get('superseded_by')]
    # Completed historical IDs remain queryable without filling the default P-number queue.
    rows = cards + [r for r in legacy if args.history or r['state'] != 'DONE' or not cards]
    rows.sort(key=lambda r: (r['state'] != 'IN_PROGRESS', r['priority'], r['id']))
    for task_owner in PROGRESS:
        if sum(r['owner'] == task_owner and r['state'] == 'IN_PROGRESS' for r in rows) > 1:
            raise ValueError('Only one active task per owner: ' + task_owner)
    owner = args.owner or role
    selected = [r for r in rows if owner == 'all' or r['owner'] == owner]
    next_tasks = workflow_control.select_next(rows, replacements,
        [o for o in PROGRESS if owner in ('all', o)], pending, pauses)
    output = {'branch': branch, 'owner': owner, 'notices': notices, 'next': next_tasks,
              'tasks': [r for r in selected if not args.open or r['state'] != 'DONE'],
              'plan_requests': intake, 'pending_decisions': pending, 'paused_sessions': pauses, 'handoffs': handoffs}
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print('\n'.join(notices))
        for o, ident in next_tasks.items():
            print(f'{o} 다음 작업: {ident or "실행 가능한 승인 작업 없음"}')
        print(f'plan 새 요구 검토 대기: {len(pending_intake)}건 (구현 승인과 별개)')
        for item in pending_intake:
            print(f"  [{item['state']}] {item['id']} {item['title']} — {item['path']}")
        for item in pending:
            print('  결정 대기: ' + item['path'] + ' — ' + item['scope'] + ' ' + ', '.join(item['tasks']))
        for item in pauses:
            print('  사용자 중지: ' + item['role'] + ' (' + item['scope'] + ') — ' + item['path'])
        if not args.brief:
            for row in output['tasks']:
                label = {'DRAFT': '기획 중', 'READY': '준비 완료', 'WAITING': '선행 대기', 'IN_PROGRESS': '개발 중', 'BLOCKED': '차단', 'DONE': '완료'}[row['state']]
                print(f"[{label}] {row['id']} {row['title']} — {row['checked']}/{row['total']} ({row['owner']})")
                if row['reason']:
                    print('  ' + row['reason'])
            for ident in filter(None, next_tasks.values()):
                task = next(r for r in rows if r['id'] == ident)
                print('\n작업서: ' + task['work_order'])
                for key, value in task['acceptance'].items():
                    mark = 'x' if key in task.get('completed_checks', []) else ' '
                    print(f'  [{mark}] {key}: {value}')
        print('조회 전용 · 자동 실행/승인/병합/네트워크 접근 없음')
    return 1 if args.open and (any(r['state'] != 'DONE' for r in selected)
                              or pending or pauses or (owner in ('plan', 'all') and pending_intake)) else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('QUEUE ERROR: ' + str(error), file=sys.stderr)
        sys.exit(2)
