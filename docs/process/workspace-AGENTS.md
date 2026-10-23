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
and read its AGENTS.md. A request covering both roles proceeds plan → dev, with
readiness review, integration and exact adoption before implementation.
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
