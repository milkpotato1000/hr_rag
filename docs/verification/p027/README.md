# P027 Drive connector verification

2026-11-27. READY afda7f700b848defe0e78fa70313b5b32a5c9c6f adopted in 1aa8862 before implementation. Actual REST/OAuth code connects a single supported Drive file to P026 snapshot/build/ask provenance. Tests use only synthetic documents, injected auth/HTTP and owned loopback HTTP. No real Google login, user credential, Drive, model or paid API request was made.

## Reproduction and evidence

- [SDK input](../../../rag_package/requirements-drive.in) and [hash lock](../../../rag_package/requirements-drive.lock): exact google-auth-oauthlib 1.5.0/google-auth 2.63.1 plus transitive dependencies installed in new ignored `.rag-runs/p027-sdk/.venv`. Official PyPI installation was authorized; no existing environment/lock changed. sdk-venv.log, sdk-resolve.log, sdk-install.log and sdk-import.json preserve installation/import/signatures.
- Python 3.12.14 on this Mac. A .pth in that new venv appends the existing Document Chunking site-packages for read-only reuse of pypdf 6.21.2, including PDF subprocesses. This is not a fresh PDF installation or wheel-only/other-OS verification.
- `-m unittest discover -s tests/rag_package -v`: tests-release-allowed.log contains final 48 PASS (12 Drive + 36 P025/P026 regression). Outbound socket/DNS blocked, with owned loopback explicitly allowed by transport tests. Actual SDK state/PKCE construction, cached credential parsing and refresh are exercised with mock browser/HTTP. No OAuth callback/login with a person occurred.
- tests-initial.log preserves 46-test failure: HTTP/1.0 body completion closed the socket before a further timeout setter; fixed by stopping at the declared length. A mock scope also ended before a session assertion and hit the test DNS blocker; fixed test scope, no external request succeeded. tests-second.log is 46 PASS, tests-final.log adds two boundary/SDK tests (48 PASS), tests-release.log preserves a sandbox-only bind failure (4 owned-loopback servers denied); tests-release-allowed.log reruns with authorized loopback binding and verifies final logging suppression/preview path checks. System Python 3.9 is outside the supported Python 3.10+ range; artifact verification uses the isolated Python 3.12.14.
- [validate_artifacts.py](validate_artifacts.py) checks preview CLI, all local learning links, Python 3.10 syntax, lock versions, ignored output, legacy hash preservation and guard. [checks.json](checks.json) records the results. No browser rendering was observed.

## Contract matrix

| Boundary | Fixture coverage |
| --- | --- |
| Strict URL/config, ambiguity/resourcekey, no secret/SDK/network preview | test_strict_links_and_offline_preview; test_other_output_boundaries_and_expired_env_token |
| TXT/MD/PDF/Docs export, scan needs_review, origin→index→answer trace | test_blob_resource_key_origin_and_pipeline; PDF/Markdown/export fixture tests |
| Version/bytes fingerprint and tampered origin | test_version_bytes_changes_and_origin_tampering |
| Metadata permissions/MIME/limits; before/after revision and permission changes | metadata/revision race tests |
| Checksum/size/empty/duplicate output, absent/newline token | checksum and input failure fixtures |
| Download/snapshot/receipt/publish write failures preserve request stages; no retry | output failure fixtures |
| Protected directory/file permissions, symlink, scope/token endpoint; login no-clobber, refresh once | auth boundary fixtures |
| Actual installed SDK state/PKCE, callback options, cached credentials/refresh; endpoint/TLS/proxy/redirect controls | installed SDK tests with fake send/browser |
| HTTP 401/403/404/429/5xx, redirect/partial/length/empty/deadline | real transport on owned loopback only |
| Secret sentinel absence | stdout/errors/receipt/snapshot checks using deliberately fake secret strings |

Only documents.py (optional origins), rag.py (origin trace) and __main__.py (CLI) change among prior rag_package files. P025 LLM files, previous PDF lock, algorithm provenance, HR/source-v4/evaluation/P013 files remain hash-identical. P013 remains BLOCKED, old success/failure/GT retained, recovery grant unused. Live connectivity, model quality, memory safety and other operating systems remain unverified. Packaging is subsequent P028, not part of this completion.
