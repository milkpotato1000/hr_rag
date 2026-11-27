# P026 verification — document RAG integration

2026-11-27. Exact READY bb733052fda6dfbdd7de8e1f2eae50118ae059c1 adopted in 7c88c59 before implementation. New general document modules and CLI use P025's public preview/invoke APIs. Existing HR/source-v4/evaluation paths and P025 LLM code remain unchanged.

## Results and reproducible checks

- Existing Python 3.12.14 and installed pypdf 6.21.2 were reused; no installation/download.
- `-m unittest discover -s tests/rag_package -v`: 36 PASS in tests-final.log, comprising 18 new document/RAG tests and all 18 P025 regressions. External socket/DNS access is blocked; the single owned loopback fake HTTP server is allowed only by its test. Fake HTTP is not an Ollama server.
- tests-initial.log preserves the initial 40-PASS run; it included four duplicate inherited/imported HTTP tests. Final discovery removes duplicates and incorporates parser metadata/unsupported option checks without dropping substantive coverage.
- validate_artifacts.py executes the documented snapshot/build/ask/compare preview paths on supplied synthetic samples, checks complete comparison rows, null metrics/cost, artifact provenance, optional PDF lock/provenance hashes, local Markdown links, `.rag-runs/` Git exclusion, Python 3.10 syntax and original-file preservation. Actual output is in checks.json. Preview output lives only in temporary ignored directories and is cleaned after verification.
- Contract guard, diff check and normal commit/push hooks remain enabled. Implementation/delivery commits are recorded separately after checks.

## Independent contract matrix

| Boundary | Actual fixture/check |
| --- | --- |
| Multi-document TXT/Markdown; original bytes, NFC/CRLF, stable snapshot identity and false/true synthetic | test_snapshot_normalization_identity_and_original_copy |
| Three chunkers, >20K text, overlap0/99, exact slices/max100/coverage, section-limited overlap, Korean/Markdown heading paths and explicit fallback | test_chunks_long_coverage_overlap_and_heading_scope; test_whitespace_coverage |
| BM25 handwritten expected rank/tie, positive scores, title excluded; budget skips oversized candidate then includes a later one | test_bm25_manual_order_ties_and_budget_skip |
| Same LLM-only/query settings preserve chunk/index identity; different chunk settings stale | test_build_identity_llm_and_query_settings |
| Three P025 provider E2E, canonical citations across documents, actual wire generation dispatch once | test_three_provider_e2e_exact_citations |
| Preview/no-context key/network/dispatch0 | test_preview_and_no_context_no_key_or_network |
| Unknown/duplicate citations, extra field, abstain with references, malformed JSON, truncation/tool/refusal; failed content not retained | test_business_and_provider_failures_not_answers |
| Every compare row including failed and no-context; changed axes, source/questions hash, fixture labels, max call count, N/A/cost null | test_compare_all_rows_failures_axes_and_labels |
| Unsupported algorithms/reranker, numeric bounds/types, duplicate IDs, unsupported format, missing file, broken UTF-8 and 20MiB overflow | test_unknown_options_and_invalid_sources |
| Hash/path/offset/index tampering; existing directory and publication race no-clobber | test_tamper_paths_and_no_clobber; test_snapshot_page_metadata_and_index_tamper |
| Handwritten two-page PDF + another document; canonical separator has no fake page; exact page intersections | test_pdf_physical_pages_and_cross_page_citations |
| Actual existing 23-page synthetic handbook PDF→structure→BM25→fake answer→source citations | test_existing_synthetic_handbook_pdf |
| Blank/scanned-equivalent page, encrypted/corrupt/101-page PDF, timeout, missing optional dependency; independent text path | test_pdf_failures_and_optional_dependency |
| Model call followed by injected OSError/UnicodeError during output; safe failure stage and dispatch=true, no automatic retry, CLI/compare preserve failure | test_post_dispatch_write_failure_preserves_attempt_without_retry |
| CLI preview, duplicate question IDs, ID named build does not collide with build folder | test_cli_preview_and_duplicate_questions; compare fixture |
| Actual P025 HTTP transport through new RAG, with automatically test_fixture labeling | RagHTTPTests.test_rag_uses_real_http_transport_with_fixture_label; intentionally invalid business response remains failed |

P025's unchanged regression tests cover actual HTTP status codes/redirect/oversize/timeout/JSON parsing, digest before/after, authentication mapping, key non-disclosure and hidden thinking. RAG adds business schema validation and strips content/parsed_json from retained provider metadata; only a validated final answer is persisted.

Plan's in-scope output failure review was applied. ask catches publication/storage OSError and UnicodeError as well as RagError, preserving whether a generation request was attempted. compare retains each failed row and propagates dispatch state if its own final publication fails. CLI prints a sanitized code/stage/dispatch flag, never the synthetic exception content.

## Preservation and limitations

preservation-before.json freezes existing Naive/Chunking/evaluation code, locks/artifacts, P013 state/history/approval/verification and P025 LLM module bytes. checks.json confirms they are unchanged. P013 remains BLOCKED; original success1/failure/GT and unused recovery grant remain intact. Existing synthetic/source-v4 allowlists and fixed runners were not weakened. Selected pure algorithms and the PDF lock have source commit/path/hash records in rag_package/provenance.json.

Actual model/API calls, actual user key reads, model downloads, model-server starts, paid calls and P013 grant consumption: **zero**. The implementation defaults to real P025 HTTP on explicit execute; canned responses exist only in tests. No Korean answer quality, memory PASS, real API success, private document evaluation, UI integration, Linux publication execution or clean-machine installation is claimed. Browser rendering was not observed; Markdown source/links were checked.

Dense/Hybrid/reranking/model-based chunking/Drive/OCR remain unsupported in this new route. Faithfulness/Correctness/Recall/MRR/nDCG remain null with explicit reasons. The capability milestone is an offline-verified general document pipeline, not completion of the overall package roadmap.
