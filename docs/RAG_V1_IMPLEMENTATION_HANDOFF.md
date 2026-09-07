# RAG V1 implementation handoff

Updated: 2026-09-07
Branch: `feature/public-auth-flow`

## Stable checkpoints

- `a4b46cd` — authoritative RAG V1 technical plan.
- `c18afd1` — persisted source corpus, generation/status lifecycle, embedding provider seam, indexing lease/retry safety, and migration `0010_persist_learning_blocks`.
- `a7f1ac4` — one owned, document-scoped exact retriever with bounded query formation, provenance, context budgets, and typed weak/failure results.
- `c34e904` — primary Learn and Ask runtime retrieval integration using original source text and persisted source generations.
- `b041e4b` — Ask support/provenance validation, attachment-aware prompt serialization, valid JSON truncation, and the first reproducible retrieval-evaluation harness.
- Current checkpoint — complete indexed-session Ask/quiz convergence and learner-facing source-index readiness handling.

## Plan status

### Completed

- Phase 0: baseline and database identity verified; unrelated dirty Learn-plan files preserved.
- Phase 1: current-generation `LearningBlock` corpus persistence, ownership/provenance, diagnostic-source rejection, re-upload invalidation, deletion behavior, and source-index status.
- Phase 2 (offline implementation): deterministic/Voyage provider contract, vector validation, indexing lifecycle, bounded retry/lease behavior, stale-worker rejection, and local retry command.
- Phase 3: exact cosine retrieval scoped by owner, document, and generation; deterministic anchor/semantic selection; bounded source serialization; explicit retrieval statuses.
- Phase 4 runtime checkpoint: indexed sessions retain `sourceGeneration`; response/continue diagnosis and tutor decisions receive retrieved original source evidence; retrieval outages fail without advancing learner state.
- Phase 5: indexed Ask answers, examples, visuals, and inline interaction grading use retrieved original blocks; Ask remains evidence-neutral; invalid model source references safely refuse; READY-index quiz navigation uses source retrieval rather than lexical guessing; Learn exposes and waits for source-index readiness.

### Current phase

Phase 6. The evaluation harness can load fixed development/holdout examples, prevent query-family leakage, score Recall@1/3/5, MRR, complete evidence, false support/refusal, latency, and compare retained failures. It has unit coverage and an explicit runner, but it does not yet have the real Stage 1/Stage 2 annotated manifests or measured Voyage artifacts.

### Remaining work from `docs/RAG_V1_TECHNICAL_PLAN.md`

1. Finish Phase 6: build manually checked Stage 1 and Stage 2 datasets from approved substantive sources, lock query-family splits/holdout, run the fake reproducibility check and explicit Voyage baseline, and retain failure artifacts without committing private source text.
2. Phase 7: run one-variable retrieval experiments, record keep/revert decisions, freeze configuration/thresholds, and evaluate the locked holdout once at the candidate gate.
3. Phase 8: execute both fresh uploaded-source browser journeys, verify visible claims and unsupported behavior against original pages, and capture refresh/auth/provenance evidence.
4. Phase 9: delete only retrieval paths made obsolete by RAG (including the temporary generated-note fallback after legacy migration), update operations/configuration docs, run disposable-database migration smoke, full backend/frontend validation, and final browser regression.

## Known limitations and blockers

- `VOYAGE_API_KEY` is not configured locally. This prevents the required live provider smoke and measured semantic baseline; offline implementation and tests remain usable.
- Provider retention/processing approval and benchmark redistribution rights are external release gates and have not been established.
- No learner-facing browser acceptance is claimed for RAG V1 yet.
- Stage 1/Stage 2 gold manifests, frozen thresholds, measured baseline, and controlled experiment log do not yet exist.
- The generated-note retrieval helper is intentionally still present for legacy sessions and must be removed at the Phase 9 convergence gate, not used as evidence for new indexed sessions.
- The frontend status contract has component/build coverage but still needs real browser observation during Phase 8.

## Validation at this checkpoint

- Previous full backend checkpoint: `383 passed, 7 warnings`.
- Phase 5 focused backend group: `29 passed, 7 warnings`.
- Indexed quiz/inline Ask focused group: `8 passed, 7 warnings`.
- Frontend: `124 passed`; TypeScript and production build passed.
- Python compilation: `venv/bin/python -m compileall -q app scripts` passed.
- Migration heads/current: both `0010_persist_learning_blocks (head)` on PostgreSQL.
- `git diff --check` passed before staging.

## Recommended next action

Resume at Phase 6 by choosing approved, redistributable substantive fixtures and authoring the 20–30-query Stage 1 manifest with verified block IDs, spans/pages, supported and unsupported cases. Tighten the CLI to the plan's full artifact/config contract while running the fake reproducibility check. Do not tune retrieval until Stage 2 fixed splits are committed.
