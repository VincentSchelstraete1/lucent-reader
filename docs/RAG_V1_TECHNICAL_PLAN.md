# Lucent RAG V1 — Authoritative Technical Plan

Status: planning complete; implementation and measured acceptance **not yet performed**. Repository verification: 2026-09-06. This extends Claude's `important-context-rule-you-gleaming-lantern.md`; it does not restart Learn migration. New file/module names below are implementation targets, not claims that they already exist.

## 1. Context and verified corrections

Preserve `docs/LUCENT_LEARN_AUTHORITATIVE_SCENE_MIGRATION_PLAN.md`'s single-runtime, single-scene, single-visual-owner invariants and `docs/LEARN_GOLDEN_EXPERIENCE.md`'s learner-visible acceptance bar. `docs/LUCENT_LEARN_CONVERGENCE_HANDOFF.md` is historical context, not current implementation evidence. In particular, its statement that Ask never enters the event runtime is outdated: Ask now supplies an `ASK_LUCENT` payload to `process_tutor_event`, although model orchestration remains in the router.

Verified against current code:

- Ingestion computes `LearningBlock`s but `_persist_learning_note()` in `routers/ingestion.py` stores Document markdown and SectionNote JSON, not these blocks. `SectionNote.sourceBlockIds` therefore cannot be resolved to persisted original evidence.
- `segmentation/schema.py` provides text, local block ID, normalized block IDs, heading ancestry, source page/bbox/location references, segmentation metadata, and attachment IDs. Preferred sizing is not a promise that every block contains useful prose. `assemble_learning_block_text()` excludes headings, tables, and images: **do not claim block text includes table cells or figure pixels**.
- `routers/learn.py::submit_learn_response()` does not supply source blocks. `learn_runtime.build_tutor_observation()` defaults them to an empty list. The primary `diagnose_response()` call passes joined block IDs as `source_context`. `choose_tutor_decision()` serializes the observation but receives no explicit source context there. The precise failure is missing original source text, not literally no information: generated notes, scene content, and candidate answers still influence tutoring.
- `services/retrieval.py::retrieve_note_context()` ranks generated SectionNote summaries lexically; Ask's `_objective_context()` then overwrites the result with objective summaries. Replacing the scoring algorithm alone cannot fix this.
- `routers/quizzes.py::_associate_question()` has duplicated lexical overlap, but it assigns **review navigation**, not factual support. Removing it alone does not ground quizzes. Full quiz-generation redesign and its potentially unbounded prompt remain outside V1.
- Ownership is `Document.source_id → Source.user_id`, not `Document.user_id`. Ingestion reuses documents by user-scoped upload source/filename; a repeated upload can change an existing document.
- Migration ancestry is `0002 → 30c016012cb8 → 0003 … → 0009_drop_learn_step_index`. The repair migration is not a second head. Attach the new migration to the actual head confirmed at implementation time, not a guessed revision.
- Current Ask semantics distinguish an **additional inline question** (another/harder) from **replacement of primary practice** (simpler). Preserve this current contract despite older golden prose permitting replacement for “another.” Inline answers are explicit events, not a second progression engine.

Claude's PostgreSQL 17.11/no-vector report is retained as a prior environment observation, not a fresh database probe in this planning pass. Its 1–2 ms search estimate is unmeasured here. Exact search is appropriate for the proposed scope independently of extension availability. Also, **embedding-model changes can re-embed persisted text without original files**; only extraction/resegmentation requires re-upload in this scope.

## 2. Preserved decisions, rationale, and boundaries

1. **Corpus: existing LearningBlocks.** Persist the cleaned, structure-aware pipeline output with provenance. Reject generated SectionNotes as evidence, a raw-markdown replacement corpus, and a second RAG chunker. Revisit boundaries only if annotated retrieval failures demonstrate a segmentation problem; first test neighboring blocks.
2. **Embeddings: Voyage `voyage-3-lite`, initially 512 dimensions.** Isolate vendor configuration and calls behind an injected provider; confirm availability/dimensions with a live smoke test before indexing. Keep environment-based configuration consistent with existing services. Reject new local torch dependencies and premature provider experimentation. Revisit the model only after controlled evaluation identifies model quality as the bottleneck; no unverified price/performance claims.
3. **Storage/search: ordinary Postgres JSONB vectors, exact Python cosine, one document.** No extension or external vector database. At approximately 50–500 blocks, simplicity outweighs ANN infrastructure. Benchmark total latency, including database and query embedding. A future storage/search adapter can adopt pgvector without changing tutor interfaces; installation alone is not a migration plan. Revisit for measured scale problems or a separately authorized cross-document product.
4. **Persist blocks, not original files; no legacy corpus backfill.** Older documents require re-upload. Persisted block inputs support model reindexing. Do not reconstruct source from generated notes or pretend Document markdown has equivalent provenance.
5. **One tutor.** Retrieval supplies evidence to the existing `TutorObservation → TutorDecision → scene execution` path. It does not select the next concept, change evidence, grade, complete sessions, or own visuals.

