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
- `d680a27` — live Voyage/Anthropic Stage 2 development gate, calibrated retrieval policy, bounded free-tier rate-limit handling, and retained support-decision failures.
- `5686d4a` — locked holdout recorded and obsolete generated-note retrieval authority removed.
- `c08d12b` — scenario harness migrated to indexed original-source fixtures.
- `8c08f82` — RAG operations/configuration documentation and evidence-based convergence handoff.
- `cd12540` — source-grounded visual Ask requests no longer false-refuse on weak imperative-query similarity; visual provenance is objective-scoped and the authoritative visual survives response replanning.
- `84cde27` — structured retrieval, source-index, and tutor-fallback operational logging.
- `33037f3` — checked-in untouched 312-block CC0 origin holdout fixture.
- `7ed97d8` — source-backed prerequisite inference, browser-complete branch/repair/return, evidence-preserving branch transitions, and final response-step/cursor compatibility deletion.

## Plan status

### Completed

- Phase 0: baseline and database identity verified; unrelated dirty Learn-plan files preserved.
- Phase 1: current-generation `LearningBlock` corpus persistence, ownership/provenance, diagnostic-source rejection, re-upload invalidation, deletion behavior, and source-index status.
- Phase 2 (offline implementation): deterministic/Voyage provider contract, vector validation, indexing lifecycle, bounded retry/lease behavior, stale-worker rejection, and local retry command.
- Phase 3: exact cosine retrieval scoped by owner, document, and generation; deterministic anchor/semantic selection; bounded source serialization; explicit retrieval statuses.
- Phase 4 runtime checkpoint: indexed sessions retain `sourceGeneration`; response/continue diagnosis and tutor decisions receive retrieved original source evidence; retrieval outages fail without advancing learner state.
- Phase 5: indexed Ask answers, examples, visuals, and inline interaction grading use retrieved original blocks; Ask remains evidence-neutral; invalid model source references safely refuse; READY-index quiz navigation uses source retrieval rather than lexical guessing; Learn exposes and waits for source-index readiness.

### Final acceptance status

Phases 6 and 7 are complete. The authorized checked-in CC0 Stage 2 corpus was indexed with Voyage `voyage-3-lite` at 512 dimensions and evaluated with Anthropic support decisions. The frozen development candidate (top-k 5, minimum similarity `0.50556`) achieved Recall@5 `1.000`, MRR `0.936`, complete evidence@5 `1.000`, and zero false support. The locked holdout was then evaluated once without tuning: Recall@5 `1.000`, MRR `0.905`, complete evidence@5 `1.000`, and zero false support. Three of seven supported holdout queries were conservatively refused and remain retained limitations.

Phase 8 has concrete real-browser evidence on both substantive CC0 domains. Pendulum visibly completed wrong-answer teaching, uncertainty support, tutor-directed visual stage/highlight adaptation, reduced-support independent application, transfer, and evidence-based completion. One fresh Satire session now contains Ask replacing the main visual, exact refresh persistence, the Ask-selected visual surviving the next learner response, wrong-answer teaching, explicit uncertainty support, intervening learning, scaffold fading, independent application, transfer, delayed review in a different representation, and an evidence-based outcome that leaves the repeatedly weak concept under `Next focus` instead of falsely claiming mastery. A near-topic unsupported Ask was separately refused without scene mutation. Evidence is gitignored under `.tmp/learn-golden/rag-v1/`.

Phase 9 convergence is implemented: generated SectionNote retrieval is no longer reachable from Ask, legacy unindexed sessions return a safe re-upload/restart response, stale tests now build indexed source fixtures, operations/configuration are documented, the unused scene-compiler `step_index` compatibility argument is removed, and `responseStepId` is no longer normalized into the public authoritative scene.

