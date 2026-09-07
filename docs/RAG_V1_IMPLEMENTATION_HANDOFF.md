# RAG V1 implementation handoff

Updated: 2026-09-07
Branch: `feature/public-auth-flow`

## Stable checkpoints

- `a4b46cd` — authoritative RAG V1 technical plan.
- `c18afd1` — persisted source corpus, generation/status lifecycle, embedding provider seam, indexing lease/retry safety, and migration `0010_persist_learning_blocks`.
- `a7f1ac4` — one owned, document-scoped exact retriever with bounded query formation, provenance, context budgets, and typed weak/failure results.
- `c34e904` — primary Learn and Ask runtime retrieval integration using original source text and persisted source generations.
- Current checkpoint — Ask support/provenance validation, attachment-aware prompt serialization, valid JSON truncation, and the first reproducible retrieval-evaluation harness.

## Plan status

### Completed

- Phase 0: baseline and database identity verified; unrelated dirty Learn-plan files preserved.
- Phase 1: current-generation `LearningBlock` corpus persistence, ownership/provenance, diagnostic-source rejection, re-upload invalidation, deletion behavior, and source-index status.
- Phase 2 (offline implementation): deterministic/Voyage provider contract, vector validation, indexing lifecycle, bounded retry/lease behavior, stale-worker rejection, and local retry command.
- Phase 3: exact cosine retrieval scoped by owner, document, and generation; deterministic anchor/semantic selection; bounded source serialization; explicit retrieval statuses.
- Phase 4 runtime checkpoint: indexed sessions retain `sourceGeneration`; response/continue diagnosis and tutor decisions receive retrieved original source evidence; retrieval outages fail without advancing learner state.

### Current phase

Phase 5/6 boundary. Shared Ask grounding is implemented for the main model path, including allowlisted source-block validation and a safe unsupported-source refusal. The Phase 6 harness can load fixed development/holdout examples, prevent query-family leakage, score Recall@1/3/5, MRR, complete evidence, false support/refusal, latency, and compare retained failures. It has unit coverage and an explicit runner, but it does not yet have the real Stage 1/Stage 2 annotated manifests or measured Voyage artifacts.

### Remaining work from `docs/RAG_V1_TECHNICAL_PLAN.md`

1. Finish Phase 5: ground inline Ask behavior where source evidence is required, finish narrow quiz/document association, add frontend index-status handling, and prove Ask visual/example mutations against raw blocks without evidence writes.
2. Finish Phase 6: build manually checked Stage 1 and Stage 2 datasets from approved substantive sources, lock query-family splits/holdout, run the fake reproducibility check and explicit Voyage baseline, and retain failure artifacts without committing private source text.
3. Phase 7: run one-variable retrieval experiments, record keep/revert decisions, freeze configuration/thresholds, and evaluate the locked holdout once at the candidate gate.
4. Phase 8: execute both fresh uploaded-source browser journeys, verify visible claims and unsupported behavior against original pages, and capture refresh/auth/provenance evidence.
5. Phase 9: delete only retrieval paths made obsolete by RAG (including the temporary generated-note fallback after legacy migration), update operations/configuration docs, run disposable-database migration smoke, full backend/frontend validation, and final browser regression.

## Known limitations and blockers

- `VOYAGE_API_KEY` is not configured locally. This prevents the required live provider smoke and measured semantic baseline; offline implementation and tests remain usable.
- Provider retention/processing approval and benchmark redistribution rights are external release gates and have not been established.
- No learner-facing browser acceptance is claimed for RAG V1 yet.
- Stage 1/Stage 2 gold manifests, frozen thresholds, measured baseline, and controlled experiment log do not yet exist.
- The generated-note retrieval helper is intentionally still present for legacy sessions and must be removed at the Phase 9 convergence gate, not used as evidence for new indexed sessions.
- Frontend source-index status/error UX and the narrow quiz convergence work remain open.

## Validation at this checkpoint

- Full backend: `383 passed, 7 warnings`.
- Focused DOCX/PPTX regression rerun: `2 passed` after replacing non-substantive stub fixtures with valid source sentences; the substantive-source production guard was not weakened.
- Python compilation: `venv/bin/python -m compileall -q app scripts` passed.
- Migration heads/current: both `0010_persist_learning_blocks (head)` on PostgreSQL.
- Frontend was unchanged in this checkpoint; its earlier Phase 0 baseline was `124 passed`, with TypeScript and production build passing.
- `git diff --check` should be rerun after this file is committed.

## Recommended next action

Resume at Phase 5, beginning with the remaining inline Ask and quiz/document grounding paths. Add captured-provider tests proving those prompts use retrieved original blocks, then finish the frontend index-status contract before creating any benchmark data. Do not begin retrieval tuning until Stage 1/Stage 2 annotations and fixed splits are committed.
