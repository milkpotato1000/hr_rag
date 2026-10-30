# P018 S2 — final installed verification

The exact reviewed deployment `0e4cdc8fdf4196962b33a30ecd792748d39850ff`
was merged and adopted at `2cd8a2923a302da1622a7316b2cce84883bf1fe3`.
This is a **legacy manual integration** of fixed release v0.1.0
`803d658a8c61dc6aa007645a98d4160b16746faa`, not an installer-managed upgrade.

- Installed runtime bytes match the S1 candidates and fixed upstream release.
  `installation.json` records both SHA-256 hashes and the deployed test hash.
- Final installed HR regression: **23/23 PASS on Python 3.9.6**. These include
  the 12 current intake cases; they are not 35 distinct tests. Z and +09:00
  succeed, timezone-naive timestamps fail. Real Git fixtures check exact
  adoption, protected edits, append-only history, false completion, latest PASS,
  and committed dev completion visible from plan without merging back.
- S1's original three baseline Z failures and 51/51 release test results remain
  unchanged. They are historical evidence, not newly executed S2 product tests.
- Guard checks for worktree, index and HEAD pass against the S2 adoption;
  executable hooks and `.githooks` configuration remain intact.
- The workspace entrypoint now equals tracked `docs/process/workspace-AGENTS.md`.
  Its prior bytes matched the older tracked template exactly, so there were no
  separate local-only additions to lose. `workspace-entrypoint.patch` records
  the changes. **The parent AGENTS.md is outside Git and is not included in push.**
- Project `CLAUDE.md` imports `@AGENTS.md`. Tracked and local rules maintain plan
  ownership, separate dev implementation, and sending/receipt/adoption/completion
  as distinct states; P018 authorization is not broadened to unrelated work.
- All 2,142 previously tracked files outside the three authorized replacements
  (adoption record and two runtime scripts) remain byte-identical to S1 baseline.
  This includes P001–P017 history, product/raw documents, and previous evidence.
  Four dirty plan files and the ignored model budget ledger also retain hashes.
- HR's `/tmp/hr-rag-request.txt` example, custom policy, guard, queue, hooks and
  template are retained. No `.harness/installation.json` is invented. Existing
  installer collision remains the reason for reviewed manual integration.
- No product/model/server execution or restart, global skill modification,
  unreleased 0.2.0 runtime, release promotion, or main push was performed.

The evidence is committed and pushed before final P018 checklist completion.
Delivery receipt and final queue/guard evidence are recorded separately after
that commit; the S1 proposal stays as immutable review history.