Non-goals: AWS/deployment, original-file/object storage, ANN, hybrid search, rerankers, web/cross-document retrieval, knowledge graphs, multi-agent/multi-hop retrieval, a RAGTutor, broad Learn cleanup, visual/pedagogy redesign, or unrelated Notes/Quiz prompt rewrites. A failing golden checkpoint is fixed at its relevant integration boundary, not by weakening acceptance.

## A. Persisted corpus and data model

Add SQLAlchemy models in `backend/app/models/learning_block.py`, export them through `models/__init__.py`, and create one Alembic migration. Use the same types under `Base.metadata.create_all` in tests.

### `document_source_indexes` — one row per document

| Column | Type / contract |
| --- | --- |
| document_id | Integer PK, FK documents.id, ON DELETE CASCADE |
| generation_id | UUID, not null; changes whenever corpus content/provenance changes |
| corpus_hash | CHAR(64), SHA-256 of canonical ordered source records |
| normalization_version, segmentation_version | TEXT, explicit pipeline versions |
| embedding_input_version | TEXT, initially `learning-block-input-v1` |
| status | VARCHAR with CHECK: PENDING, INDEXING, READY, FAILED |
| provider, model, dimensions | TEXT, TEXT, positive Integer; intended active configuration |
| block_count, embedded_count | Nonnegative Integer, embedded_count <= block_count |
| attempt_id | Nullable UUID, indexing lease/compare-and-swap token |
| attempt_count | Nonnegative Integer |
| lease_expires_at | Nullable timezone timestamp |
| failure_code | Nullable bounded VARCHAR(64); never raw provider text |
| created_at, updated_at, indexed_at | Timezone timestamps; indexed_at nullable |

Add index `(status, lease_expires_at)` for local recovery. READY requires nonempty substantive corpus, all retrievable blocks embedded, and one model/input version. Enforce aggregate consistency in the publishing transaction; SQL CHECK alone cannot validate other rows.

### `learning_blocks` — current corpus only

| Column | Type / contract |
| --- | --- |
| document_id, block_id | Composite PK; document_id FK document_source_indexes.document_id ON DELETE CASCADE; block_id TEXT retains ingestion ID |
| generation_id | UUID, matches owning index; validated on writes/reads |
| ordinal | Nonnegative Integer, unique `(document_id, ordinal)` |
| block_type, title | TEXT; title nullable |
| text | TEXT, original cleaned LearningBlock text, never model prose |
| character_count, token_count | Integer; token_count nullable when unavailable |
| heading_ancestry, normalized_block_ids, section_ids | JSONB arrays of strings |
| source | JSONB exact SourceReference: page_start/end, raw_block_ids, bboxes, locations |
| segmentation | JSONB method, boundary_reason, version, confidence |
| attachments | JSONB bounded records for attached normalized tables/captions/image metadata |
| content_hash, embedding_input_hash | CHAR(64), canonical SHA-256 |
| embedding | Nullable JSONB numeric array; finite, positive norm, exact dimensions |
| embedded_at | Nullable timezone timestamp |

Composite PK and ordinal index suffice for single-document reads; no JSON/vector index. Model/version metadata belongs on the index row; blocks cannot mix embedding configurations. Source identity is `(document_id, generation_id, block_id)`, **never bare `b1`**. The block IDs consumed by existing scenes remain unchanged inside that scoped identity.

`section_ids` comes from existing grouping/mapping used to generate SectionNotes, not a new semantic segmenter. Persist that deterministic mapping; require note generation/version association to the same generation. Carry generation into SectionNote payload metadata and `LearnSession.state.sourceGeneration`; no second scene store.

Attachment policy: preserve existing normalized table text/cells under the owning block, and captions already available as source text. Embedding input is title + ancestry + block text + bounded normalized textual attachments in a versioned deterministic format. Do not regenerate table descriptions with a model or create independent RAG chunks. Preserve parent/attachment provenance and any truncation offsets. If a table-only block cannot be represented substantively within the input limit, flag unsupported coverage and block objectives requiring it; do not silently index only its heading. Figure pixels are not evidence in this text-only V1; caption-supported claims are allowed, unobserved diagram details are not. Document coverage warnings are structured status, never corpus prose.

Deletion cascades index/blocks/vectors within the same document-deletion transaction, including the existing manual deletion route. No global cache survives deletion. Check ownership through Source before any block/vector read or write; no redundant user ownership column.

Re-upload serializes updates on the existing document. Identical canonical corpus + versions is idempotent. Changed corpus atomically replaces current blocks and sets a new PENDING generation; never retain searchable old vectors. Mark existing active Learn sessions source-invalidated in the same transaction without deleting attempts/reports. Their next write returns `SOURCE_CHANGED`; GET must not relabel an old scene as current-source evidence or regenerate it. Show a clear “Source updated—start a new session” state; historical progress remains available as historical, not resumable instruction. Require matching generation for generated notes before allowing a new Learn session. Old documents with no index have NOT_INDEXED API status and a re-upload instruction, not fabricated blocks.

