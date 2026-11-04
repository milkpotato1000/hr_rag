#!/usr/bin/env python3
"""Local contract guard. No dependencies, network access, or semantic approval."""
import argparse
import json
import pathlib
import re
import subprocess
import sys

import plan_cards
import plan_intake
import workflow_control


def git(*args, check=True):
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and result.returncode:
        raise ValueError(result.stderr.strip() or "git command failed")
    return result


def read_at(path, target):
    if target == "worktree":
        return pathlib.Path(path).read_text()
    return git("show", (":" if target == "index" else target + ":") + path).stdout


def ancestor(older, newer):
    return git("merge-base", "--is-ancestor", older, newer, check=False).returncode == 0


def policy():
    # Use the committed policy: editing a working/index policy must not disable checks.
    return json.loads(git("show", "HEAD:.harness/policy.json").stdout)


def baseline(target, config):
    record = json.loads(read_at(config["baseline_file"], target))
    sha = record.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Baseline must be a full commit SHA")
    if not record.get("review_reference", "").strip():
        raise ValueError("A handoff/review reference is required; it is not semantic approval")
    if not ancestor(sha, config["planning_branch"]):
        raise ValueError("Baseline is not in local planning branch history; fetch/update plan first")
    tips = ["HEAD"] if target in ("index", "worktree") else [target]
    if target in ("index", "worktree"):
        merge = git("rev-parse", "--verify", "MERGE_HEAD", check=False)
        if merge.returncode == 0:
            tips.append(merge.stdout.strip())
    if not any(ancestor(sha, tip) for tip in tips):
        raise ValueError("Merge the selected plan commit into dev before adopting it")
    return sha


def check_contracts(target, config):
    sha = baseline(target, config)
    args = ["diff", "--name-only", "-z"]
    if target == "index":
        args += ["--cached", sha]
    elif target == "worktree":
        args += [sha]
    else:
        args += [sha, target]
    paths = config["protected_paths"]
    changed = git(*args, "--", *paths).stdout.split("\0")
    if target == "worktree":
        changed += git("ls-files", "--others", "--exclude-standard", "-z", "--", *paths).stdout.split("\0")
    changed = sorted(set(filter(None, changed)))
    blocked = []
    for path in changed:
        if not config.get('p_card_execution') or not plan_cards.CARD.fullmatch(path):
            blocked.append(path)
            continue
        # New/deleted cards and file type/mode changes are never execution edits.
        try:
            base_entry = git('ls-tree', sha, '--', path).stdout
            if not base_entry.startswith('100644 blob '):
                raise ValueError('P-card must exist as regular file in adopted plan')
            if target == 'worktree':
                node = pathlib.Path(path)
                if node.is_symlink() or not node.is_file() or node.stat().st_mode & 0o111:
                    raise ValueError('P-card file type/mode changed')
            elif target == 'index':
                if not git('ls-files', '--stage', '--', path).stdout.startswith('100644 '):
                    raise ValueError('P-card index type/mode changed')
            elif not git('ls-tree', target, '--', path).stdout.startswith('100644 blob '):
                raise ValueError('P-card commit type/mode changed')
            previous_ref = 'HEAD' if target in ('worktree', 'index') else target + '^'
            previous = git('show', previous_ref + ':' + path, check=False)
            plan_cards.validate_change(read_at(path, sha), read_at(path, target),
                                       lambda p: read_at(p, target),
                                       previous.stdout if previous.returncode == 0 else None)
        except (ValueError, OSError) as error:
            blocked.append(path + ' (' + str(error) + ')')
    changed = blocked
    if changed:
        raise ValueError("Protected files differ from adopted plan " + sha[:12] + ":\n  " + "\n  ".join(changed))
    # Captured requests are immutable facts. Corrections are new request records.
    previous = 'HEAD' if target in ('worktree', 'index') else target + '^'
    if git('rev-parse', '--verify', previous, check=False).returncode == 0:
        prior = git('ls-tree', '-r', '--name-only', previous, '--', plan_intake.REQUESTS).stdout.splitlines()
        for path in prior:
            if path.endswith('.json') and read_at(path, previous) != read_at(path, target):
                raise ValueError('Dev intake request is immutable; add a follow-up request: ' + path)
    current = snapshot(target)
    plan_intake.collect(current, current)
    previous_snapshot = snapshot(previous) if git('rev-parse', '--verify', previous, check=False).returncode == 0 else None
    workflow_control.validate_changes(current, previous_snapshot, config)
    print("PASS: contracts match adopted plan " + sha[:12])


