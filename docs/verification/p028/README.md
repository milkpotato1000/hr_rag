# P028 installation verification

2026-11-27. Exact READY 7e92000a4365519a11861696d3692f2d00d7c106 adopted in 48434cb after P027 completion 41a469d and verified personal/dev push. P029 remains queued for its separate later adoption. P013 remains BLOCKED; no model/API/Drive/login/user credential access, server startup or recovery grant consumption.

## Build and installed execution

- New build environment: build 1.6.1/setuptools 84.2.1 plus packaging 26.4/pyproject-hooks 1.3.3. Official PyPI hash resolution/install in [build lock](../../../packaging/requirements-build.lock), build-resolve.log/build-install.log. No global or previous environment/lock modification.
- Explicit [allowlist](../../../packaging/allowlist.json), pyproject packages/resources and MANIFEST.in exclude repository stages/evaluation/GT/harness/tests/private artifacts. [artifacts.json](artifacts.json) records wheel/sdist hashes and complete inventories. No license is invented. The pure-Python wheel tag does not promise Windows storage support.
- `python -m build --no-isolation` creates sdist then wheel from that sdist. A second extraction and independent wheel build is installed in a third venv; all wheel member bytes match, even if ZIP container timestamps differ. Build backend execution is distinct from application network calls.
- [installation.json](installation.json) records fresh core-only/extras/rebuilt environments outside the source checkout, with no editable install. [installed-commands.json](installed-commands.json) records actual console/module help/version, rebuild and clean process probes. PYTHONPATH/PYTHONHOME are absent; explicit minimal process environment avoids passing user secret values. Package import is asserted under each new venv's site-packages and no dev source path is present in sys.path.
- [core-probe.json](core-probe.json), [extras-probe.json](extras-probe.json), [rebuilt-probe.json](rebuilt-probe.json): init/no-clobber/doctor, TXT+MD snapshot, all three chunkers, ask-preview, compare9 rows, Drive offline preview, marked configuration rejection for generation/evaluation before key/HTTP, installed Git directory/worktree file credential rejection outside cwd and allowed dedicated outside directory. Socket/DNS and secret-env lookup are guarded in the application probes.
- Extras: pinned pypdf 6.21.2 and exact P027 SDK lock installed independently. A tiny generated synthetic PDF is parsed by the installed module's subprocess; no repository PDF is needed. Actual SDK imports/signatures and cached fake credentials checked; no callback/browser login. Core-only doctor reports optional missing without failing core; no SDK/PDF module imported by core path.
- [regression.log](regression.log): 51 PASS = prior 48 + 3 new resource/doctor/configuration/credential boundary tests. Prior fake transport/owned loopback HTTP and actual mocked SDK tests remain active. [unit-initial.log](unit-initial.log) preserves the new unit checks. Tests do not classify fake responses as live model quality.

## Failures preserved and corrected

installed-commands-initial.json preserves an attempted local rebuild installation denied by the default uv cache sandbox. The verifier now uses a new cache inside its owned temporary area, no bypass or global cache modification.

installed-commands-env-guard-failure.json records an overbroad environment guard that also blocked argparse locale settings; revised to deny secret-like keys. installed-commands-sdk-env-failure.json records SDK import's stdlib WSGI environment-copy behavior hitting that guard. Final probes receive a minimal clean environment without user secrets and retain the secret lookup/network blockers. These were verifier failures; no real service request occurred and no raw secret values are in logs.

## Limits and reproduction

Same physical Mac, Python 3.12.14, fresh venvs. Python 3.10 syntax checked, not every runtime. macOS storage primitive verified; Linux implementation exists but untested, Windows unsupported. No new computer, paid API, model memory/quality, live Drive, or Codex/Claude Code UI test is claimed.

[install_environments.py](install_environments.py) is an explicit developer verification script that installs allowed dependencies from PyPI into fresh environments, not a product command. [verify_installation.py](verify_installation.py) uses that record, bounded local rebuild/install and [installed_probe.py](installed_probe.py); new probes use new output names, preserving earlier attempts. Runtime network is blocked. [validate_artifacts.py](validate_artifacts.py) checks links, resource/source provenance, Python syntax, lock and protected baseline preservation; results are in [checks.json](checks.json).

P028 changes only __main__.py, llm/core.py, connectors/drive_config.py and drive_auth.py among preexisting package files. All prior stages/evaluation/P013, GT and dependency locks remain hash-identical. The installed credential boundary uses actual cwd/explicit workspace and ancestor Git markers; absolute/no-symlink/0700/0600 and original HR container boundaries remain enforced. Sample output is preview-only until the user configures identities; no automatic model lookup/download/fallback.
