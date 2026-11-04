"""P-number work orders: immutable contracts, checked evidence, append-only execution."""
from datetime import datetime
from pathlib import PurePosixPath
import re

DIRECTORY = 'docs/planning/plans'
CARD = re.compile(r'docs/planning/plans/P[0-9]{3,}\.md\Z')
CHECK = re.compile(r'- \[([ x])\] (C[1-9][0-9]*): (.+)\Z')
STATES = {'미착수': 'READY', '진행 중': 'IN_PROGRESS', '차단': 'BLOCKED', '완료': 'DONE'}


def section(text, name):
    start, end = f'<!-- {name}:START -->\n', f'<!-- {name}:END -->'
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('Missing/duplicate P-card markers: ' + name)
    a, b = text.index(start) + len(start), text.index(end)
    if b < a:
        raise ValueError('Invalid P-card section order')
    return a, b, text[a:b]


def parse(text):
    title = re.match(r'# (P[0-9]{3,}) — (.+)\n', text)
    if not title:
        raise ValueError('Invalid P-card title')
    def field(key):
        values = re.findall(r'^> ' + key + r': (.*)$', text, re.M)
        if len(values) != 1:
            raise ValueError('Missing/duplicate P-card field: ' + key)
        return values[0]
    preparation, execution = field('준비'), field('실행')
    if preparation not in ('초안', '준비 완료') or execution not in STATES:
        raise ValueError('Invalid P-card state')
    priority = field('우선순위')
    if not priority.isdecimal():
        raise ValueError('Invalid P-card priority')
    deps = field('선행')
    deps = [] if deps == '없음' else deps.split(', ')
    if any(not re.fullmatch(r'[A-Z][A-Z0-9-]*', dep) for dep in deps) or len(set(deps)) != len(deps):
        raise ValueError('Invalid P-card dependencies')
    approval = field('승인 근거')
    if preparation == '준비 완료' and (not approval.strip() or approval.startswith('미확정')):
        raise ValueError('Prepared P-card requires approval reference')
    a, b, checklist = section(text, 'CHECKLIST')
    checks = {}
    for line in checklist.splitlines():
        match = CHECK.fullmatch(line)
        if not match or match[2] in checks:
            raise ValueError('Invalid/duplicate P-card checklist item')
        checks[match[2]] = {'checked': match[1] == 'x', 'text': match[3]}
    if not checks:
        raise ValueError('P-card requires completion criteria')
    c, d, log = section(text, 'EXECUTION')
    if c <= b:
        raise ValueError('Execution log must follow checklist')
    events = []
    for line in log.splitlines():
        fields = line.split(' | ', 4)
        if len(fields) != 5 or not fields[0].startswith('- '):
            raise ValueError('Invalid P-card log; use timestamp | criterion | result | evidence | note')
        stamp, criterion, result, evidence, note = fields
        moment = datetime.fromisoformat(stamp[2:].replace('Z', '+00:00'))
        if moment.tzinfo is None or not note.strip():
            raise ValueError('P-card log requires timezone and note')
        if criterion == 'STATE':
            if result != 'NOTE' or evidence != '-':
                raise ValueError('STATE log must use NOTE and -')
        elif criterion not in checks or result not in ('PASS', 'FAIL'):
            raise ValueError('Unknown P-card criterion/result')
        else:
            p = PurePosixPath(evidence)
            if (p.is_absolute() or '..' in p.parts or '\\' in evidence
                    or not evidence.startswith(('docs/verification/', 'docs/progress/'))):
                raise ValueError('P-card evidence must be a repository-relative verification/progress path')
        events.append(dict(criterion=criterion, result=result, evidence=evidence, note=note))
    # Only these exact characters and the bounded execution log are mutable by dev.
    contract = text[:a] + re.sub(r'(?m)^- \[[ x]\]', '- [ ]', checklist) + text[b:c] + text[d:]
    contract = re.sub(r'^> 실행: .*$', '> 실행: <DEV>', contract, flags=re.M)
    return dict(id=title[1], title=title[2], preparation=preparation, execution=execution,
                priority=int(priority), depends_on=deps, approval=approval, checks=checks,
                log=log, events=events, contract=contract)


