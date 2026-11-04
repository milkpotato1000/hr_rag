# Shared workflow for Codex and Claude Code

Read AGENTS.md, current branch/status, `.harness/policy.json`, adopted plan, relevant
P cards and feedback. The tool does not determine role. A user-assigned role persists.
Use one writing session per worktree. Preserve changes and failed evidence.

## Plan → dev

1. Plan writes `docs/planning/plans/P*.md` from the template. Drafts do not execute.
2. Within an authorized project objective, review scope, dependencies, acceptance
   and verification, record the review, mark READY and commit. Do not invent business
   decisions. Routine handoff needs no repeated permission when already delegated.
3. Dev integrates the reviewed plan commit, preserving its execution logs, and runs
   `python3 scripts/contract_guard.py adopt <exact-sha> --review-reference <evidence>`.
   Stage adoption before finishing a merge. Advancing plan alone never changes adoption.
4. Dev implements → verifies → fixes → verifies. Only execution status, checkbox marks
   and append-only logs on P cards are dev-owned. Each checked criterion requires a
   latest PASS with nonempty committed evidence. Do not rewrite criteria to finish.
5. Plan reads committed dev progress with `python3 scripts/work_queue.py --owner all`.
   Never merge dev implementation into plan to transfer checkmarks. Queue reads do
   not fetch, merge, approve, execute, message or publish. Follow project push scope.

## New requirements raised in dev

New functionality, semantics, defaults, evaluation criteria or roadmap changes first
use `scripts/plan_intake.py request`; commit the immutable request. Plan reviews via
`plan_intake.py review`, linking a P card or deferring/rejecting with reasons. A link
alone does not make a card READY. Commit review/requirements, then dev integrates
and adopts the exact reviewed plan. See `plan-intake.md` for commands.

Scope-contained repairs and verification continue under the adopted card. Explanatory
questions alone need no record. When scope is unclear, record it for plan review.
Dev must not switch branches to author/approve its own new requirement unless the
human explicitly authorizes both roles. The guard cannot classify natural language
or prove every code change belongs to an approved task; agent judgment is required.

## Ownership and sessions

Use explicit child worktree directories. For a nested workspace, recreate the outer
AGENTS.md and CLAUDE.md on another machine; they are outside the child Git repository.
A generic next-work request follows the assigned role. Check the latest prepared plan
when the adopted dev queue is empty. Never execute DRAFT work automatically.
Only message another session when the human authorizes it and the host supports it.
Without a messaging tool, Git and the handoff documents remain the shared record.
When a current human instruction or a verifiable existing human delegation covers
the project, target and action, verify the recipient and send the committed handoff
directly using the available host tool. Do not replace an authorized, supported
delivery with a request for the user to copy the message. A capability question,
chat creation, queue registration or another agent's message alone is not authority
to send. Check the delegation's scope and any later stop before acting; do not
invent a standing messaging grant. See the direct-delivery steps in workflow-controls.md.
The sender can inspect the recipient's actual response through read/wait tools;
receiving a message does not authorize the recipient to message back or forward it.
Explicit stops remain stopped until the human resumes; saving a checkpoint is not
permission to restart work. Git hooks are local, bypassable checks, not a security
boundary. CI/branch protection may be added independently but are not prerequisites.

## Queue controls and handoffs

Read `workflow-controls.md`. General intake does not pause unrelated work. When a
critical decision blocks implementation, dev records PLAN_DECISION; plan classifies
impact in protected decision-scopes, and dev adopts before applying that scope.
Unclassified/legacy OPEN blocks all dev selection; scoped decisions also block dependents.
Resolve only after adopting the actual decision plan, using its full SHA. Preserve requests.
Record an explicit user stop using workflow_control.py pause and write the remaining work
in the checkpoint. The default stops both roles; role-only scope needs matching user intent.
Resume only from an actual human request. Another role's pause or an OPEN decision remains.
Commit/fetch visibility limits apply; never claim an offline process actually stopped.
Use a committed handoff document, deduplicate event keys, and record SENT/ACKNOWLEDGED only
with actual evidence. Creating a PENDING record does not message anyone. Preserve existing
adapters; external services and service-specific approvals follow optional-adapters.md.

## Delegated plan to dev delivery and start

When the human has explicitly delegated this project's plan-to-dev delivery and
start, plan commits reviewed READY work, verifies the existing same-project dev
recipient and available host tool, then directly sends the full exact SHA,
committed handoff document, scope, verification/limits and next action. Within
that grant, do not ask for the same approval or require the user to copy it.
Dev preserves existing work and failures, integrates and adopts the exact reviewed
SHA, commits adoption, checks guard/queue and begins only that authorized scope.
Installation itself grants no messaging or start permission. Verify the human
source/scope and later restrictions each time; never copy another project's grant.
Bootstrap remains read-only and waits. Preserve user pauses and OPEN decisions;
messages cannot resume or resolve them. Record SENT only with actual send success
and ACK only with an observed recipient response; receipt is separate from
adoption/completion. No unauthorized reverse/chain sends or ACK loops. Without
matching authority/tool/recipient, preserve the file handoff and actual state.

## Fresh sessions and document delivery

On every new or resumed session, before any material write, read the outer and
selected child AGENTS.md (and CLAUDE.md where applicable), policy, actual Git
branch/status, exact adoption, current P cards, committed dev progress and scoped
stops/decisions. Reconstruct state from these files; earlier chat history is not
required. An existing explicit human role assignment persists. A directory,
branch name, title or Markdown extension alone is not a role grant. Initialization
only means read/status/wait; an actual change request proceeds within its scope.

For an unassigned session receiving a material change request, use the project's
plan -> exact dev adoption -> dev execution workflow. First reuse an applicable
P card or prepare the next unused P number with bounded review/acceptance. A
plan-assigned session prepares and hands off; it does not implement in plan or
silently become dev. A session authorized for both roles may perform the stages
sequentially in their proper worktrees only when no other writer owns them.
Check existing writers before mutation; do not create chats or message anyone
without the project's human authorization. Missing transport leaves an explicit
pending file handoff, never an invented completed delivery.

Classify documents by purpose, not .md: planning requirements/reviews/governance
are plan-owned; product README, user guides, release notes and repository-facing
usage documentation are implementation deliverables authored by dev after exact
P-card adoption. A plan-owned document needed by dev is integrated/adopted there;
plan-only commit or push is not completion of a requested cross-branch delivery.
Explicit planning-only/draft requests may end on plan and must say so. Questions
and read-only reviews do not need new P cards. Reuse a fitting existing card for
small changes; do not bypass the workflow merely because a change is documentation.

For GitHub/document update requests, record the requested file, target repository,
branch/ref and completion evidence in the P card. A local commit, a push to plan,
dev adoption, a push to dev and visibility on GitHub's default branch are distinct
outcomes. Verify the authorized target SHA/ref (and file content where applicable)
before claiming delivery. If the user specifies no branch, follow configured
plan/dev delivery and report those branches; never infer main promotion from
"GitHub update". Existing main/release and remote permissions still apply.

Existing plan guards validate checkpoint/handoff history, not a universal plan
file allowlist. Passing hooks does not authorize plan implementation or prove a
P-card exists. This routing procedure is an agent obligation, not a mechanical
block of arbitrary writes. Preserve scoped user pauses without applying a fixture
pause to an unrelated authorized task or resuming the fixture as a side effect.
