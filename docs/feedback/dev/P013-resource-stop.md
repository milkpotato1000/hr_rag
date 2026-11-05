# P013 — OS critical memory pressure stopped S2

Type: validation/resource failure within adopted P013. No new plan scope is approved by this note.

Exact plan 0cb6497a63c3c79e2b11615f6897f3f4f8f7eb85, adoption 9d7cb4b; frozen experiment p013-run001 manifest 007f38f7c5ae6f6de30baff8762717db87b3e757218457b334bc14109e8fb514.

## Observed

The first of 16 extraction requests returned correct two-claim text and occurrence spans, but macOS pressure reached critical (4) during loading. This independently triggers section 3's stop rule even though sampled Ollama RSS peaked at about 5.81 GiB, below 12 GiB. See docs/verification/p013/resource-stop.json and the immutable calls/001.json. The first call remains charged to the original ledger. The remaining 15 S2 and all S3/S4 requests were not sent. The runtime's next-request guard was verified offline with network disabled.

## Proposed recovery review, not executed

1. Determine a suitable memory window with the user; do not terminate unrelated applications/sessions or lower the critical-pressure threshold. The post-stop normal reading alone does not prove the next 8B load will remain below critical pressure.
2. Review explicit recovery of the existing resource-stop record. Preserve its event, first call, exact payloads, counter and original four-hour wall window. No model-output retry, new run directory budget reset or silent ledger edit. If the wall window expires, obtain a new plan contract; do not reset it locally.
3. If recovery is authorized, implement/test an append-only resource recovery event that distinguishes a completed request's resource stop from an unresolved timeout. It must not clear ambiguous provider activity or any unrelated stop. Integrate/exact-adopt the plan before applying any changed execution semantics.
4. Resume only the unexecuted S2 requests if permitted. S2/S3 must pass before S4; new semantic output review is separate from the already-approved fixed data. Preserve the original runtime stop even if later execution succeeds.
5. S4 live LangChain/export integration and full end-to-end report remain unfinished. Do not mark P013 complete or treat the successful first sample as model-quality acceptance.

A model/quantization/limit change, extra requests, retries or re-embedding is outside this exact run's authorization. No reverse chat message is sent; plan can observe this committed evidence through its existing read/wait workflow.
