# hr_rag workspace

Open this directory as the single Codex project. It is a workspace container;
Git commands and project scripts run inside the selected worktree.

| Directory | Branch | Responsibility |
| --- | --- | --- |
| `hr_rag_plan/` | `plan` | Requirements, contracts, P-card readiness and handoff |
| `hr_rag_dev/` | `dev` | Adopted implementation, verification and execution logs |
| `hr_rag_main/` | `main` | Release baseline; promotion requires an explicit request |

For planning requests, enter `hr_rag_plan/` and read its AGENTS.md.
For implementation, fixes, verification or “다음 큐 진행”, enter `hr_rag_dev/`
and read its AGENTS.md. Work needing both roles proceeds through the plan chat's
readiness review and committed P-card, then the separate dev chat's integration,
exact adoption and implementation. General requests to plan then proceed, start,
or continue do not authorize the plan chat to switch roles and implement.
If a missing business decision changes the scope, ask before dependent work.
Do not choose a role from the workspace root's name or run Git at this level.
Use explicit working directories; do not assume a previous shell's `cd` persists.

A chat initialized by the user as plan or dev keeps that assigned role across
turns. In a plan chat, “다음 작업” means planning in `hr_rag_plan/`; in a dev
chat it means the development queue in `hr_rag_dev/`. Do not silently switch
roles because both children are visible. The initial role instruction and later
explicit user requests determine scope; a title is only a navigation label.
Creating or bootstrapping role chats reads status/rules/queues and then waits;
it does not authorize new product work or messaging another chat.

New requirements raised in a dev chat must pass through plan before implementation.
Dev captures the request in `docs/feedback/dev/requests/` using `scripts/plan_intake.py`,
commits it, and retains its dev role. Do not enter the plan worktree to author or approve
new scope unless the user explicitly requests a role change or both-role work.
Plan triages the committed request, links a P-card, reviews readiness, and commits it;
dev then integrates and adopts the exact plan before implementing that scope.
Fixes within an adopted contract may continue with a P-card reference and verification.
Read the child's `docs/process/plan-intake.md`; queue queries show pending requests.
File-based intake does not authorize messaging another chat or automatic execution.

Within actual human authorization, plan directly sends the committed READY card,
full SHA, scope, verification and next action to the verified existing dev chat.
Do not ask repeatedly for the same authorized handoff or make the user copy it.
Record sending, observed receipt, exact adoption and completion separately.
The user's 2026-10-30 approval covers P018 delivery/start and its S1/S2 handoffs;
it is not a grant for other projects, reverse messages or all future work.
Follow the tracked docs/process/direct-handoff.md. Preserve stops and unresolved
decisions. Do not infer a role-change permission from generic progress requests.
For protected harness code, dev prepares isolated proposals/tests; plan reviews
and publishes the governed baseline; dev adopts that exact commit before applying.
Never disable guards or move to plan to approve your own implementation.

All three directories share one Git repository through linked worktrees.
Preserve existing work, P-card requirements, dev execution logs and adoption rules.
Inspect status and the current branch before changes. Never merge dev into plan
just to transfer completion marks. Honor existing remote/push authorization;
release promotion and release pushes require an explicit user request.

From this directory, inspect the queue with:

```sh
(cd hr_rag_plan && python3 scripts/work_queue.py --owner all)
(cd hr_rag_dev && python3 scripts/contract_guard.py check)
```

This local entrypoint is outside Git. Tracked instructions in each worktree must
also describe this layout so it can be recreated on another computer. The release
worktree may retain historical instructions until explicitly promoted; the path
mapping above describes the current local workspace.