def snapshot(revision):
    from work_queue import Source
    class Snapshot(Source):
        def __init__(self, revision):
            super().__init__(pathlib.Path.cwd())
            self.revision = revision
        def read(self, path):
            return read_at(path, self.revision)
        def names(self, directory):
            if self.revision == 'worktree':
                return [str(p.relative_to(pathlib.Path.cwd())) for p in (pathlib.Path.cwd() / directory).rglob('*') if p.is_file()]
            command = ('ls-files', '--', directory) if self.revision == 'index' else ('ls-tree', '-r', '--name-only', self.revision, '--', directory)
            return git(*command).stdout.splitlines()
        def paths(self, directory):
            return [p for p in self.names(directory) if p.endswith('.md')]
        def records(self, directory):
            return {pathlib.Path(p).stem: json.loads(self.read(p)) for p in self.names(directory) if p.endswith('.json')}
    return Snapshot(revision)


def check_plan_controls(target):
    previous = 'HEAD' if target in ('worktree', 'index') else target + '^'
    prior = snapshot(previous) if git('rev-parse', '--verify', previous, check=False).returncode == 0 else None
    workflow_control.validate_role_changes(snapshot(target), prior, 'plan')
    print('PASS: plan checkpoint and handoff history')


def install():
    desired = ".githooks"
    current = git("config", "--get", "core.hooksPath", check=False).stdout.strip()
    if current and current != desired:
        raise ValueError("Existing core.hooksPath must be integrated explicitly: " + current)
    hooks = pathlib.Path(git("rev-parse", "--git-path", "hooks").stdout.strip())
    if not current and hooks.exists():
        active = [p.name for p in hooks.iterdir() if p.is_file() and not p.name.endswith(".sample")]
        if active:
            raise ValueError("Existing hooks must be integrated explicitly: " + ", ".join(active))
    git("config", "--local", "core.hooksPath", desired)
    print("Installed shared repository hooks: " + desired)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--target", default="worktree", help="worktree, index, or commit/ref")
    check.add_argument("--branch", help="Branch being validated (for a push ref)")
    adopt = sub.add_parser("adopt")
    adopt.add_argument("commit")
    adopt.add_argument("--review-reference", required=True)
    sub.add_parser("install")
    sub.add_parser("pre-push")
    args = parser.parse_args()
    root = git("rev-parse", "--show-toplevel").stdout.strip()
    import os
    os.chdir(root)
    if args.command == "install":
        install()
        return
    config = policy()
    branch = git("branch", "--show-current").stdout.strip()
    if args.command == "adopt":
        if branch != config["development_branch"]:
            raise ValueError("Adoption records are written only on the configured development branch")
        sha = git("rev-parse", "--verify", args.commit + "^{commit}").stdout.strip()
        path = pathlib.Path(config["baseline_file"])
        previous = path.read_bytes() if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"commit": sha, "review_reference": args.review_reference}, indent=2) + "\n")
        try:
            check_contracts("worktree", config)
        except Exception:
            if previous is None:
                path.unlink()
            else:
                path.write_bytes(previous)
            raise
        print("Adoption recorded. Stage and commit " + str(path) + "; pending semantic decisions remain pending.")
    elif args.command == "pre-push":
        for line in sys.stdin:
            local_ref, sha, remote_ref, _ = line.split()
            if sha == "0" * 40:
                continue
            if remote_ref == "refs/heads/" + config["development_branch"]:
                check_contracts(sha, config)
            elif remote_ref == "refs/heads/" + config["planning_branch"]:
                check_plan_controls(sha)
    else:
        selected = args.branch or branch
        if selected == config["release_branch"] and args.target == "index":
            raise ValueError("No direct release-branch commits; promote reviewed development with a fast-forward merge")
        if selected == config["development_branch"]:
            check_contracts(args.target, config)
        elif selected == config["planning_branch"]:
            check_plan_controls(args.target)
        elif not selected:
            raise ValueError("Detached HEAD: specify --branch for an explicit check")
        else:
            print("SKIP: development contract guard on branch " + selected)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        sys.exit(1)
