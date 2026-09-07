# RAG V1 retrieval experiment log

Dataset: `rag-v1-stage2`  
Development split: 38 queries (35 supported, 3 unsupported)  
Embedding configuration: Voyage `voyage-3-lite`, 512 dimensions, `learning-block-input-v1`  
Support configuration: Anthropic `claude-haiku-4-5-20251001`, `rag-source-support-v1`

Local artifacts containing excerpts and database IDs remain under `.tmp/rag-eval/` and are intentionally gitignored.

## Live baseline

Artifact: `stage2-voyage-development-baseline-reliable.json`

- Recall@1/3/5: `0.814 / 0.971 / 1.000`
- MRR: `0.936`
- Complete evidence@5: `1.000`
- False support / correct abstention: `0.000 / 1.000`
- Supported false refusal: `0.057` (2/35: `s07-narrator-author`, `c05-direct-placement`)
- Search p50/p95: `0.48 / 0.71 ms`
- Total p50/p95: `158.54 / 62026.04 ms`

The high total p95 is provider admission latency on a no-payment Voyage project limited to 3 RPM, not local exact-search latency. The client now applies bounded 429 backoff rather than misclassifying throttled requests as retrieval failures.

## Experiment 1 — more permissive inference wording in support judge

Hypothesis: explicitly allowing faithful paraphrases and one-step unavoidable inferences would fix the two supported false refusals without increasing false support.

Only variable changed: Anthropic support instruction. Retrieval query, embeddings, source serialization, top-k, and models remained fixed.

Result:

- Ranking metrics unchanged.
- False support remained `0.000`.
- Supported false refusal regressed from `0.057` (2/35) to `0.114` (4/35).
- New false refusals: `s06-parody-distinction`, `c17-miss-rate-only`; the original two remained.

Decision: **revert**. The instruction made the judge more conservative without a safety benefit.

## Cutoff calibration and frozen candidate

All 38 observed development top-score boundaries were evaluated using the same bounded support decisions. Among cutoffs meeting the zero-false-support safety gate, `0.50556` is the most conservative boundary with the minimum observed supported false-refusal rate (`0.057`). The cutoff is scoped to the exact calibrated provider/model/dimensions and query/input policy; other providers default to no calibrated cutoff.

Frozen candidate:

- top-k: `5`
- minimum similarity: `0.50556`
- query version: `source-query-v1`
- retrieval version: `exact-cosine-v1`
- retrieval policy: `rag-retrieval-policy-v1`
- support policy: `rag-source-support-v1`

Candidate development result:

- Recall@1/3/5: `0.814 / 0.971 / 1.000`
- MRR / complete evidence@5: `0.936 / 1.000`
- False support / correct abstention: `0.000 / 1.000`
- Supported false refusal: `0.057`
- Retained failures: `s07-narrator-author`, `c05-direct-placement`

The candidate clears the declared V1 development gates. The two false refusals are retained as known conservative limitations rather than relabeled as retrieval misses.

## Locked holdout result

Artifact: `stage2-voyage-holdout-final.json`

The frozen candidate was evaluated once on the locked 12-query holdout (7 supported, 5 unsupported). No configuration was changed after observing it.

- Recall@1/3/5: `0.643 / 1.000 / 1.000`
- MRR / complete evidence@5: `0.905 / 1.000`
- False support / correct abstention: `0.000 / 1.000`
- Supported false refusal: `0.429` (3/7)
- Search p50/p95: `0.41 / 0.81 ms`
- Total p50/p95: `153.97 / 62033.56 ms`
- Retained false refusals: `s10-every-joke`, `c12-hit-miss-compare`, `c18-mapping-performance`

Decision: **accept the frozen retrieval candidate for V1 retrieval safety/ranking, while retaining conservative support refusal as a measured limitation.** The declared Recall@5, MRR, complete-evidence, and zero-false-support gates pass. The false refusals are not tuned against this holdout; improving the support decision requires a new development experiment and a new untouched holdout.
