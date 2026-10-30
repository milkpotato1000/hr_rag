#!/usr/bin/env python3
"""Dev request capture and plan-owned triage; never approves or runs product work."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid

import plan_cards

REQUESTS = 'docs/feedback/dev/requests'
DECISIONS = 'docs/planning/request-decisions'
IDENT = re.compile(r'R[0-9]{8}-[0-9a-f]{8}\Z')
DISPOSITIONS = ('linked', 'covered', 'deferred', 'rejected')


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def required_text(record, keys):
    if not isinstance(record, dict):
        raise ValueError('Intake record must be an object')
    if any(not isinstance(record.get(k), str) or not record[k].strip() for k in keys):
        raise ValueError('Intake record requires nonempty text: ' + ', '.join(keys))


def request(text, ident):
    item = json.loads(text)
    if not isinstance(item, dict):
        raise ValueError('Intake request must be an object')
    if not IDENT.fullmatch(ident) or item.get('id') != ident or item.get('schema_version') != 1:
        raise ValueError('Invalid intake request ID/schema: ' + ident)
    required_text(item, ('title', 'request', 'source', 'impact', 'created_at'))
    if datetime.fromisoformat(item['created_at'].replace('Z', '+00:00')).tzinfo is None:
        raise ValueError('Request timestamp requires timezone')
    return item


def collect(plan_source, dev_source):
    if dev_source is None:
        return []
    requests = dev_source.records(REQUESTS)
    decisions = plan_source.records(DECISIONS)
    if set(decisions) - set(requests):
        raise ValueError('Plan decision has no visible dev request; sync dev before review')
    rows = []
    for ident in sorted(requests):
        path = f'{REQUESTS}/{ident}.json'
        raw = dev_source.read(path)
        item = request(raw, ident)
        row = dict(id=ident, title=item['title'], path=path, request_sha256=digest(raw),
                   state='PENDING', cards=[], reason='plan 검토 필요')
        if ident in decisions:
            decision = decisions[ident]
            required_text(decision, ('request_sha256', 'reason', 'review_reference'))
            disposition = decision.get('disposition')
            cards = decision.get('cards')
            if (decision.get('schema_version') != 1 or decision.get('id') != ident
                    or disposition not in DISPOSITIONS or not isinstance(cards, list)
                    or any(not isinstance(c, str) or not re.fullmatch(r'P[0-9]{3,}', c) for c in cards)
                    or len(set(cards)) != len(cards)
                    or (disposition in ('linked', 'covered') and not cards)
                    or not re.fullmatch(r'[0-9a-f]{64}', decision['request_sha256'])):
                raise ValueError('Invalid plan intake decision: ' + ident)
            for card in cards:
                parsed = plan_cards.parse(plan_source.read(f'{plan_cards.DIRECTORY}/{card}.md'))
                if parsed['id'] != card:
                    raise ValueError('Decision P-card mismatch: ' + ident)
            row.update(cards=cards, reason=decision['reason'])
            row['state'] = disposition.upper() if decision['request_sha256'] == row['request_sha256'] else 'CHANGED'
        rows.append(row)
    return rows


def write_new(path, data):
    if not path.parent.resolve().is_relative_to(Path.cwd().resolve()):
        raise ValueError('Intake directory escapes repository')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    # Queue imports this module too; defer this CLI-only import.
    from work_queue import Source, git, dev_ref
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    new = sub.add_parser('request')
    for name in ('title', 'request-file', 'source', 'impact'):
        new.add_argument('--' + name, required=True)
    review = sub.add_parser('review')
    review.add_argument('id')
    review.add_argument('--disposition', choices=DISPOSITIONS, required=True)
    review.add_argument('--cards', nargs='*', default=[])
    review.add_argument('--reason', required=True)
    review.add_argument('--review-reference', required=True)
    sub.add_parser('list')
    args = parser.parse_args()
    root = Path(git(Path(__file__).resolve().parent, 'rev-parse', '--show-toplevel').stdout.strip())
    import os
    os.chdir(root)
    config = json.loads(git(root, 'show', 'HEAD:.harness/policy.json').stdout)
    branch = git(root, 'branch', '--show-current').stdout.strip()
    role = {config['planning_branch']: 'plan', config['development_branch']: 'dev'}.get(branch)
    if role is None:
        raise ValueError('Run intake from plan or dev')
    if args.command == 'request':
        if role != 'dev':
            raise ValueError('Capture requests only in dev; plan owns P-cards and triage')
        ident = 'R' + datetime.now(timezone.utc).strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:8]
        item = dict(schema_version=1, id=ident, title=args.title,
                    request=Path(args.request_file).read_text(), source=args.source, impact=args.impact,
                    created_at=datetime.now(timezone.utc).isoformat())
        request(json.dumps(item), ident)
        path = Path(REQUESTS) / (ident + '.json')
        write_new(path, item)
        print(f'{path}: plan 검토 대기. dev에 커밋한 뒤 plan 큐에서 확인. 구현 승인 아님.')
        return
    ref = dev_ref(root, config['development_branch'])
    dev_source = Source(root) if role == 'dev' else (Source(root, ref) if ref else None)
    plan_source = Source(root)
    rows = collect(plan_source, dev_source)
    if args.command == 'review':
        if role != 'plan':
            raise ValueError('Only plan may triage requests')
        row = next((r for r in rows if r['id'] == args.id), None)
        if row is None:
            raise ValueError('Request must be committed on dev before plan review')
        item = dict(schema_version=1, id=args.id, request_sha256=row['request_sha256'],
                    disposition=args.disposition, cards=args.cards, reason=args.reason,
                    review_reference=args.review_reference)
        # Validate before creating any file; existing decisions require explicit reviewed edits.
        class Preview:
            def records(self, directory):
                return {**plan_source.records(directory), args.id: item}
            def read(self, path):
                return plan_source.read(path)
        collect(Preview(), dev_source)
        path = Path(DECISIONS) / (args.id + '.json')
        write_new(path, item)
        print(f'{path}: P카드 준비 검토·정확한 채택은 별도 단계.')
        return
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('INTAKE ERROR: ' + str(error), file=sys.stderr)
        sys.exit(2)