RAG V1 functional acceptance is complete. A fresh, real-browser CC0 Satire journey now proves the final prerequisite requirement without database manipulation: weak evidence on the source foundation led into the dependent interpretation objective; a misconception there branched to the source-backed foundation; Lucent displayed prerequisite explanation, visual, and a new bounded repair interaction; an exact browser refresh preserved revision 5 byte-for-byte at the API scene boundary; correct prerequisite evidence returned to the original objective at revision 6; and the next original-objective prediction recorded correct application evidence at revision 7. Parent failure evidence and repaired prerequisite evidence both remained present, and provenance moved from `section-1`/`learning-block-2` to `section-0`/`learning-block-1` during repair and back again on return.

The complete two-domain golden evidence remains valid. Pendulum session `4ff3f9e8-2d10-469a-a1f5-262c50276892` demonstrates cohesive source teaching, misconception remediation, explicit uncertainty support, autonomous visual stage/highlight adaptation, scaffold fading, independent application, transfer, delayed review, and evidence-based completion. Satire session `a9a4d3fa-2b2d-4fb8-9755-41a3a794378e` demonstrates grounded Ask mutation, exact refresh persistence, Ask-selected visual persistence across a response, wrong-answer teaching, uncertainty support, intervening learning, scaffold fading, independent application, transfer, delayed review in a different representation, and evidence-sensitive completion. The post-cleanup Pendulum smoke (session `1e481372-caea-454f-972e-62153eead2af`) reconfirmed source teaching/practice, wrong-answer teaching-before-retest, Ask replacing `Energy and Motion Across the Swing` with the grounded `Ideal vs. Real Pendulums` visual, and exact visual/interaction persistence after refresh.

### Remaining work from `docs/RAG_V1_TECHNICAL_PLAN.md`

No functional RAG V1 implementation or browser-acceptance requirement remains. The following are release/operations follow-ups rather than acceptance gaps:

1. Before external rollout, confirm provider retention/processing terms for real student content; current authorization covers only the checked-in CC0 benchmark fixtures.
2. Improve the conservative support-decision false-refusal rate only through a new development experiment and a new untouched holdout; do not tune against the consumed Stage 2 holdout.
3. Run the disposable-database Alembic downgrade/upgrade smoke only if release policy requires downgrade proof. The active PostgreSQL database is at `0010_persist_learning_blocks (head)`.

## Known limitations and blockers

- The no-payment Voyage project is limited to 3 RPM and 10K TPM. Bounded backoff makes evaluation reliable, but measured total p95 latency is about 62 seconds under this tier; exact search p95 remains below 1 ms.
- Two supported development queries are conservatively refused by the support judge despite retrieving the gold block first: `s07-narrator-author` and `c05-direct-placement`. They remain explicit retained failures; the declared recall/MRR and zero-false-support gates still pass.
- Authorization was provided for sending the checked-in CC0 benchmark fixtures to Voyage and Anthropic. This does not authorize sending real student documents; provider retention/processing terms remain an external release gate.
- The support judge is deliberately conservative: two development and three holdout supported queries were refused despite successful retrieval. No false support was observed.

## Final validation

- Final post-convergence backend checkpoint: `406 passed, 7 warnings`.
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
- Focused Learn plan/scene/runtime/API convergence group: `96 passed, 7 warnings`.
- Fresh browser prerequisite evidence: `.tmp/learn-golden/rag-v1/prerequisite-final/01-foundation.png` through `08-original-objective-success.png`, with machine-readable assertions in `journey-result.json` (gitignored because browser artifacts contain source excerpts and development identifiers).
- Final Pendulum smoke evidence: `.tmp/learn-golden/rag-v1/pendulum-final-post-cleanup/`, including initial teaching, wrong-answer remediation, Ask visual replacement, and exact refresh persistence.
- `git diff --check` passed before staging.

## Recommended next action

Treat RAG V1 as functionally accepted. The next release action is the external provider retention/processing review before any real student material is enabled. Keep the current Stage 2 holdout frozen; any future false-refusal tuning requires a new development experiment and a new untouched holdout.
