# P025 verification — independent LLM providers

2026-11-27. Exact plan 0f7ce86a3eb2c41fbd9bd6f3a03f5acb37f3621f adopted in ab52ff5 before implementation. Product paths: rag_package/llm, tests/rag_package, examples/llm and docs/learning/rag-package/providers.md. Existing RAG and evaluation runners are not integrated or edited.

## Actual validation

- Python 3.12.14 from the existing 2. Document Chunking/.venv; no dependency installation.
- `-m unittest discover -s tests/rag_package -v`: 18 tests PASS in tests-final.log. Tests have independent expected wire fields and expected result statuses; the production default uses real HTTP, not canned output.
- Existing evaluation/project_b/test_evaluator.py: 16 tests PASS in legacy-evaluator-regression.log with socket/DNS denied. Existing model runners were not invoked.
- validate_artifacts.py records real CLI help/validate/preview execution for all new examples, local-link/JSON checks, Python 3.10 syntax parsing, bounded secret scans, parent-file hash preservation, guard and diff checks in checks.json.
- Commit/push hooks remain active. Normal personal/dev delivery is recorded after the implementation commit. No main promotion.

## Contract matrix

| Contract cases | Tests/evidence |
| --- | --- |
| Three provider routing, output budget, system split, role selection, auth/version, no foreign options | test_routing_and_roles; canonical Korean messages preserved |
| JSON instruction and actual messages hash, original input unchanged, no key/network during validate/preview | test_preview_no_keys_no_network_and_json_hash; test_cli_and_files |
| Unknown fields, bool/numeric/nonfinite/range errors, invalid roles/URLs/identity and P024 example_only rejected | test_config_rejection, test_urls, test_messages |
| Text/JSON, API alias, missing usage=null, duration ns→ms | routing, usage and JSON tests |
| Local missing/different digest before dispatch; same name changed digest after dispatch | test_identity_gates; test_missing_model_and_empty_envelopes |
| Truncated/refused/tool/unknown finish/block; malformed envelope/role/model/done/empty/nonstring content | test_non_success_finishes, test_envelope_and_json_errors, test_additional_envelope_boundaries |
| Duplicate/nonfinite/fenced/non-object JSON | test_envelope_and_json_errors |
| No hidden thinking persistence | test_usage_missing_and_hidden_thinking, test_inline_thinking_rejected_not_repaired, test_escaped_thinking_in_json |
| Missing/invalid synthetic key dispatch0; HTTP401/403/429/5xx, timeout/size/redirect/connection failures, one dispatch and no secret error echo | test_missing_key_and_errors_no_retry_or_leak; test_real_transport_errors |
| Real urllib path with fake HTTP, proxy disabled, no redirects, size/JSON errors, owned server only | HTTPTests, socket and DNS guards permit only that test's bound address/port |
| Import/help offline, failure exit and output, atomic no-clobber, input file bound | test_import_help_and_cli_failure_artifact; test_cli_and_files; test_http_invoke_cli_and_no_proxy |

The initial test run is preserved in tests-initial.log: the sandbox denied fake server bind and a CLI test incorrectly blocked all environment lookups (including argparse terminal formatting), not just API key resolution. The test now specifically forbids API key lookup during offline CLI paths. Fake server tests run with reviewed local bind permission plus socket/DNS guards. tests-second.log records the first passing 14-test run; final tests add more response/thinking/CLI boundaries. The initial host python3 was 3.9; final tests use the existing Python 3.12.14 environment.

Plan's in-scope thinking review was applied: nonempty Ollama thinking with think=false is unsupported_response; separated Anthropic thinking blocks are discarded, inline think tags are rejected without repairing the answer, including escaped tags inside parsed JSON. No thinking or provider raw body is retained in artifacts.

## Sources and limits

Official docs opened 2026-11-27: [Ollama chat](https://docs.ollama.com/api/chat), [OpenAI Chat create](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [Claude Messages create](https://platform.claude.com/docs/en/api/http/messages/create). The implemented wire mapping follows the adopted contract, including Anthropic Bearer/version2026-10-21 and OpenAI max_completion_tokens. OpenAI n is omitted because the documented default is one and some models reject explicit n. Multiple returned choices remain invalid. API response model aliases are recorded, not treated as a digest verification.

Actual provider requests, actual user key reads, inference, model downloads, Ollama server starts, paid API calls and P013 recovery consumption: **zero**. Fake HTTP traffic is not a model run. No live API success, Korean quality, memory safety, clean-machine installation, browser rendering or RAG integration is claimed. timeout_seconds is a socket timeout, not an experiment wall budget. No model-level capability discovery is claimed; unsupported model options remain provider errors.

Existing Naive/Chunking/evaluation code, locks and artifacts plus P013 state/history/approval and verification files are hash-checked against preservation-before.json. P013 remains BLOCKED, with its original success1/failure/GT and unused recovery grant intact. The previous endpoint refusal is historical; no new endpoint probe was made.
