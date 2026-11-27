# RAG package follow-up ordering — human clarification pending

2026-11-27. The existing order P013/P014 -> P008 -> P010 Hybrid -> P020 reranking remains in force. P013 local model execution is explicitly held. The new package goal motivates asking whether Hybrid/reranker code and offline verification may precede the held live evaluator experiments, while preserving the hold itself.

An asynchronous question was presented directly to the user in the plan chat:

1. Keep live evaluation held, but implement and verify Hybrid/reranking offline first (recommended for package progress).
2. Preserve the existing order and finish evaluator experiments before Hybrid/reranking.

No answer has been observed as of this record. A preselected option or elapsed time is not authorization. Do not change the corresponding dependencies or resume P013 from this question alone. P026 generic document RAG and P027 source connector preparation are independent and continue. This is not a project-wide pause and does not invalidate the current P026 READY handoff.

When a human response arrives, record its actual scope and amend the relevant plan contracts/dependencies before exact dev adoption. Do not mark model quality or held experiments complete based on offline adapter tests.
