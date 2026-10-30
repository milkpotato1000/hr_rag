"""P018 proposal. Run after deployment at tests/harness, or in an isolated copy."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import plan_cards
import plan_intake
import test_plan_intake as intake_fixture

CARD = '''# P001 — Timestamp fixture
> 준비: 준비 완료
> 실행: 진행 중
> 우선순위: 1
> 선행: 없음
> 승인 근거: Fixture review
<!-- CHECKLIST:START -->
- [ ] C1: Verify fixture.
<!-- CHECKLIST:END -->
<!-- EXECUTION:START -->
- {stamp} | STATE | NOTE | - | Fixture started.
<!-- EXECUTION:END -->
'''


class TimestampTests(unittest.TestCase):
    def card(self, stamp):
        return plan_cards.parse(CARD.format(stamp=stamp))

    def request(self, stamp):
        ident = 'R20261030-1234abcd'
        return plan_intake.request(json.dumps(dict(
            id=ident, schema_version=1, title='Fixture', request='Fixture request',
            source='Fixture user', impact='Fixture scope', created_at=stamp)), ident)

    def test_card_z(self):
        self.assertEqual(len(self.card('2026-10-30T12:00:00Z')['events']), 1)

    def test_card_offset(self):
        self.assertEqual(len(self.card('2026-10-30T21:00:00+09:00')['events']), 1)

    def test_card_naive_rejected(self):
        with self.assertRaisesRegex(ValueError, 'timezone'):
            self.card('2026-10-30T12:00:00')

    def test_request_z(self):
        self.assertEqual(self.request('2026-10-30T12:00:00Z')['title'], 'Fixture')

    def test_request_offset(self):
        self.assertEqual(self.request('2026-10-30T21:00:00+09:00')['title'], 'Fixture')

    def test_request_naive_rejected(self):
        with self.assertRaisesRegex(ValueError, 'timezone'):
            self.request('2026-10-30T12:00:00')


class HRGuardTests(intake_fixture.IntakeTests):
    """Inherits the 12 existing intake cases against the same candidate files."""
    def ready_card(self):
        self.git('checkout', 'plan')
        path = self.root / 'docs/planning/plans/P001.md'
        text = path.read_text().replace('> 준비: 초안', '> 준비: 준비 완료')
        path.write_text(text)
        self.git('add', 'docs/planning/plans/P001.md')
        self.git('commit', '-m', 'Prepare fixture')
        sha = self.git('rev-parse', 'HEAD').stdout.strip()
        self.git('checkout', 'dev')
        self.git('merge', '--no-ff', '--no-commit', 'plan')
        self.run_cmd(sys.executable, 'scripts/contract_guard.py', 'adopt', sha,
                     '--review-reference', 'Fixture ready review')
        self.git('add', '.harness/adopted-plan.json')
        self.git('commit', '-m', 'Adopt ready fixture')
        return path, text

    def commit_card(self, path, text, ok=True):
        path.write_text(text)
        self.git('add', str(path.relative_to(self.root)))
        return self.git('commit', '-m', 'Fixture execution', ok=ok)

    def complete(self, stamp='2026-10-30T21:00:00+09:00'):
        path, text = self.ready_card()
        evidence = self.root / 'docs/verification/fixture.md'
        evidence.parent.mkdir(parents=True)
        evidence.write_text('Fixture expected equals actual.\n')
        self.git('add', str(evidence.relative_to(self.root)))
        log = f'- {stamp} | C1 | PASS | docs/verification/fixture.md | Verified.\n'
        done = text.replace('> 실행: 미착수', '> 실행: 완료').replace('- [ ] C1:', '- [x] C1:')
        done = done.replace('<!-- EXECUTION:END -->', log + '<!-- EXECUTION:END -->')
        self.commit_card(path, done)
        return path, done

    def test_dev_protected_runtime_edit_rejected(self):
        path = self.root / 'scripts/plan_cards.py'
        path.write_text(path.read_text() + '\n# Unauthorized fixture edit\n')
        self.git('add', 'scripts/plan_cards.py')
        result = self.git('commit', '-m', 'Edit protected runtime', ok=False)
        self.assertIn('Protected files differ', result.stderr)

    def test_false_completion_rejected(self):
        path, text = self.ready_card()
        bad = text.replace('> 실행: 미착수', '> 실행: 완료').replace('- [ ] C1:', '- [x] C1:')
        result = self.commit_card(path, bad, ok=False)
        self.assertIn('Execution requires a log', result.stderr)

    def test_committed_log_rewrite_rejected(self):
        path, done = self.complete()
        result = self.commit_card(path, done.replace('Verified.', 'Rewritten history.'), ok=False)
        self.assertIn('append-only', result.stderr)

    def test_latest_fail_invalidates_checked_pass(self):
        path, done = self.complete()
        fail = '- 2026-10-30T21:01:00+09:00 | C1 | FAIL | docs/verification/fixture.md | Regression.\n'
        result = self.commit_card(path, done.replace('<!-- EXECUTION:END -->', fail + '<!-- EXECUTION:END -->'), ok=False)
        self.assertIn('latest PASS', result.stderr)

    def test_plan_queue_reads_committed_dev_completion_with_z(self):
        self.complete(stamp='2026-10-30T12:00:00Z')
        self.git('checkout', 'plan')
        before = self.git('rev-parse', 'HEAD').stdout
        row = self.queue()['tasks'][0]
        self.assertEqual((row['state'], row['checked']), ('DONE', 1))
        self.assertEqual(self.git('rev-parse', 'HEAD').stdout, before)
        self.assertIn('> 실행: 미착수', (self.root / 'docs/planning/plans/P001.md').read_text())


if __name__ == '__main__':
    unittest.main()