Add owned `GET /documents/{document_id}/source-index` returning only generation, public status (NOT_INDEXED/PENDING/INDEXING/READY/FAILED), counts, coverage warnings and safe retryability. It does not enqueue work or return chunks/vectors. The existing ingestion response may include the same status. New Learn starts return structured 409 for not-ready/source-changed conditions, 422 for unusable source, and retryable 503 for temporary embedding service failure. Do not serialize technical status codes as teaching blocks. Local indexing retry is initially CLI-only; no new production administrative endpoint is needed.

## B. Indexing lifecycle and transactions

`upload → existing extraction/normalization/segmentation → substantive validation → persist corpus(PENDING) → INDEXING → READY | FAILED`

Separate source persistence from generated-note persistence in `routers/ingestion.py`. All PDF, progressive PDF, DOCX, and PPTX routes must converge on the same corpus persistence service. Progressive ingestion currently keeps jobs in memory and opens its own DB session in `_run_progressive_job`; retain that lightweight scheduling mechanism, but make source/index status durable. Persist source before expensive note generation. Note failure does not discard valid source; indexing failure does not discard notes. Learn requires both usable notes and READY source of the same generation.

1. Short transaction: ownership, document identity, source validation, corpus replacement, generation/status update. Commit before any embedding network call.
2. BackgroundTasks invokes `index_document(document_id, generation_id)` with its **own SessionLocal**, never the request's closed session. Claim PENDING/FAILED or expired INDEXING via atomic update, assign attempt UUID and five-minute lease. Active attempts are not duplicated.
3. Read immutable bounded inputs, release transaction, embed batches. Renew lease between batches. Start with 32 inputs/batch, at most three transport attempts with exponential backoff/jitter; honor bounded Retry-After. Do not retry bad credentials/invalid input indefinitely.
4. Validate every returned vector before publish. Publish all vectors and READY in one short transaction conditioned on generation, attempt token, and document existence. No partial READY. A stale worker after delete/re-upload/retry discards its results.
5. Failure publishes only a sanitized failure code if the attempt still owns the generation. Incomplete work is not searchable. V1 retries the document, not a complex batch-resume system. A local CLI lists/retries PENDING/FAILED/expired INDEXING after process restart; durable state does not depend on progressive poll objects surviving restart.

Reindexing a model/input-version change uses the same lease mechanism and persisted source. Set INDEXING and make retrieval temporarily unavailable rather than mix dimensions. Preserve current scenes on transient indexing downtime, but block new source-dependent events with a retryable response; never recompose on GET. Reembedding unchanged corpus does not change source generation; input/config changes do change index metadata. Retrieval verifies the configured query model matches published vectors.

No successful learner event may be half committed because retrieval failed: fetch needed evidence before evidence/attempt mutation; on final persist recheck scene revision and source generation. Network calls must not hold database locks. Use the existing stale-event mechanism for concurrent Ask/answer/ingestion writes.

## C. Embedding provider contract

New `services/embeddings.py`:

```python
@dataclass(frozen=True)
class EmbeddingMetadata:
    provider: str
    model: str
    dimensions: int

class EmbeddingProvider(Protocol):
    metadata: EmbeddingMetadata
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
```

Voyage adapter sends document/query input types appropriately, uses explicit timeout (20 seconds per call), checks response ordering/count/dimensions/finite values, and returns L2-normalized vectors. Shared validation also protects injected implementations. Reject empty strings/zero vectors. Errors are typed `EmbeddingUnavailable`, `EmbeddingInvalidInput`, `EmbeddingInvalidResponse`; public handlers map them to safe messages, never `str(exception)`.

Use `get_embedding_provider()` and a resettable test injection seam. The fake uses fixed hashing of normalized tokens, not Python's randomized hash; hand-authored vectors test exact ranking. Fake rankings test mechanics, not semantic retrieval quality. Tests reset injected state after each case and never fall back to network.

Environment: `VOYAGE_API_KEY` (secret), `RAG_EMBEDDING_MODEL=voyage-3-lite`, `RAG_EMBEDDING_DIMENSIONS=512`, `RAG_EMBEDDING_TIMEOUT_SECONDS=20`, `RAG_EMBEDDING_BATCH_SIZE=32`. Validate config once; record metadata with every index. Add documented examples without keys. Use existing HTTP dependencies where adequate; otherwise add only the small vendor client, no ML framework. Conservative input cap: 6,000 UTF-8 bytes per document input and 1,200 characters per query, also respecting the provider's verified batch/token limits. Do not rely on character counts as exact token counts or enable silent provider truncation.

## D. One retrieval service

Replace the implementation/contract in `services/retrieval.py`, not a second Ask-only retriever:

```python
retrieve_source(
    db, *, user_id: UUID, document_id: int,
    expected_generation: UUID, query: SourceQuery,
    anchor_block_ids: Sequence[str] = (), top_k: int = 5,
) -> RetrievedSourceContext
```

