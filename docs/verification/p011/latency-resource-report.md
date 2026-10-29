# P011 latency and resources

All values below are milliseconds, original-root A vs candidate B with3 paired repetitions. Full distributions and component times are in controlled-comparison.json. No p95 or statistical significance claim.

| Phase | Case | A median | B median | Paired delta median (B−A) | Ratio median |
|---|---|---:|---:|---:|---:|
|cold|meal-bm25|7322.9|7640.7|+329.7|1.045|
|cold|pdf-q06|28849.3|29158.7|+584.3|1.020|
|cold|q03|16810.2|16601.4|+346.5|1.021|
|warm|c01|7570.0|10963.7|+3517.9|1.472|
|warm|c02|11931.6|12234.4|+302.8|1.025|
|warm|c03|5575.0|7533.5|+2222.5|1.409|
|warm|c04|11716.4|11664.5|+258.9|1.023|
|warm|meal-bm25|3089.1|3970.0|+1051.5|1.355|
|warm|pdf-q06|30470.4|30601.5|+389.0|1.013|
|warm|q01|13038.4|13370.3|+310.1|1.025|
|warm|q02|13523.7|13788.4|+90.7|1.007|
|warm|q03|16298.4|16616.1|+298.2|1.018|
|warm|q04|11720.1|12006.3|+273.8|1.024|
|warm|q05|12280.8|12949.5|+330.0|1.025|
|warm|q06|13073.7|13322.6|+295.4|1.022|
|warm|q07|13679.3|13945.2|+227.9|1.017|
|warm|q08|11517.8|11971.1|+389.1|1.034|
|warm|q09|16980.1|17254.6|+290.1|1.017|
|warm|q10|12596.6|12759.9|+91.5|1.007|
|warm|q11|15302.6|15693.9|+486.0|1.032|
|warm|q12|11174.8|11512.9|+315.9|1.028|
|warm|q13|10987.7|11104.8|+455.5|1.041|
|warm|q14|10607.1|10822.4|+317.6|1.030|

Warm refers to an already exercised model-service workflow; each Python worker is new. Dense switches BGE/Qwen with MAX_LOADED_MODELS=1. Model load, embedding, search, context, HTTP generation and provider durations are reported separately, never summed as if disjoint. BM25 index-open is missing because the original boundary includes it in search; it is not filled with zero.

Initial138 slots and all4 cold HTTP500 errors remain in latency-report.json. OS sleep affected warm q14/q03/q06 and cold model loading. Preregistered repair-plan repeats both sides of every affected case/repetition and all18 cold slots under a process-scoped idle sleep assertion. Added epoch wall clocks agree with monotonic clocks within1second; OS caches were not cleared.

Offline verification overlapped portions of the original warm measurements; host load was not globally controlled. Small paired differences are descriptive, not proof of framework-caused speed changes. Resource reports exclude shared model-service memory from Python RSS.

BM25 order/cache confounding: bm25-order-observations.json shows c01 first-in-pair prompt evaluation around3.2seconds versus about0.08seconds second, whichever implementation runs first. c03 shows about1.9seconds versus0.08seconds, and meal about0.78seconds versus0.08seconds. Three repetitions per case imply a2/1 first-position split even though the overall schedule is balanced. Thus the BM25 paired medians above are observed workflow differences, not an estimate of LangChain overhead. Dense also switches embedding/generation models; its observed90.7–486.0ms paired median differences do not isolate a causal framework cost.

Paired-delta median is computed from each B−A pair; it need not equal median(B)−median(A). Cold q03 illustrates this. Warm/cold, retriever and corpus are not pooled into a single speed percentage.
