# Harness 0.2.1 maintenance verification

Verified 2026-11-04T12:03:47+09:00.
Exact reviewed maintenance: e019a35a2ad9c671167d2adad54c4890a8c02f99.
Baseline parent: e065560e3a48a6a4a1d41c26a721ee2a99521dce.
Dev adoption: 35427012a324905dc9b9f3f0323320bccff2d6c7.
Review: docs/process/harness-0.2.1-review.md.

Manual integration of source 0.2.1 is recorded in .harness/manual-upgrade.json;
all provenance hashes match actual files. No installer-managed manifest was invented.
Plan/dev guards passed for worktree, index and HEAD. Existing task states, next
selections and decision/pause lists matched pre-upgrade observations. All original
tracked content outside the reviewed maintenance allowlist and dev adoption was
unchanged. Existing dirty work, product cards/logs/evidence, one-shot records,
main/FE/backup/stash refs, hooks, Git configuration and remotes were preserved.
Outer entrypoints match the tracked reconstruction document.

The dev adopted only the maintenance SHA, excluding the newer plan integration tip.
No product queue, model/DB/service action or pause resumption was performed.
Isolated runtime regression: 67 passed in the full suite, then the one case with
an omitted reference-document fixture passed in a focused rerun (68 latest case
results). Earlier fixture-setup failures remain in the private audit; this is not
a claim of a single clean full-suite run. Actual-history merge/adoption rehearsals
and legacy-control/approval negative checks passed. Project-specific guards and
timestamp rules were retained; fresh model compliance is not proven by these tests.

This commit records local verification. Remote plan/dev delivery is separately
verified by the coordinating upgrade audit after normal push; no main promotion.