`SourceQuery` contains purpose (initial/response/continue/ask/prerequisite/review), bounded text, and target objective ID. It is internal, constructed from validated runtime state. The result contains `status` (SUPPORTED, WEAK, NOT_INDEXED, INDEXING, FAILED, SOURCE_CHANGED), document/generation, query fingerprint, embedding metadata, ordered `blocks`, coverage/truncation flags, and timings. Unauthorized/missing documents return indistinguishable 404, not these status variants.

Each retrieved block includes `text`, `blockIds`, `sectionIds`, source page/location/bbox metadata, ordinal, rank, nullable cosine score, selection kind (semantic/anchor/neighbor), and exact excerpt offsets. These are original source excerpts, not generated summaries. Return no embedding arrays publicly. A typed adapter supplies the existing observation's `{text, sectionIds, blockIds}` shape with bounded provenance.

Algorithm: ownership + generation/status check → read only that document's published rows → embed query using matching model → exact dot product of unit vectors → descending score, ascending ordinal then ID for ties → dedupe block IDs → budget. Never select first section merely because all scores are weak. No hybrid or reranking. The storage seam `similarity_search(document_id, generation_id, vector, limit)` may later change without changing this contract.

Anchors resolve the current interaction/objective's validated source IDs first for grading/diagnosis. They are visibly distinguished internally from semantic hits and do not receive invented similarity scores. A broad objective reference must not fill the whole budget: maximum three anchors; if the interaction needs more source than fits, return incomplete evidence and do not semantically grade on an arbitrary subset. Semantic search uses the remaining slots. Start with adjacent expansion **off**; a later one-variable experiment may add one immediate neighbor per hit within the same section and budget. Never cross document/generation or merge away provenance. Exact duplicate text may share a rendered excerpt while retaining all IDs/offsets, not erase distinct source locations.

Weak-score policy is calibrated on dev supported/unsupported queries; similarity is not an entailment probability. Until calibration is frozen, score threshold alone cannot certify SUPPORTED. SUPPORTED means usable candidate evidence, followed by the claim-support contract below; unsupported answering still requires an explicit evidence check. No arbitrary numeric threshold is asserted as validated in this plan.

## E. Bounded query formation

Add a small pure `build_source_query()` in the retrieval module; no model rewriter or new agent loop. Priority within 1,200 characters:

1. Current authoritative objective/concept title and learning outcome (up to 350).
2. Active prompt or explicit Ask message (up to 450).
3. Learner response/uncertainty (up to 250).
4. Evidence target and most recent validated misconception, when available (remaining budget).

For IDK, use the concept/prompt; repeating “I don't know” adds no retrieval value. For “why was I wrong,” include the actual recent response and evaluated distinction. For visual/example/rephrase requests, include the concept/visual title, not just the generic intent. For prerequisite/review use the **validated target concept**, not the parent/current stale objective. Source instructions and learner strings remain untrusted data.

At most one retrieval before diagnosis/decision and one target-specific retrieval if the decision legitimately changes concept (prerequisite/review/advance). A previous diagnosis can inform the first query; a newly computed one does not cause unbounded query-rewrite loops. Retrieval never decides to branch or review.

## F. Learn integration — precise boundaries

`owned event → revision/generation validation → retrieve original evidence → diagnose/grade → bounded observation → existing tutor decision → target evidence if needed → validate/execute → commit scene + attempt/evidence`

- `routers/learn.py::create_learn_session`: require matching READY corpus and substantive generation-matched notes before `build_learn_plan`. Resolve each objective's source IDs; pass bounded source excerpts into existing plan/asset generation in `services/learn_engine.py`. Do not trust a summary solely because it cites an existing ID. Cover initial teaching/practice, distractors, expected answers, and visual claims. No whole-document prompt.
- `learn_runtime.process_tutor_event`: own retrieval orchestration for production events with DB context. Authenticate document/session in the route, independently scope retrieval by session user/document. Keep test injection of source context, but make production absence explicit rather than silently empty. Pure visual playback and STOP need no retrieval if they introduce no source claims.
- Replace the joined-ID `diagnose_response(source_context=...)` argument with serialized anchored original excerpts. Preserve deterministic grading/private expected-answer behavior; do not make a similarity score a grade.
- `build_tutor_observation`: populate sourceBlocks using one typed bounded adapter. Supply the **same retrieved context explicitly** to `choose_tutor_decision(context={"source": ...})`. Current `str(observation)[:6500]` can cut off critical evidence; serialize field-bounded JSON, omit duplicated source bodies from observation text, and keep source in its own section. Test the actual captured provider prompt, not only the Python observation.
- `services/learn_tutor.py`: diagnosis, decision, feedback, visual and practice generation receive delimited untrusted evidence and authorized IDs. Preserve bounded schemas. Validate source references at scene execution; new claim-bearing fallback content must resolve to this generation too.
- On target change, retrieve target evidence before composing; if unavailable do not fabricate prerequisite teaching or grade against parent evidence. Preserve the old scene and report a safe retry/source limitation without mutating progression. No LearnPlan appends, second observation builder, or retrieval-owned transition policy.
- Inline Ask answer events must receive their own interaction's source anchors, not accidentally grade against the primary practice. Persist source generation/references with the existing private interaction payload.

