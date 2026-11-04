# Harness 0.2.1 plan review — 2026-11-04

APPROVED by the planning owner for the user's existing-project harness upgrade
request, preserving existing work and pauses. This is infrastructure maintenance,
not product execution, new requirement approval, service publication or resumption.

Reviewed proposal manifest SHA-256: `09214f5a6ae494f6a401fd0375390338d6520b9487dc976c5083c193b8830da3`.
Maintenance parent: `e065560e3a48a6a4a1d41c26a721ee2a99521dce` (the existing dev adoption).
Changes: 15 allowlisted runtime, instruction and provenance files,
plus this review. Existing protected paths and hooks are retained. New ownership
paths only protect new controls/intake and manual integration provenance.
No installer-managed manifest is fabricated. See harness-0.2.1-integration.md.

Review performed: stock0.2.1 runtime parity; project-specific guard/parser
extensions; exact adoption and original work preservation; new-session role and
document target-ref instructions in child/outer entrypoints; no new messaging
or execution permission. The retained daily-work skill is not replaced.

Validation evidence before application: isolated actual-history plan integration
and exact dev adoption passed; task/next/control state parity and product paths
unchanged. Each proposal runtime has 68 latest passing case results:67 passed in
the full suite, one test-fixture-path error repaired and that case passed in a
focused rerun. Initial test-setup failures remain recorded; this is not a claim
of a clean single full-suite run. Shared legacy-control/ledger checks12 passed;
existing custom ledger/timestamp checks9 passed where applicable. Final text-only
clarifications were inspected separately; runtime bytes remained unchanged.

Apply only after checking current writers/refs/original file hashes and dirty
content. Merge this maintenance commit into plan without resetting other plans;
dev integrates/adopts this exact maintenance SHA, not the newer plan tip. Preserve
product cards, execution evidence, checkpoints, decisions and consumed one-shots.
Do not start the product queue. Keep main/FE/backup/stash, hooks, remotes and secrets.
Non-force pushes use existing authorized plan/dev destinations only.

After actual application, run guards for worktree/index/HEAD and compare queues,
file fingerprints and existing dirty status again. The application result is
separate evidence; these preflight tests do not claim live application or remote
publication. Model compliance in a fresh chat is not proven by these tests.
