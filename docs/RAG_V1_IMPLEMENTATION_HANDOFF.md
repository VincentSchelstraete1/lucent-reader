# RAG V1 implementation handoff

Updated: 2026-09-07
Branch: `feature/public-auth-flow`

## Stable checkpoints

- `a4b46cd` — authoritative RAG V1 technical plan.
- `c18afd1` — persisted source corpus, generation/status lifecycle, embedding provider seam, indexing lease/retry safety, and migration `0010_persist_learning_blocks`.
- `a7f1ac4` — one owned, document-scoped exact retriever with bounded query formation, provenance, context budgets, and typed weak/failure results.
- `c34e904` — primary Learn and Ask runtime retrieval integration using original source text and persisted source generations.
- `b041e4b` — Ask support/provenance validation, attachment-aware prompt serialization, valid JSON truncation, and the first reproducible retrieval-evaluation harness.
- `84f542d` — complete indexed-session Ask/quiz convergence and learner-facing source-index readiness handling.
- `462155a` — locked, redistributable Stage 1/Stage 2 benchmark manifests with strict source/gold validation and expanded metrics.
- `e810376` — reproducible local fixture seeding, raw/final retriever instrumentation, and the complete evaluation CLI/artifact contract.
- Current checkpoint — live Voyage/Anthropic Stage 2 development gate, calibrated retrieval policy, bounded free-tier rate-limit handling, and retained support-decision failures.

## Plan status

### Completed

- Phase 0: baseline and database identity verified; unrelated dirty Learn-plan files preserved.
- Phase 1: current-generation `LearningBlock` corpus persistence, ownership/provenance, diagnostic-source rejection, re-upload invalidation, deletion behavior, and source-index status.
- Phase 2 (offline implementation): deterministic/Voyage provider contract, vector validation, indexing lifecycle, bounded retry/lease behavior, stale-worker rejection, and local retry command.
- Phase 3: exact cosine retrieval scoped by owner, document, and generation; deterministic anchor/semantic selection; bounded source serialization; explicit retrieval statuses.
- Phase 4 runtime checkpoint: indexed sessions retain `sourceGeneration`; response/continue diagnosis and tutor decisions receive retrieved original source evidence; retrieval outages fail without advancing learner state.
- Phase 5: indexed Ask answers, examples, visuals, and inline interaction grading use retrieved original blocks; Ask remains evidence-neutral; invalid model source references safely refuse; READY-index quiz navigation uses source retrieval rather than lexical guessing; Learn exposes and waits for source-index readiness.

### Current phase

Phase 6 is complete, including the authorized external live-provider gate. The original CC0 Stage 2 corpus was indexed with Voyage `voyage-3-lite` at 512 dimensions and evaluated with Anthropic support decisions. The reliable development baseline achieved Recall@5 `1.000`, MRR `0.936`, complete evidence@5 `1.000`, and zero false support. A first run exposed the no-payment project's 3-RPM limit; bounded 429 backoff now prevents throttling from becoming false retrieval failure. The evaluator also retains supported false refusals as failures. Phase 7 development work is frozen at top-k 5 and calibrated minimum similarity `0.50556`; the candidate preserves the baseline quality/safety metrics with two explicit conservative false refusals. The one allowed locked holdout run is next.

### Remaining work from `docs/RAG_V1_TECHNICAL_PLAN.md`

1. Complete Phase 7 by evaluating the locked 12-query holdout exactly once with the frozen candidate and recording the result without tuning against it.
2. Phase 8: execute both fresh uploaded-source browser journeys, verify visible claims and unsupported behavior against original pages, and capture refresh/auth/provenance evidence.
3. Phase 9: delete only retrieval paths made obsolete by RAG (including the temporary generated-note fallback after legacy migration), update operations/configuration docs, run disposable-database migration smoke, full backend/frontend validation, and final browser regression.

## Known limitations and blockers

- The no-payment Voyage project is limited to 3 RPM and 10K TPM. Bounded backoff makes evaluation reliable, but measured total p95 latency is about 62 seconds under this tier; exact search p95 remains below 1 ms.
- Two supported development queries are conservatively refused by the support judge despite retrieving the gold block first: `s07-narrator-author` and `c05-direct-placement`. They remain explicit retained failures; the declared recall/MRR and zero-false-support gates still pass.
- Provider retention/processing approval and benchmark redistribution rights are external release gates and have not been established.
- No learner-facing browser acceptance is claimed for RAG V1 yet.
- A measured live baseline, frozen thresholds/configuration, and controlled experiment log do not yet exist.
- The generated-note retrieval helper is intentionally still present for legacy sessions and must be removed at the Phase 9 convergence gate, not used as evidence for new indexed sessions.
- The frontend status contract has component/build coverage but still needs real browser observation during Phase 8.

## Validation at this checkpoint

- Previous full backend checkpoint: `383 passed, 7 warnings`.
- Phase 5 focused backend group: `29 passed, 7 warnings`.
- Indexed quiz/inline Ask focused group: `8 passed, 7 warnings`.
- Phase 6 evaluator/manifest tests: `5 passed, 7 warnings`.
- Retrieval/index regression slice (`test_retrieval_evaluation`, `test_retrieval`, `test_embeddings`, `test_source_index`, `test_learning_block`, `test_route_learning_block`): `17 passed`.
- Direct manifest integrity check: Stage 1 loaded 24 examples (20 development/4 holdout); Stage 2 loaded 50 examples (38 development/12 holdout) across all three declared domains/types.
- Current Phase 6 retrieval/index slice: `19 passed`.
- Full backend after the support-decision boundary: `390 passed, 7 warnings`.
- Focused evaluator/retriever slice after the support-decision boundary: `13 passed, 7 warnings`.
- Explicit fake-provider mechanics baselines completed locally under `.tmp/rag-eval/` (gitignored because artifacts contain excerpts and database IDs). Stage 1 development: Recall@1/3/5 `0.583/0.917/1.000`, MRR `0.789`; Stage 2 development: Recall@1/3/5 `0.629/0.900/1.000`, MRR `0.796`. Both correctly report false-support `1.000` and semantic-quality `false`; deterministic hash vectors are not a support/answerability model.
- Frontend: `124 passed`; TypeScript and production build passed.
- Python compilation: `venv/bin/python -m compileall -q app scripts` passed.
- Migration heads/current: both `0010_persist_learning_blocks (head)` on PostgreSQL.
- `git diff --check` passed before staging.

## Recommended next action

Run the locked Stage 2 holdout exactly once with the frozen hash-locked Voyage/Anthropic candidate. Record the result without tuning against holdout, then proceed to the two fresh uploaded-source browser journeys.