## G. Ask integration and narrow quiz convergence

Keep auth/ownership, CSRF, rate limit, and relevance checks in `ask_lucent`. Replace `retrieve_note_context(payload, ...)` and remove `_objective_context`'s summary-text override. Route the source-dependent Ask reasoning through the same runtime evidence preparation as normal events. Move only the router's necessary model/context preparation behind its existing ASK_LUCENT handling; do not introduce another tutor coordinator or preserve two competing source selections. The same context object feeds Ask answer, observation, visual/example generation, and validated scene execution.

Relevance checks may reject plainly unrelated requests early, but lexical mismatch must not reject a legitimate paraphrased question before retrieval. The source-support check handles unanswered in-domain questions. Another/harder adds the existing inline interaction; simpler intentionally replaces primary practice. Explain/example changes the designated teaching surface without stacking repeated answers. Visual requests keep using existing visual generation/state; retrieval supplies evidence, not a new renderer. Ask messages never mutate correctness/mastery, auto-answer practice, or advance just by being asked.

For quizzes, remove the competing lexical **provenance association** only: when provider section IDs are absent/invalid and READY corpus exists, use this retriever on question+explanation and map supported source hits to section IDs. If ambiguous/unavailable leave navigation unassociated rather than claim a false match. Do not relabel this as full raw-source quiz grounding. Valid section IDs remain navigation metadata, not factual proof. Full quiz prompt conversion is explicitly deferred; the no-index quiz path need not acquire a hidden dependency on Voyage or a guessed first-section link.

## H. Grounding and learner-language contract

Grounded content uses substantive original excerpts of the owned document/generation; cited references resolve; material claims are supported by those excerpts. Examples must be labeled as illustrative rather than falsely attributed quotations. Source IDs alone validate membership, **not semantic truth**. Use the existing structured model output to request support/abstention and references, enforce membership and learner-language validation in the executor, and audit factual support in evaluation/browser review. Do not claim structural validators eliminate hallucinations.

Treat document text as untrusted quoted data, never system instructions. Do not put extracted commands in instruction roles or allow them to change retrieval scope/tools. Source insufficiency, extraction errors, headings-only and placeholder content fail substantive corpus/plan validation before instruction begins. This is a generic typed quality boundary, not one blacklist phrase. Retain existing diagnostic-language checks as defense in depth.

Unsupported Ask: explain briefly that the uploaded material does not establish that answer; offer to work with what it does cover. No invented answer, forced nearest section, fabricated citation, or evidence mutation. Transient indexing/provider failure: safe retry status, not “the source says nothing.” Runtime errors, model rationale, vectors/scores, index statuses, tool arguments, “Insufficient Source Material,” and provider details must never become learning content. Existing valid scenes survive outages and GET unchanged.

## I. Context budget

- Default semantic top-k 5; caller cap 8 total source blocks including anchors/neighbors.
- Total source text at most 8,000 characters; at most 3,000 per excerpt. Heading/provenance serialization separately capped at 1,500 characters. Preserve excerpt offsets; cut at a safe boundary, never silently clip mid-table into a false relationship.
- Diagnosis gets a focused at-most-5,000-character subset supporting the active interaction; decision/Ask use up to 8,000. Replace conflicting current 4,000/5,000 blind slices with shared budgeting; bounded valid JSON must survive serialization.
- When evidence cannot fit, mark coverage incomplete and narrow/defer the task; never claim complete support. No full-document injection into Learn.
- Log estimated tokens and measured provider usage where available; character limits are engineering bounds, not token-exact guarantees.

## J. Observability and privacy

Structured internal event: request/session/event IDs, document/generation, query hash/purpose, model/input version, selection kind, retrieved IDs/rank/score, source page/section references, coverage flags, query embedding/search/total latency, status/failure code. Link to existing tutor event trace without exposing retrieval fields in learner blocks.

Raw query, learner responses, and source excerpts are off by default in logs. Opt-in local debug may retain redacted query/excerpts under `.tmp/rag-eval/`; never credentials, original files, or unrelated user data. Record sanitized failure category, not provider exception bodies. Logs are not a new persisted evidence/scene authority. No global embedding cache keyed only by text or block ID; V1 avoids a cache entirely.

## K. Evaluation harness

Create `backend/app/retrieval_eval/{dataset.py,evaluation.py}` and `backend/scripts/evaluate_retrieval.py`. Follow existing segmentation evaluation's injectable strategy + retained failure examples, routing evaluation's per-example results + fixed/regressed comparison, and dataset-loader validation patterns. Do not import labels from retrieval output or silently regenerate gold after segmenter changes.

Manifest schema: dataset/version, document ID alias and content hash, approved source fixture path, domain/type, query ID, query-family ID, fixed split, category, natural query, optional learner/objective context, supported boolean, gold evidence sets. Gold contains actual source quotation/span offsets/page plus verified block IDs and corpus hash. Alternative evidence sets represent equivalent support; multiple required spans represent multi-block answers. Human-author and inspect gold; a hash/span mismatch fails the run, not auto-relabels it.

