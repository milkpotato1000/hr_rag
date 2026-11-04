#!/usr/bin/env python3
"""Durable queue controls and handoffs. Never sends messages or starts work."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import uuid

DECISIONS = 'docs/feedback/dev'
SCOPES = 'docs/planning/decision-scopes'
SESSIONS = 'docs/progress/sessions'
HANDOFFS = 'docs/progress/handoffs'
DECISION = re.compile(r'docs/feedback/dev/(P[0-9]{3,})-decision-[A-Za-z0-9_-]+\.md\Z')
SHA = re.compile(r'[0-9a-f]{40}\Z')
KINDS = ('DECISION_REQUEST', 'DECISION_READY', 'WORK_READY', 'STOP', 'RESUME')
STATES = ('PENDING', 'SENT', 'ACKNOWLEDGED')


def now():
    return datetime.now(timezone.utc).isoformat()


def require(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Nonempty ' + name + ' required')
    return value


def field(text, name):
    values = re.findall(r'^> ' + re.escape(name) + r': (.*)$', text, re.M)
    if len(values) != 1 or not values[0].strip():
        raise ValueError('Missing/duplicate control field: ' + name)
    return values[0]


def replace_field(text, name, value):
    if '\n' in value or '\r' in value:
        raise ValueError('Control fields must be single-line')
    field(text, name)
    return re.sub(r'^> ' + re.escape(name) + r': .*$', lambda _: '> ' + name + ': ' + value, text, flags=re.M)


def fingerprint(text):
    # Execution status/resolution may change; question/impact must stay identical.
    body = re.sub(r'^> (상태|결정 plan): .*\n?', '', text, flags=re.M)
    return hashlib.sha256(body.encode()).hexdigest()


def decision_paths(source):
    if source is None:
        return []
    paths = []
    for path in sorted(source.paths(DECISIONS)):
        if PurePosixPath(path).parent != PurePosixPath(DECISIONS):
            continue
        if DECISION.fullmatch(path) or '> 유형: PLAN_DECISION' in source.read(path):
            paths.append(path)
    return paths


def pending_decisions(plan_source, dev_source, baseline_file):
    from work_queue import git
    pending = []
    scopes = plan_source.records(SCOPES)
    for path in decision_paths(dev_source):
        match = DECISION.fullmatch(path)
        if not match:
            raise ValueError('Invalid decision filename: ' + path)
        text = dev_source.read(path)
        if field(text, '유형') != 'PLAN_DECISION' or field(text, '작업') != match[1]:
            raise ValueError('Decision type/task mismatch: ' + path)
        state, resolution = field(text, '상태'), field(text, '결정 plan')
        if state == 'RESOLVED':
            if not SHA.fullmatch(resolution):
                raise ValueError('Resolution requires full plan SHA: ' + path)
            adopted = json.loads(dev_source.read(baseline_file))['commit']
            if not SHA.fullmatch(adopted) or git(dev_source.root, 'merge-base', '--is-ancestor', resolution, adopted, required=False).returncode:
                raise ValueError('Adopt the decision plan before resolving: ' + path)
        elif state == 'OPEN':
            if resolution != '-':
                raise ValueError('OPEN decision must not claim resolution: ' + path)
            item = dict(path=path, task=match[1], scope='all', tasks=[], reason='Impact not classified by plan')
            classification = scopes.get(PurePosixPath(path).stem)
            if classification is not None:
                if (classification.get('schema_version') != 1 or classification.get('request') != path
                        or classification.get('request_sha256') != fingerprint(text)):
                    raise ValueError('Stale/invalid decision classification; review in plan: ' + path)
                scope, tasks = classification.get('scope'), classification.get('tasks')
                if (scope not in ('all', 'tasks') or not isinstance(tasks, list)
                        or any(not isinstance(t, str) or not re.fullmatch(r'P[0-9]{3,}', t) for t in tasks)
                        or len(set(tasks)) != len(tasks) or (scope == 'tasks' and match[1] not in tasks)
                        or (scope == 'all' and tasks)):
                    raise ValueError('Invalid decision scope: ' + path)
                item.update(scope=scope, tasks=tasks, reason=require(classification.get('reason'), 'scope reason'))
                require(classification.get('review_reference'), 'plan review reference')
            pending.append(item)
        else:
            raise ValueError('Decision state must be OPEN/RESOLVED: ' + path)
    return pending


def checkpoint(text, role):
    state = field(text, '상태')
    if field(text, '역할') != role or state not in ('PAUSED', 'ACTIVE'):
        raise ValueError('Invalid checkpoint role/state')
    request, resume = field(text, '사용자 요청'), field(text, '재개 요청')
    if request == '-' or (state == 'ACTIVE' and resume == '-'):
        raise ValueError('Explicit user pause/resume reference required')
    # Legacy checkpoints without scope mean stop both roles.
    scope = field(text, '범위') if re.search(r'^> 범위:', text, re.M) else 'all'
    if scope not in ('all', 'role'):
        raise ValueError('Checkpoint scope must be all/role')
    return dict(role=role, state=state, scope=scope, request=request, resume=resume)


def paused_sessions(sources):
    pauses = []
    for role, source in sources.items():
        path = SESSIONS + '/' + role + '.md'
        if source and path in source.paths(SESSIONS):
            item = checkpoint(source.read(path), role)
            if item['state'] == 'PAUSED':
                pauses.append(dict(item, path=path))
    return pauses


def select_next(rows, replacements, owners, pending, pauses):
    known = {r['id'] for r in rows}
    blocked = {}
    for decision in pending:
        targets = set(decision['tasks']) if decision['scope'] == 'tasks' else known.copy()
        if targets - known:
            raise ValueError('Decision scope references unknown tasks: ' + ', '.join(sorted(targets - known)))
        while True:
            more = {r['id'] for r in rows if set(r.get('depends_on', [])) & targets}
            if more <= targets:
                break
            targets |= more
        for ident in targets:
            blocked.setdefault(ident, []).append(decision['path'])
    next_tasks = {}
    for owner in owners:
        stopped = any(p['scope'] == 'all' or p['role'] == owner for p in pauses)
        next_tasks[owner] = None if stopped else next((r['id'] for r in rows if r['owner'] == owner
            and not (owner == 'dev' and r['id'] in blocked)
            and (r['state'] in ('IN_PROGRESS', 'READY') or
                 (owner == 'plan' and r['id'] in replacements and r['state'] == 'DRAFT'))), None)
    for row in rows:
        row['blocked_by_decisions'] = blocked.get(row['id'], []) if row['owner'] == 'dev' else []
    return next_tasks


def event_key(kind, target, commit, document):
    return hashlib.sha256(json.dumps([kind, target, commit, document], separators=(',', ':')).encode()).hexdigest()


def handoff(record, ident, source):
    from work_queue import git, safe_path
    if not isinstance(record, dict) or record.get('schema_version') != 1:
        raise ValueError('Invalid handoff schema')
    for key in ('kind', 'target_role', 'source_role', 'commit', 'document', 'summary', 'next_action', 'status'):
        require(record.get(key), 'handoff ' + key)
    if (record['kind'] not in KINDS or record['target_role'] not in ('plan', 'dev')
            or record['source_role'] not in ('plan', 'dev') or record['source_role'] == record['target_role']
            or not SHA.fullmatch(record['commit']) or record['status'] not in STATES):
        raise ValueError('Invalid handoff fields')
    safe_path(record['document'])
    if ident != event_key(record['kind'], record['target_role'], record['commit'], record['document']):
        raise ValueError('Handoff event key mismatch')
    # Evidence must name an actual committed document, not a working-tree draft.
    if not git(source.root, 'show', record['commit'] + ':' + record['document']).stdout.strip():
        raise ValueError('Handoff document must be committed and nonempty')
    history = record.get('history')
    if not isinstance(history, list) or len(history) != STATES.index(record['status']) + 1:
        raise ValueError('Invalid handoff history')
    for index, event in enumerate(history):
        if not isinstance(event, dict) or event.get('status') != STATES[index]:
            raise ValueError('Handoff transitions must be PENDING -> SENT -> ACKNOWLEDGED')
        require(event.get('at'), 'event timestamp')
        if datetime.fromisoformat(event['at'].replace('Z', '+00:00')).tzinfo is None:
            raise ValueError('Event timestamp requires timezone')
        require(event.get('evidence'), 'delivery/receipt evidence')
    return record


def handoffs(sources):
    found = {}
    for role, source in sources.items():
        if source:
            directory = HANDOFFS + '/' + role
            for ident, record in source.records(directory).items():
                item = handoff(record, ident, source)
                if item['source_role'] != role:
                    raise ValueError('Handoff owner mismatch')
                found[ident] = dict(item, id=ident, path=directory + '/' + ident + '.json')
    return list(found.values())


def validate_changes(current, previous, config):
    """Dev guard: checkpoint commits remain allowed; silently erasing stops does not."""
    pending_decisions(current, current, config['baseline_file'])
    paused_sessions({'plan': current, 'dev': current})
    handoffs({'plan': current, 'dev': current})
    if previous is None:
        return
    for path in decision_paths(previous):
        if path not in decision_paths(current):
            raise ValueError('Preserve decision records; resolve with adopted plan: ' + path)
        if fingerprint(previous.read(path)) != fingerprint(current.read(path)):
            raise ValueError('Decision question is immutable; create a follow-up: ' + path)
    validate_role_changes(current, previous, 'dev')


def validate_role_changes(current, previous, role):
    path = SESSIONS + '/' + role + '.md'
    if path in current.paths(SESSIONS):
        checkpoint(current.read(path), role)
    handoffs({role: current})
    if previous is None:
        return
    if path in previous.paths(SESSIONS):
        if path not in current.paths(SESSIONS):
            raise ValueError('Preserve checkpoint; record explicit resume')
        before, after = checkpoint(previous.read(path), role), checkpoint(current.read(path), role)
        history = lambda text: re.findall(r'^- .+ \| (?:PAUSE|RESUME) \| .+$', text, re.M)
        old_history, new_history = history(previous.read(path)), history(current.read(path))
        if new_history[:len(old_history)] != old_history:
            raise ValueError('Checkpoint event history is append-only')
        if (before['state'], before['scope']) != (after['state'], after['scope']):
            key = 'resume' if after['state'] == 'ACTIVE' else 'request'
            if before[key] == after[key] or after[key] == '-':
                raise ValueError('New user reference required for checkpoint transition')
    directory = HANDOFFS + '/' + role
    old, new = previous.records(directory), current.records(directory)
    for ident, before in old.items():
        if ident not in new:
            raise ValueError('Preserve handoff history')
        after = new[ident]
        if (any(after.get(k) != v for k, v in before.items() if k not in ('status', 'history'))
                or after['history'][:len(before['history'])] != before['history']):
            raise ValueError('Handoff content/history is immutable')


def write(path, text, create=False):
    path = Path(path)
    if not path.resolve().is_relative_to(Path.cwd().resolve()) or path.is_symlink():
        raise ValueError('Control path escapes repository or is a symlink')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x' if create else 'w', encoding='utf-8') as stream:
        stream.write(text)


def main():
    from work_queue import Source, git, dev_ref
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    req = sub.add_parser('decision'); req.add_argument('--task', required=True); req.add_argument('--question-file', required=True)
    classify = sub.add_parser('classify'); classify.add_argument('path'); classify.add_argument('--scope', choices=('all', 'tasks'), required=True)
    classify.add_argument('--tasks', nargs='*', default=[]); classify.add_argument('--reason', required=True); classify.add_argument('--review-reference', required=True)
    resolve = sub.add_parser('resolve'); resolve.add_argument('path'); resolve.add_argument('--plan-commit', required=True)
    for action in ('pause', 'resume'):
        command = sub.add_parser(action); command.add_argument('--request', required=True)
        if action == 'pause': command.add_argument('--scope', choices=('all', 'role'), default='all')
    new = sub.add_parser('handoff'); new.add_argument('--kind', choices=KINDS, required=True)
    new.add_argument('--target-role', choices=('plan', 'dev'), required=True); new.add_argument('--commit', required=True)
    new.add_argument('--document', required=True); new.add_argument('--summary', required=True); new.add_argument('--next-action', required=True)
    update = sub.add_parser('handoff-status'); update.add_argument('id'); update.add_argument('--status', choices=STATES[1:], required=True)
    update.add_argument('--evidence', required=True)
    a = p.parse_args()
    root = Path(git(Path(__file__).resolve().parent, 'rev-parse', '--show-toplevel').stdout.strip())
    import os
    os.chdir(root)
    config = json.loads(git(root, 'show', 'HEAD:.harness/policy.json').stdout)
    role = {config['planning_branch']: 'plan', config['development_branch']: 'dev'}.get(git(root, 'branch', '--show-current').stdout.strip())
    if role is None: raise ValueError('Run from configured plan/dev worktree')
    local = Source(root)
    if a.command == 'decision':
        if role != 'dev' or not re.fullmatch(r'P[0-9]{3,}', a.task): raise ValueError('Dev decision requires a P-card ID')
        local.read('docs/planning/plans/' + a.task + '.md')
        question = require(Path(a.question_file).read_text(), 'question/impact')
        path = DECISIONS + '/' + a.task + '-decision-' + uuid.uuid4().hex[:12] + '.md'
        text = '# Decision request\n\n> 유형: PLAN_DECISION\n> 상태: OPEN\n> 작업: ' + a.task + '\n> 결정 plan: -\n\n' + question + '\n'
        # Do not permit the question to inject duplicate protocol fields.
        for key in ('유형', '상태', '작업', '결정 plan'): field(text, key)
        write(path, text, create=True)
    elif a.command == 'classify':
        if role != 'plan' or not DECISION.fullmatch(a.path): raise ValueError('Only plan classifies decision scope')
        ref = dev_ref(root, config['development_branch'])
        if not ref: raise ValueError('Committed dev request required')
        dev = Source(root, ref); text = dev.read(a.path)
        value = dict(schema_version=1, request=a.path, request_sha256=fingerprint(text), scope=a.scope,
                     tasks=a.tasks, reason=a.reason, review_reference=a.review_reference)
        path = SCOPES + '/' + PurePosixPath(a.path).stem + '.json'
        class Preview(Source):
            def records(self, directory):
                records = super().records(directory)
                if directory == SCOPES: records[PurePosixPath(a.path).stem] = value
                return records
        if field(text, '상태') != 'OPEN': raise ValueError('Classify an OPEN request')
        pending_decisions(Preview(root), dev, config['baseline_file'])
        for task in a.tasks: local.read('docs/planning/plans/' + task + '.md')
        write(path, json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    elif a.command == 'resolve':
        if role != 'dev' or not DECISION.fullmatch(a.path) or not SHA.fullmatch(a.plan_commit): raise ValueError('Dev resolution requires full plan SHA')
        path = a.path; text = local.read(path)
        adopted = json.loads(local.read(config['baseline_file']))['commit']
        if git(root, 'merge-base', '--is-ancestor', a.plan_commit, adopted, required=False).returncode: raise ValueError('Adopt decision plan before resolution')
        text = replace_field(replace_field(text, '상태', 'RESOLVED'), '결정 plan', a.plan_commit)
        write(path, text)
    elif a.command in ('pause', 'resume'):
        require(a.request, 'user request reference')
        if a.request.strip() == '-' or '\n' in a.request or '\r' in a.request: raise ValueError('Single-line actual user reference required')
        path = SESSIONS + '/' + role + '.md'; old = Path(path).read_text() if Path(path).exists() else None
        if a.command == 'resume':
            if not old or checkpoint(old, role)['state'] != 'PAUSED': raise ValueError('Only resume an existing PAUSED checkpoint')
            text = replace_field(replace_field(old, '상태', 'ACTIVE'), '재개 요청', a.request)
        else:
            if old:
                checkpoint(old, role)
                text = replace_field(replace_field(replace_field(old, '상태', 'PAUSED'), '사용자 요청', a.request), '재개 요청', '-')
                text = replace_field(text, '범위', a.scope) if re.search(r'^> 범위:', text, re.M) else text + '\n> 범위: ' + a.scope + '\n'
            else:
                text = '# Session checkpoint\n\n> 역할: ' + role + '\n> 상태: PAUSED\n> 범위: ' + a.scope + '\n> 사용자 요청: ' + a.request + '\n> 재개 요청: -\n'
        text += '\n- ' + now() + ' | ' + a.command.upper() + ' | ' + a.request + '\n'
        checkpoint(text, role); write(path, text)
    elif a.command == 'handoff':
        ident = event_key(a.kind, a.target_role, a.commit, a.document)
        path = HANDOFFS + '/' + role + '/' + ident + '.json'
        value = dict(schema_version=1, kind=a.kind, target_role=a.target_role, source_role=role,
                     commit=a.commit, document=a.document, summary=a.summary, next_action=a.next_action,
                     status='PENDING', history=[dict(status='PENDING', at=now(), evidence='Created locally; not sent')])
        handoff(value, ident, local)
        if git(root, 'merge-base', '--is-ancestor', a.commit, 'HEAD', required=False).returncode: raise ValueError('Handoff commit must be integrated in current history')
        if Path(path).exists():
            existing = handoff(json.loads(Path(path).read_text()), ident, local)
            if any(existing[k] != v for k, v in value.items() if k not in ('status', 'history')): raise ValueError('Existing event differs; preserve it')
            print('KEEP', path); return
        write(path, json.dumps(value, indent=2, ensure_ascii=False) + '\n', create=True)
    else:
        if not re.fullmatch(r'[0-9a-f]{64}', a.id): raise ValueError('Invalid event ID')
        path = HANDOFFS + '/' + role + '/' + a.id + '.json'
        value = handoff(json.loads(local.read(path)), a.id, local)
        if STATES.index(a.status) != STATES.index(value['status']) + 1: raise ValueError('Record the next delivery state only')
        value['status'] = a.status; value['history'].append(dict(status=a.status, at=now(), evidence=require(a.evidence, 'receipt evidence')))
        handoff(value, a.id, local); write(path, json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    print(path + ': local record only; review and commit. No message or work was executed.')


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('CONTROL ERROR:', exc, file=sys.stderr); sys.exit(2)
