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
- Current checkpoint — locked, redistributable Stage 1/Stage 2 benchmark manifests with strict source/gold validation and expanded metrics.

## Plan status

### Completed

- Phase 0: baseline and database identity verified; unrelated dirty Learn-plan files preserved.
- Phase 1: current-generation `LearningBlock` corpus persistence, ownership/provenance, diagnostic-source rejection, re-upload invalidation, deletion behavior, and source-index status.
- Phase 2 (offline implementation): deterministic/Voyage provider contract, vector validation, indexing lifecycle, bounded retry/lease behavior, stale-worker rejection, and local retry command.
- Phase 3: exact cosine retrieval scoped by owner, document, and generation; deterministic anchor/semantic selection; bounded source serialization; explicit retrieval statuses.
- Phase 4 runtime checkpoint: indexed sessions retain `sourceGeneration`; response/continue diagnosis and tutor decisions receive retrieved original source evidence; retrieval outages fail without advancing learner state.
- Phase 5: indexed Ask answers, examples, visuals, and inline interaction grading use retrieved original blocks; Ask remains evidence-neutral; invalid model source references safely refuse; READY-index quiz navigation uses source retrieval rather than lexical guessing; Learn exposes and waits for source-index readiness.

### Current phase

Phase 6, partially complete. The repository now contains an original CC0 fixture corpus spanning physics/PDF, humanities/DOCX, and computer architecture/PPTX. Stage 1 has 24 queries across two domains; Stage 2 extends it to 50 queries across three domains with a locked 38-development/12-holdout split. Every supported gold evidence set has validated source block IDs and exact quotation offsets (plus pages for PDF evidence), including conjunctive multi-block requirements. The evaluator reports raw and final Recall/Hit@1/3/5, MRR, complete evidence, abstention/refusal, per-document/category macros, and embedding/search/total latency. The explicit live runner and measured Voyage artifacts are not yet complete.

### Remaining work from `docs/RAG_V1_TECHNICAL_PLAN.md`

1. Finish Phase 6: tighten `scripts/evaluate_retrieval.py` to the required `--config` and retained baseline/artifact contract; add deterministic local fixture seeding; run the fake reproducibility check; then run the explicit Voyage smoke/baseline when credentials are available. Do not label fake-vector results as semantic quality.
2. Phase 7: run one-variable retrieval experiments, record keep/revert decisions, freeze configuration/thresholds, and evaluate the locked holdout once at the candidate gate.
3. Phase 8: execute both fresh uploaded-source browser journeys, verify visible claims and unsupported behavior against original pages, and capture refresh/auth/provenance evidence.
4. Phase 9: delete only retrieval paths made obsolete by RAG (including the temporary generated-note fallback after legacy migration), update operations/configuration docs, run disposable-database migration smoke, full backend/frontend validation, and final browser regression.

## Known limitations and blockers

- `VOYAGE_API_KEY` is not configured locally. This prevents the required live provider smoke and measured semantic baseline; it does not block the remaining offline runner/seeding work.
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
- Frontend: `124 passed`; TypeScript and production build passed.
- Python compilation: `venv/bin/python -m compileall -q app scripts` passed.
- Migration heads/current: both `0010_persist_learning_blocks (head)` on PostgreSQL.
- `git diff --check` passed before staging.

## Recommended next action

Resume Phase 6 by tightening `backend/scripts/evaluate_retrieval.py` to require `--config`, retain complete per-query ranks/context/timings and fixed/regressed IDs, and record reproducible metadata. Add the smallest deterministic local fixture-seeding path, then produce the fake-provider mechanics baseline. The first live semantic action is the explicit Voyage smoke/baseline once `VOYAGE_API_KEY` and processing approval are available; only then begin Phase 7 tuning.