Stages:

1. **20–30 queries, 2–3 real documents:** index/evaluator correctness and honest baseline. Include every requested category: factual, conceptual, paraphrase, adjacent/multi-block, confusing concepts, prerequisite, misconception, Ask-style, unsupported. Report sparse categories honestly, not as statistically robust findings.
2. **50–75 queries, >=3 domains and document types:** expand difficult cases and controlled dev experiments. Freeze document/query-family splits in a checked-in manifest. Keep paraphrase siblings together; avoid tuning and scoring near-duplicates as independent generalization.
3. **Later 100–150+ queries, 5–8 documents:** locked held-out subset including unseen documents. Stage 3 is future benchmark growth, not a prerequisite for V1. Stage 2 must nevertheless include a locked holdout before optimization. Holdout is evaluated at the frozen candidate gate, not each iteration. Once inspected/tuned against, retire it as holdout and obtain new untouched cases.

Metrics on supported queries: Recall@1/@3/@5 (fraction of gold relevant blocks recovered, best valid alternative evidence set), MRR (reciprocal rank of first relevant block), plus Hit@k and complete-evidence coverage for conjunctive multi-block questions. Score raw semantic rankings separately from final budgeted/anchor-expanded context so anchors cannot inflate the retrieval benchmark. State denominator, supported count, macro-by-document/category and aggregate values. Report p50/p95 embedding, search and total latency, with corpus size and cold/warm methodology. Do not mix fake-provider performance with live semantic quality.

Unsupported queries have no gold relevant block and are excluded from recall/MRR. Report false-support rate and correct abstention rate using an explicit answerability/support decision with manually reviewed borderline cases; also supported-query false-refusal. Similarity alone cannot establish that a question is answerable. Keep near-topic unsupported cases and deceptive source-instruction cases, not only unrelated easy negatives.

Artifacts: JSON run metadata (git revision, dataset/corpus hashes, config/model/provider versions), all per-query ranks and excerpts, missed gold, selected/omitted context, statuses/timings; Markdown summary and fixed/regressed IDs. Local private source excerpts stay gitignored; committed eval fixtures require permission/licensing. Tests use deterministic fake vectors; a separately invoked live embedding benchmark establishes semantic metrics.

## L. One-variable experiment protocol and release gate

Baseline → inspect retained failures → classify extraction/coverage, boundary, query, embedding, dedupe, budget, scope, or unsupported-decision issue → change **one major variable** → rerun identical dev manifest → compare → keep/revert. Start with query formation, metadata inclusion, adjacency, dedupe and top-k; model changes last. Do not optimize the tutor to memorize test answers or expand generation scope to hide retrieval failure.

For every experiment record hypothesis, variable/config diff, before/after metrics and latency, affected failure classes, newly broken query IDs, decision and rationale. Select calibration/weak-score policy on dev only and freeze with the candidate config before holdout. No unsupported threshold is tuned on holdout.

Calibration procedure: evaluate candidate cosine cutoffs at observed dev score boundaries with the same bounded support/abstention decision; choose the cutoff with the lowest supported false-refusal among those meeting the unsupported safety gate, breaking ties toward the more conservative cutoff. Persist the selected cutoff with model/input/query versions. If no cutoff meets the gate, classify the unsupported failures and repair source-support handling rather than force a threshold or claim cosine proves entailment. A model or query-policy change invalidates calibration and requires a new dev run.

Proposed V1 gates, declared before baseline: supported Recall@5 >=0.85 and MRR >=0.70; report counts and uncertainty given small datasets. Zero cross-user/document/generation leakage; zero diagnostics as teaching; no false supported answers on the curated unsupported safety set; no unexplained degradation from baseline in complete-evidence coverage. These are release targets, not measured results or guarantees. If unattained, inspect/fix; do not silently lower them. Browser grounding and golden behavior must also pass regardless of retrieval averages. Establish a latency baseline, then reject >20% p95 regression from an experiment absent documented quality benefit; separate unavoidable vendor network latency from search costs.

## M. Automated test matrix (offline by default)

| Layer | Required proof |
| --- | --- |
| Corpus/schema | All ingest formats preserve IDs/order/source metadata; headings-only/error/placeholder rejected; table/caption coverage explicit; hash/mapping deterministic |
| DB/migration | Composite uniqueness/FKs/delete cascade; create_all and Alembic agree; upgrade populated legacy DB leaves documents NOT_INDEXED; downgrade tested only in disposable DB |
| Provider | Stable fake across processes; query/document input type; batching/order; dimensions/count/NaN/zero rejection; timeout/rate/auth errors and retry bounds; no network fallback |
| Lifecycle | Idempotent upload; changed generation removes stale search; duplicate worker exclusion; partial failure/retry; expired lease recovery; stale completion after delete/reupload cannot publish; model reindex without originals |
| Retrieval | Known cosine ranking/ties; one-document query; anchors/dedupe/budgets/truncation; incompatible model rejection; weak evidence no first-section fallback; neighbors cannot cross scope |
| Security | Other-user document returns404; forged anchor IDs/generation cannot retrieve; same local block IDs across documents stay isolated; deleted source and provenance inaccessible |
| Learn | Captured diagnosis/decision prompts contain actual original text, not only IDs/generated summaries; initial/wrong/IDK/continue/branch/review/new practice remain grounded; evidence transaction rolls back on failure |
| Ask | Shared retriever used for all intents; proper inline versus primary anchors; primary practice preserved for another/harder; simpler replaces intentionally; no evidence/grade mutation from question; no duplicate explanations |
| Persistence/UI | GET does not retrieve/embed/generate; refresh retains scene/visual/private target; failed indexing preserves progress; source change cannot resume stale teaching; safe messages no raw provider/schema errors |
| Evaluation | Gold span/hash validation; fixed splits/no family leakage; alternative/conjunctive metrics correct; unsupported denominators; injectable strategies; fixed/regressed reporting reproducible |

