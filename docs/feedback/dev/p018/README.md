# P018 S1 — reviewed deployment proposal

Status: proposal only; live protected runtime files remain unchanged. P018 is in
progress with C1–C4 unchecked. Plan review/deployment and S2 exact adoption remain.

The adopted contract is `405cae9d23ea836bfa67f504e8a8ae423f96ef54`.
The release source is plan-dev-harness v0.1.0, peeled commit
`803d658a8c61dc6aa007645a98d4160b16746faa`. These are different repositories.

## Proposed files

- `candidate/scripts/plan_cards.py`: exact release asset bytes.
- `candidate/scripts/plan_intake.py`: exact release asset bytes.
- `candidate/tests/harness/test_timestamp_guards.py`: new HR regression tests,
  intended for `tests/harness/test_timestamp_guards.py` after plan review. It
  imports the existing HR intake fixture; that fixture is preserved unchanged.
- `runtime.patch`: only the two runtime normalization line changes.
- `manifest.json`: source/baseline/candidate hashes and adoption provenance.

Each parser converts `Z` to `+00:00` before `datetime.fromisoformat`. This fixes
Python 3.9 UTC input compatibility while retaining the timezone-required checks.
The release implementation uses `replace`, not a new strict terminal-Z parser;
this proposal preserves its exact bytes and does not broaden validation policy.

## Review and reproduction

Copy the current HR `scripts`, `.harness`, `.githooks`, and `tests/harness` into
a disposable directory. Overlay only the candidate files at their intended paths.
Run Python 3.9:

```sh
python3 -m unittest discover -s tests/harness -p test_timestamp_guards.py -v
```

The 23 tests comprise 12 inherited current HR intake regressions, six timestamp
acceptance/rejection cases, and five real Git/hook governance cases. The same
tests against unchanged HR runtime reproduce three expected Z failures. Logs
retain those failures. Tests use new temporary repositories; no actual HR branch,
adoption, hooks, product data or model is mutated by the fixtures.

The fixed release's bundled suite is separately exported with `git archive` and
run in a disposable directory. Those are upstream tests, not proof of HR product
behavior. Upstream fixtures include deliberate hook-bypass simulation to exercise
pre-push rejection; no live project hook is bypassed or disabled. The new HR tests
bootstrap before hook activation and do not bypass active fixture hooks.

## Deployment boundary

Plan should review the committed candidates and evidence, deploy only approved
protected files/tests, and supply the exact subsequent plan SHA for S2. Dev must
not copy this proposal into live protected paths before that handoff. Local
workspace AGENTS synchronization is also deferred to S2.

This is a legacy manual integration proposal, not an installer-managed upgrade.
No `.harness/installation.json` is created. Existing guard, queue, hooks, policy,
template, and the HR `/tmp/hr-rag-request.txt` documentation example are retained.
No unreleased 0.2.0 runtime, global skill update, product/model/server run, main
promotion, or reverse message to plan is included.

Verification and preserved baseline failures: `docs/verification/p018/`.
