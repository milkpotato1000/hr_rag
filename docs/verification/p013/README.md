# P013 execution evidence

Exact READY plan: 0cb6497a63c3c79e2b11615f6897f3f4f8f7eb85; adoption: 9d7cb4b.
The version-bound human approval sidecar covers the fixed input/expected data. It does not approve new model outputs. Historical preparation run001–004 remain unchanged.

## Offline implementation

Strict role schemas, duplicate-key/nonfinite rejection, Unicode occurrence spans, full reference comparison, E/U/C/I and coverage, maximum one-to-one matching, required/supplementary scoring, independent synthetic fixtures, source-review sidecar validation, LangChain trace export validation, immutable experiment inputs/code, serial durable ledger and offline replay/bundle/HTML.

unit-tests-final.log contains the current offline unit results; preparation-regression.log covers the existing preparation modules. tokenizer-historical-check.json compares a no-download GGUF-vocabulary BPE implementation to all 30 historical actual provider input token counts. All 30 agree exactly. This is measured historical calibration, not proof of every possible Unicode input. New calls also check actual prompt_eval_count, and mismatches fail.

P019's byte upper bound is not reused as an exact token count. The installed tokenizer metadata and full pinned single-user/no-tools/think=false template are required. The only new model requests initially permitted are S2's fixed 8 answers × 2 repetitions. S3 requires all S2 outputs to pass; S4 requires S3 as well. The live S4 export integration is not yet enabled, and P013 completion is not claimed.

No automatic semantic approval is made for a paraphrased extraction. Exact text plus every occurrence span can pass mechanically; differing outputs retain null final extraction scores and exact-match diagnostics pending independent semantic review. This does not label every paraphrase wrong. Model-derived decisions cannot approve themselves.

The runtime does not change/restart servers, download models, clear prior counters or retry. Its 1-second RSS/pressure monitoring is observational, not a hard memory sandbox. Transport ambiguity, missing memory measurements or critical memory state blocks subsequent requests.