Use the existing PostgreSQL fixture conventions in `backend/tests/conftest.py`, existing Learn API/runtime/scenario tests, and frontend component tests. New tests belong alongside these; do not make normal suites depend on Voyage keys. Live evaluation is an explicit separate command.

## N. Real browser acceptance

Re-upload two substantive original documents through the real ingestion UI: satire and pendulum (or licensed equivalents in meaningfully different domains). Do not seed only generated SectionNotes as proof of source retrieval. Use a clean session per document and record its document/generation/index config. Observe processing → ready, then start Learn; also verify legacy re-upload and safe failure states.

Execute the full existing golden journey in each domain: cohesive teaching + meaningful visual + practice; plausible wrong response; source-specific teaching before retest; tutor-directed visual change with explanation/follow-up; IDK/uncertainty support; guided success → visibly reduced support → independent application; authorized prerequisite repair/return; delayed review after intervening material; transfer; evidence-based completion. Retrieval must support these paths without choosing their pedagogy.

Ask rephrase/example/visual/why-wrong/another/harder/simpler plus a paraphrased factual question and a near-topic unsupported question. Inspect displayed claims against the actual uploaded pages, not generated notes. Verify same-scene mutation, inline/replacement contracts, no text stacking, no false citations, no debug labels. Refresh after visual/Ask mutation: exact revision/interaction/visual/evidence persists with no provider call or regrading. Test another user's source cannot be reached.

Capture `.tmp/learn-golden/rag-v1/<domain>/<checkpoint>.png` and a compact manifest of visible behavior, source page/excerpt, action, session/scene revision and internal retrieval trace ID. DOM/accessibility evidence is acceptable if screenshots fail; API state alone is not. Stable local test auth is allowed only under existing development/test safeguards, never production bypasses. Use real embeddings/tutor calls for final acceptance, not scripted decisions that hardcode the journey. Fix a failing checkpoint, then rerun the complete affected fresh journey. Both domains must pass before declaring RAG V1 accepted.

## O. Security and operational constraints

Every entry (request, worker, CLI, provenance resolution) scopes by document and Source owner or a trusted server-resolved job identity. Never trust client-supplied user/generation/source IDs. CSRF/auth/rate limits remain unchanged. Source and learner data sent to Voyage is a new external processing boundary: document it; never send entire documents when only bounded inputs are needed. Keep keys server-only. Real student documents/queries must not become committed benchmark artifacts. Deletion removes vectors/provenance as well as text; no stale worker can recreate them. Retention/logging and provider data terms need confirmation before external rollout, not a production-auth shortcut.

## P. Ordered implementation phases and commit boundaries