def validate_execution(card, read):
    checked = [k for k, v in card['checks'].items() if v['checked']]
    if card['preparation'] != '준비 완료' and (card['execution'] != '미착수' or checked or card['events']):
        raise ValueError('Draft P-card cannot execute: ' + card['id'])
    if card['execution'] == '미착수' and (checked or card['events']):
        raise ValueError('Unstarted P-card has execution records: ' + card['id'])
    if card['execution'] != '미착수' and not card['events']:
        raise ValueError('Execution requires a log: ' + card['id'])
    latest = {e['criterion']: e for e in card['events']}
    for key in checked:
        event = latest.get(key)
        if not event or event['result'] != 'PASS':
            raise ValueError('Checked item lacks latest PASS evidence: ' + card['id'] + '/' + key)
        if not read(event['evidence']).strip():
            raise ValueError('Empty P-card evidence: ' + event['evidence'])
    complete = len(checked) == len(card['checks'])
    if (card['execution'] == '완료') != complete:
        raise ValueError('P-card completion state/checklist mismatch: ' + card['id'])
    if card['execution'] == '차단' and 'STATE' not in latest:
        raise ValueError('Blocked P-card requires STATE reason')


def validate_change(before, after, read, previous=None):
    base, current = parse(before), parse(after)
    if base['contract'] != current['contract']:
        raise ValueError('P-card requirement/criteria changed: ' + current['id'])
    if not current['log'].startswith(base['log']):
        raise ValueError('P-card log must be append-only')
    if previous is not None:
        prior = parse(previous)
        if prior['contract'] == current['contract'] and not current['log'].startswith(prior['log']):
            raise ValueError('P-card committed log must be append-only')
    validate_execution(current, read)
    return current


def rows(source, dev_source, legacy, branch, baseline_file='.harness/adopted-plan.json'):
    cards = {}
    for path in source.paths(DIRECTORY):
        if not CARD.fullmatch(path):
            continue
        text = source.read(path)
        card = parse(text)
        if path != DIRECTORY + '/' + card['id'] + '.md':
            raise ValueError('P-card filename/title mismatch')
        evidence_source = source
        notice = ''
        if branch == 'plan' and dev_source and path in dev_source.paths(DIRECTORY):
            dev_text = dev_source.read(path)
            actual = parse(dev_text)
            # Review against dev's adopted baseline, not the advancing plan branch.
            import json
            adopted = json.loads(dev_source.read(baseline_file))['commit']
            baseline_source = type(source)(source.root, adopted)
            validate_change(baseline_source.read(path), dev_text, dev_source.read)
            if card['contract'] == actual['contract']:
                card, evidence_source = actual, dev_source
            else:
                notice = '계획 개정: 이전 dev 진척을 승계하지 않음. 새 기준 채택·영향 검토 필요.'
        validate_execution(card, evidence_source.read)
        cards[card['id']] = {**card, 'work_order': path, 'notice': notice}
    old = {r['id']: r for r in legacy}
    result, visiting = {}, set()
    def resolve(ident):
        if ident in result:
            return result[ident]
        if ident in visiting:
            raise ValueError('P-card dependency cycle')
        visiting.add(ident)
        card = cards[ident]
        missing = []
        for dep in card['depends_on']:
            if dep in cards:
                state = resolve(dep)['state']
            elif dep in old:
                if old[dep].get('superseded_by'):
                    raise ValueError('Use replacement P-number dependency: ' + dep)
                state = old[dep]['state']
            else:
                raise ValueError('Unknown P-card dependency: ' + dep)
            if state != 'DONE':
                missing.append(dep)
        state = 'DRAFT' if card['preparation'] == '초안' else STATES[card['execution']]
        if missing and state in ('IN_PROGRESS', 'DONE'):
            raise ValueError('P-card executed before dependency completion: ' + ident)
        if missing and state == 'READY':
            state = 'WAITING'
        owner = 'plan' if state == 'DRAFT' else 'dev'
        reason = card['notice'] or ('선행 작업: ' + ', '.join(missing) if missing else '')
        if state == 'BLOCKED':
            reason = [e['note'] for e in card['events'] if e['criterion'] == 'STATE'][-1]
        result[ident] = dict(id=ident, depends_on=card['depends_on'], title=card['title'], owner=owner, priority=card['priority'],
                            state=state, reason=reason, work_order=card['work_order'],
                            checked=sum(v['checked'] for v in card['checks'].values()), total=len(card['checks']),
                            completed_checks=[k for k,v in card['checks'].items() if v['checked']],
                            acceptance={k:v['text'] for k,v in card['checks'].items()})
        visiting.remove(ident)
        return result[ident]
    for ident in cards:
        resolve(ident)
    return list(result.values())
