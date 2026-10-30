# P018 S1 verification

Status: **S1_PROPOSAL_VALIDATED_WAITING_PLAN_DEPLOYMENT**. P018 is IN_PROGRESS,
0/4 criteria checked. No protected runtime/test deployment has occurred.

Adopted plan: `405cae9d23ea836bfa67f504e8a8ae423f96ef54`.
Adoption commit: `7d3abc591c70d377f1842a298c7ba858e77565be`.
Source: plan-dev-harness v0.1.0 `803d658a8c61dc6aa007645a98d4160b16746faa`.
Candidate bytes and hashes: `docs/feedback/dev/p018/manifest.json`.

## Actual results (Python 3.9.6)

| Run | Result | Meaning |
| --- | --- | --- |
| Unchanged HR intake suite | 12/12 PASS | Existing intake baseline |
| New regression suite on unchanged runtime | 20 PASS, 3 expected failures | Reproduces two Z parser errors and Z completion rejected by real hook |
| Same regression suite on candidate | 23/23 PASS | Includes 12 existing HR intake cases, 6 timestamp cases, 5 Git governance cases |
| Fixed release bundled tests | 51/51 PASS | Release fixtures only; not HR product tests |

The baseline failure transcript is retained in `baseline-regression.log`; it is
not a failed candidate run. Candidate fixes resolve all three cases, and +09:00
acceptance and timezone-naive rejection remain. No broader timestamp grammar or
product behavior is claimed. Test logs, interpreter versions, exit codes and
elapsed times are in `test-results.json` and the corresponding log files.

Current HR intake tests verify exact adoption, stale review handling, immutable
requests, plan/dev ownership, and unchanged adopted baselines when plan advances.
Additional real disposable Git tests reject protected runtime edits, fabricated
completion, committed log rewrites, and a checked criterion whose latest result
is FAIL. The queue reads committed dev completion from plan without merging back.
All those negative cases assert the expected rejection, not merely a failed exit.

## Preservation and guard evidence

`preservation-before.json` records SHA-256 for all 2,145 pre-existing tracked files
except P018's mutable state/log, all four specified dirty plan files, and the
ignored runtime budget ledger. `preservation-after.json` confirms no differences.
The ignored ledger baseline was taken during fixture tests; no product/model/server
command was run during S1. No live protected file, source PDF, product result,
P001–P017 card/log, hook setting, or installation manifest was changed.

`guard-before-stage.log` records worktree/index/HEAD checks against the exact
adopted plan. `s1-queue.json` shows P018 IN_PROGRESS, 0/4, and no pending intake.
A later `guard-staged.log` checks the complete proposed commit's index as well.
Hooks remain executable with `core.hooksPath=.githooks`.

All test repositories are disposable. The upstream suite's deliberate bypass
simulation is confined to a test fixture to verify pre-push enforcement. No live
HR hook is bypassed; new HR fixtures bootstrap before activating hooks. Release
packaging/bootstrap tests write only inside their temporary directories, not to
global skills or real worktrees.

## Remaining work

Plan must review the committed candidate, deploy approved protected files/tests,
and hand off an exact new SHA. S2 must adopt it, repeat the final checks, synchronize
the local workspace entrypoint, and record final delivery. S1 does not satisfy the
full C1–C4 completion conditions. The unchanged legacy installer conflict and the
HR-specific intake example are preserved; no installer-managed upgrade is claimed.
