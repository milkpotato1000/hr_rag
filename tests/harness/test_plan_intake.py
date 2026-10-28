"""Exercise intake ownership and visibility with real temporary Git snapshots/hooks."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class IntakeTests(unittest.TestCase):
    def run_cmd(self, *args, ok=True):
        result = subprocess.run(args, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def git(self, *args, **kw):
        return self.run_cmd('git', *args, **kw)

    def cli(self, *args, **kw):
        return self.run_cmd(sys.executable, 'scripts/plan_intake.py', *args, **kw)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hr-rag-intake-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-b', 'plan')
        self.git('config', 'user.name', 'Harness fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        # Fixture bootstrap precedes activation; no project hook is disabled.
        self.git('config', 'core.hooksPath', '.githooks')
        shutil.copytree(ROOT / 'scripts', self.root / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT / '.harness', self.root / '.harness')
        card = self.root / 'docs/planning/plans/P001.md'
        card.parent.mkdir(parents=True)
        card.write_text('''# P001 — Fixture draft

> 준비: 초안
> 실행: 미착수
> 우선순위: 1
> 선행: 없음
> 승인 근거: fixture

<!-- CHECKLIST:START -->
- [ ] C1: Verify fixture.
<!-- CHECKLIST:END -->
<!-- EXECUTION:START -->
<!-- EXECUTION:END -->
''')
        self.git('add', '.')
        self.git('commit', '-m', 'Fixture plan')
        self.base = self.git('rev-parse', 'HEAD').stdout.strip()
        shutil.copytree(ROOT / '.githooks', self.root / '.githooks')
        self.git('add', '.githooks')
        self.git('commit', '-m', 'Activate fixture hooks')
        self.base = self.git('rev-parse', 'HEAD').stdout.strip()
        self.git('checkout', '-b', 'dev')
        self.run_cmd(sys.executable, 'scripts/contract_guard.py', 'adopt', self.base,
                     '--review-reference', 'Fixture reviewed adoption')
        self.git('add', '.harness/adopted-plan.json')
        self.git('commit', '-m', 'Adopt fixture')
        self.body = self.root / 'request.txt'
        self.body.write_text('New PDF corpus requirement')

    def capture(self, commit=True):
        self.cli('request', '--title', 'PDF corpus', '--request-file', str(self.body),
                 '--source', 'User fixture request', '--impact', 'New corpus scope')
        path = next((self.root / 'docs/feedback/dev/requests').glob('*.json'))
        if commit:
            self.git('add', str(path.relative_to(self.root)))
            self.git('commit', '-m', 'Capture request')
        return path.stem

    def queue(self):
        return json.loads(self.run_cmd(sys.executable, 'scripts/work_queue.py', '--owner', 'all', '--json').stdout)

    def review(self, ident, **kw):
        return self.cli('review', ident, '--disposition', 'linked', '--cards', 'P001',
                        '--reason', 'Needs new contract', '--review-reference', 'Fixture review', **kw)

    def test_committed_request_visible_to_plan_without_merging_dev(self):
        ident = self.capture()
        self.git('checkout', 'plan')
        before = self.git('rev-parse', 'HEAD').stdout
        result = self.queue()
        self.assertEqual(result['plan_requests'][0]['id'], ident)
        self.assertEqual(result['plan_requests'][0]['state'], 'PENDING')
        self.assertEqual(before, self.git('rev-parse', 'HEAD').stdout)
        self.assertEqual(result['next']['dev'], None)

    def test_uncommitted_request_not_reported_as_plan_handoff(self):
        self.capture(commit=False)
        self.assertEqual(self.queue()['plan_requests'][0]['state'], 'PENDING')
        self.git('checkout', 'plan')
        self.assertEqual(self.queue()['plan_requests'], [])

    def test_dev_cannot_review_or_forge_decision(self):
        ident = self.capture()
        self.review(ident, ok=False)
        target = self.root / 'docs/planning/request-decisions' / (ident + '.json')
        target.parent.mkdir(parents=True)
        target.write_text('{}')
        self.git('add', str(target.relative_to(self.root)))
        result = self.git('commit', '-m', 'Forge approval', ok=False)
        self.assertIn('Protected files differ', result.stderr)

    def test_linking_draft_does_not_approve_execution(self):
        ident = self.capture()
        self.git('checkout', 'plan')
        self.review(ident)
        result = self.queue()
        self.assertEqual(result['plan_requests'][0]['state'], 'LINKED')
        self.assertEqual(result['tasks'][0]['state'], 'DRAFT')
        self.assertIsNone(result['next']['dev'])

    def test_missing_card_rejected_before_writing_decision(self):
        ident = self.capture()
        self.git('checkout', 'plan')
        self.cli('review', ident, '--disposition', 'linked', '--cards', 'P999',
                 '--reason', 'Missing', '--review-reference', 'Fixture', ok=False)
        self.assertFalse((self.root / 'docs/planning/request-decisions').exists())

    def test_request_edit_and_delete_rejected_in_index(self):
        ident = self.capture()
        path = self.root / 'docs/feedback/dev/requests' / (ident + '.json')
        original = path.read_text()
        path.write_text(original.replace('New PDF', 'Changed PDF'))
        self.git('add', str(path.relative_to(self.root)))
        self.git('commit', '-m', 'Edit old request', ok=False)
        path.write_text(original)
        self.git('add', str(path.relative_to(self.root)))
        self.git('rm', str(path.relative_to(self.root)))
        self.git('commit', '-m', 'Remove old request', ok=False)

    def test_stale_review_hash_reappears_pending(self):
        ident = self.capture()
        self.git('checkout', 'plan')
        self.review(ident)
        path = self.root / 'docs/planning/request-decisions' / (ident + '.json')
        item = json.loads(path.read_text())
        item['request_sha256'] = '0' * 64
        path.write_text(json.dumps(item))
        self.assertEqual(self.queue()['plan_requests'][0]['state'], 'CHANGED')

    def test_plan_decision_requires_exact_adoption_on_dev(self):
        ident = self.capture()
        self.git('checkout', 'plan')
        self.review(ident)
        self.git('add', 'docs/planning/request-decisions')
        self.git('commit', '-m', 'Review request')
        plan = self.git('rev-parse', 'HEAD').stdout.strip()
        self.git('checkout', 'dev')
        self.assertEqual(self.queue()['plan_requests'][0]['state'], 'PENDING')
        self.git('merge', '--no-commit', '--no-ff', 'plan')
        self.run_cmd(sys.executable, 'scripts/contract_guard.py', 'check', ok=False)
        self.run_cmd(sys.executable, 'scripts/contract_guard.py', 'adopt', plan,
                     '--review-reference', 'Fixture decision and draft preserved')
        self.git('add', '.harness/adopted-plan.json')
        self.git('commit', '-m', 'Adopt reviewed decision')
        self.assertEqual(self.queue()['plan_requests'][0]['state'], 'LINKED')
        self.assertIsNone(self.queue()['next']['dev'])

    def test_invalid_request_rejected_by_hook(self):
        folder = self.root / 'docs/feedback/dev/requests'
        folder.mkdir(parents=True)
        (folder / 'R20261028-1234abcd.json').write_text('{}')
        self.git('add', str(folder.relative_to(self.root)))
        self.git('commit', '-m', 'Invalid intake', ok=False)

    def test_pending_request_does_not_block_unrelated_dev_record(self):
        self.capture()
        path = self.root / 'docs/progress/existing-contract.md'
        path.parent.mkdir(parents=True)
        path.write_text('Verification of existing contract, no new scope')
        self.git('add', str(path.relative_to(self.root)))
        self.git('commit', '-m', 'Existing scoped verification')
        self.run_cmd(sys.executable, 'scripts/contract_guard.py', 'check', '--target', 'HEAD')

    def test_plan_advance_does_not_invalidate_old_dev_adoption(self):
        self.capture()
        self.git('checkout', 'plan')
        path = self.root / 'docs/planning/future.md'
        path.write_text('New proposal awaiting review')
        self.git('add', str(path.relative_to(self.root)))
        self.git('commit', '-m', 'Advance plan')
        self.git('checkout', 'dev')
        self.run_cmd(sys.executable, 'scripts/contract_guard.py', 'check', '--target', 'HEAD')

    def test_plan_cannot_capture_dev_request(self):
        self.git('checkout', 'plan')
        self.cli('request', '--title', 'Wrong role', '--request-file', str(self.body),
                 '--source', 'Fixture', '--impact', 'Fixture', ok=False)


if __name__ == '__main__':
    unittest.main()