| Phase / dependency | Files and contracts | Tests and acceptance / stable checkpoint |
| --- | --- | --- |
| 0 — baseline; none | Existing Learn docs, tests, migration env, dev run commands. Confirm actual backend/Alembic DB identity without secrets and current head; inspect existing browser harness rather than build another. | Record baseline regressions separately; preserve dirty user files; confirm raw-source ingestion examples. Commit only necessary baseline documentation. |
| 1 — corpus; 0 | New models/migration, `models/__init__.py`, `routers/ingestion.py`, new `services/source_index.py`, ingestion response/status schema. Introduce generation/ownership/coverage contract. | All formats, deletion, identical/changed re-upload, legacy NOT_INDEXED, note-generation alignment; source records resolve. Commit durable source boundary. |
| 2 — embeddings/index; 1 | New `services/embeddings.py`, source_index worker, environment docs, local `scripts/index_learning_blocks.py`. Provider seam + lifecycle. | Offline error/race/retry suite; live explicitly invoked smoke; no partial READY and no originals needed to reembed. Commit indexing lifecycle. |
| 3 — retrieval; 2 | Replace `services/retrieval.py`, typed retrieval/query models and serializer. | Exact ranking/scoping/budgets/weak status tests; source text and provenance resolve; no notes-as-evidence fallback. Commit single retrieval capability. |
| 4 — primary Learn; 3 | `routers/learn.py` create/response, `services/learn_runtime.py`, `learn_tutor.py`, relevant `learn_engine.py` generation and scene validation. | Actual captured prompts and DB API tests prove raw source from start through diagnosis/transition; no GET generation; outage/reupload safe. Commit grounded primary runtime. |
| 5 — Ask/convergence; 4 | Existing ASK_LUCENT runtime branch and router, narrow quiz navigation association, relevant frontend status handling. | Shared retrieval; inline/simpler semantics; Ask visuals/examples grounded; no duplicate context override or evidence writes. Commit shared Ask grounding. |
| 6 — measured baseline; 3–5 | New evaluation loader/runner/fixtures; Stage1 then Stage2 manifests, locked split and artifacts. | Metric unit tests + real embedding baseline; manually verified gold including unsupported and attachments. Commit reproducible benchmark, not private artifacts. |
| 7 — controlled optimization; 6 | Only evidence-justified query/budget/adjacency/config changes plus experiment log. | Identical dev comparisons, one variable each; freeze threshold/config, then heldout gate; retain failures. Commit chosen configuration and honest metrics. |
| 8 — browser acceptance; 7 | Existing browser journey runner and only failing product integration boundaries. | Both full fresh source-upload journeys; visible claims checked against pages; refresh/auth/unsupported checks. Commit relevant fixes and concise acceptance manifest. |
| 9 — convergence/regression; 8 | Remove now-unused lexical source retrieval/context overrides and only RAG-obsolete adapters; update runbook/config/docs. | Full backend, Learn scenarios/runtime/API/Postgres, frontend tests/typecheck/build, compile, migration smoke in disposable DB, diff check; rerun browser after behavior-affecting cleanup. Commit final validated V1, no push unless separately requested. |

Suggested validation commands use the existing environment: `cd backend && PYTHONPATH=. venv/bin/pytest tests -q`; targeted Learn/runtime/scenario selection from current test filenames; `venv/bin/python -m compileall -q app`; `venv/bin/alembic heads` and `current`, migration upgrade/downgrade smoke on an explicitly disposable DB; `cd web && npm test -- --run`, `npx tsc -b`, `npm run build`; `git diff --check`. Proposed evaluation CLI must support `--dataset`, `--split`, `--config`, `--output`, explicit `--provider fake|voyage`, and comparison against a saved baseline. Never run a live benchmark implicitly as pytest.

## Open Questions / Assumptions

- Voyage credentials, account model availability/quotas, and provider data-retention/processing terms cannot be established from repository code. Phase 2 performs the bounded live smoke and verifies provider limits; external rollout waits for appropriate data-processing approval. Offline implementation is not blocked by credentials.
- Benchmark source redistribution rights and availability of the original two golden PDFs must be confirmed. Use approved substantive substitutes if unavailable; never commit private uploads or use generated notes as source substitutes.
- Current live PostgreSQL identity/extension inventory and provider latency were not re-probed in this planning-only pass. Phase 0 records them safely; neither changes the chosen plain-Postgres design.
- Threshold and achieved metric values deliberately remain empirical outputs of the declared dev protocol, not invented results. Corpus size 50–500 blocks is a sizing assumption to measure, not a security limit or performance promise.

No additional product or architecture decision is required to begin Phase 0. These external/runtime checks are explicit phase gates, not reasons to invent implementation substitutes.

## Codex Goal-Mode Execution Checklist

- [ ] Read this plan and current Learn contracts; inspect current state without replaying completed migration or altering unrelated user changes.
- [ ] Record baseline tests/browser/environment and actual migration head; no credentials in logs.
- [ ] Persist existing LearningBlocks, metadata/attachments/mapping, ownership and generation atomically for every ingestion path.
- [ ] Cover deletion, re-upload, note-generation alignment and legacy re-upload-only policy with DB tests and safe UI status.
- [ ] Implement injected Voyage/fake provider, vector validation, durable statuses, bounded retries/leases and stale-worker rejection; verify model reindex without originals.
- [ ] Implement one owned single-document exact retriever, typed weak/failure results, query formation and explicit context budgets.
- [ ] Ground initial Learn and all source-dependent runtime events; replace diagnosis IDs with text and verify real provider prompt serialization.
- [ ] Ground Ask through the same runtime/retriever, preserve inline/replacement semantics, remove summary override; narrow quiz association cleanup only.
- [ ] Establish Stage1 then Stage2 annotated benchmark, fixed splits and locked holdout; save honest baseline and retained failures.
- [ ] Run one-variable dev experiments, record keep/revert, freeze configuration, evaluate heldout once at the candidate gate.
- [ ] Browser-run both uploaded-source golden journeys uninterrupted; inspect visible claims against pages, unsupported behavior, source/scene generation and refresh persistence.
- [ ] Fix failures at their root, add focused regression coverage, rerun complete affected journey; never mark API-only evidence as browser PASS.
- [ ] Remove only obsolete RAG/source paths; run full tests/build/compile/migration/diff verification and final browser regression.
- [ ] Commit stable checkpoints, keep private evidence local, report measured metrics and actual browser outcomes; do not push without authorization or claim completion on tests alone.
