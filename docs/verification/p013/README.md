# P013 execution evidence

Exact READY plan: 0cb6497a63c3c79e2b11615f6897f3f4f8f7eb85; adoption: 9d7cb4b.
The version-bound human approval sidecar covers the fixed input/expected data. It does not approve new model outputs. Historical preparation run001–004 remain unchanged.

## Offline implementation

Strict role schemas, duplicate-key/nonfinite rejection, Unicode occurrence spans, full reference comparison, E/U/C/I and coverage, maximum one-to-one matching, required/supplementary scoring, independent synthetic fixtures, source-review sidecar validation, LangChain trace export validation, immutable experiment inputs/code, serial durable ledger and offline replay/bundle/HTML.

unit-tests-final.log contains the current offline unit results; preparation-regression.log covers the existing preparation modules. tokenizer-historical-check.json compares a no-download GGUF-vocabulary BPE implementation to all 30 historical actual provider input token counts. All 30 agree exactly. This is measured historical calibration, not proof of every possible Unicode input. New calls also check actual prompt_eval_count, and mismatches fail.

P019's byte upper bound is not reused as an exact token count. The installed tokenizer metadata and full pinned single-user/no-tools/think=false template are required. The only new model requests initially permitted are S2's fixed 8 answers × 2 repetitions. S3 requires all S2 outputs to pass; S4 requires S3 as well. The live S4 export integration is not yet enabled, and P013 completion is not claimed.

No automatic semantic approval is made for a paraphrased extraction. Exact text plus every occurrence span can pass mechanically; differing outputs retain null final extraction scores and exact-match diagnostics pending independent semantic review. This does not label every paraphrase wrong. Model-derived decisions cannot approve themselves.

The runtime does not change/restart servers, download models, clear prior counters or retry. Its 1-second RSS/pressure monitoring is observational, not a hard memory sandbox. Transport ambiguity, missing memory measurements or critical memory state blocks subsequent requests.

## Actual S2 execution and resource stop

Frozen manifest: 007f38f7c5ae6f6de30baff8762717db87b3e757218457b334bc14109e8fb514, committed before dispatch in cc7fab1. One Qwen3:8b request ran for 21.76 seconds (287 input / 146 output tokens). It returned the two expected facts with exact text and occurrence spans. This one case has extraction P/R/F1=1; the full 8-case/two-repeat gate is NOT passed.

During model loading the OS pressure level reached critical (4) in four 1-second samples. Peak sampled Ollama RSS was 6,239,797,248 bytes (about 5.81 GiB), below the separate 12 GiB RSS threshold. The OS-critical rule independently required stopping. The in-flight request completed; no next request was dispatched. ledger.json retains unresolved=true with pending=null. No retry or counter reset occurred. The later read-only observation found no loaded model and pressure level 1; this is not a resume authorization.

resource-stop.json and the raw calls/001.json preserve this distinction. S2 is 1/16; S3/S4 are 0. C2/C3 cannot pass, and P013 remains incomplete. Live S4 integration remains disabled. The report is evaluation/project_b/artifacts/p013-run001/review.html. It is a static output; actual browser/narrow/keyboard observation of this new report has not been performed. Prior run004 UI confirmation is not reused.

The post-stop offline bundle replays the same JSON and HTML without model calls. Prior packet/source/P007 files remain unchanged, and both selected P007 chunk/index identities were verified read-only. docs/feedback/dev/P013-resource-stop.md proposes a bounded recovery review; it does not change the adopted contract or clear the stop.
