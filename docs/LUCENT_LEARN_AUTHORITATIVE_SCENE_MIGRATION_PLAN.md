# Lucent Learn: Authoritative LearningScene Migration and Execution Plan

Status: implementation handoff plan; no migration code implemented by this document

Repository audited: 2026-09-05

Branch: `feature/public-auth-flow`

Revision at audit: `c3dba7a fix: separate tutor state from learner feedback`
Working tree at audit: clean

This document supersedes phase-status claims as the execution guide for migrating Lucent Learn from legacy step authority to one authoritative, revisioned `LearningScene` runtime. It complements `docs/LUCENT_LEARN_COHESIVE_TUTOR_IMPLEMENTATION_PLAN.md`, but is intentionally narrower: it identifies the duplicate control paths that must be removed and gives an ordered migration that leaves the application runnable at every commit.

## Architectural invariants

These invariants apply during every phase, including compatibility phases. A commit must not land if it violates one of them.

1. **Exactly one authoritative learner-facing scene.** For every active runtime-version-2 session, `LearnSession.state.currentScene` is the sole persisted learner-facing source of truth. The API field `scene` is a validated serialization of that object, never an independently recomposed object.
2. **No independent legacy progression.** No legacy step-selection function, cursor, array position, or frontend fallback may independently determine what the learner sees after runtime-version-2 activation.
3. **One tutor runtime for responses and Ask Lucent.** Normal learner responses, teaching-only continuation, hints, Ask Lucent, visual interactions, prerequisite transitions, and delayed reviews enter `learn_runtime.process_tutor_event()` and mutate the same scene state.
4. **Exactly one persisted visual-state owner.** Canonical visual state exists only inside `state.currentScene.visualState`. Other representations are compatibility inputs or ephemeral animation state, never competing persisted state.
5. **Internal tutor metadata never renders directly.** `TutorObservation`, diagnosis, hypothesis, confidence, strategy, rationale, tool calls/results, evidence labels, review state, and fallback metadata are not present in public learner-facing block types.
6. **Backend validates; tutor chooses pedagogy.** The backend owns safety and invariant enforcement but does not preselect teach versus test, pedagogical strategy, modality, scaffold, or whether to stay on the concept during the normal model-driven path.
7. **Legacy steps are assets, not a runtime.** `LearnPlan.objectives[].steps[]` may supply authorized source content, visuals, expected answers, and fallback interactions, but its order has no learner-facing meaning after upgrade.
8. **Every learner-visible mutation is grounded.** Every source-dependent scene block, interaction, feedback correction, and visual carries authorized provenance and passes learner-content validation before persistence.
9. **Reads are idempotent.** GET/resume never calls the provider, advances a concept, changes evidence, increments revision, or rebuilds a valid current scene.
10. **One response target.** A scene contains zero or one active response-bearing practice block, and the private grading payload has the same `interactionId` as the public block.
11. **Plan immutability.** Runtime remediation, prerequisite repair, Ask Lucent, and review never append, reorder, or replace `LearnPlan.objectives[].steps[]`.
12. **Fallbacks preserve the same runtime.** Provider/model failure uses the scene executor and persisted scene revision; it never silently re-enters legacy cursor progression.

## DO NOT

- Do not add another runtime abstraction or parallel scene-state store.
- Do not preserve obsolete control paths “just in case” when they create duplicate authority.
- Do not make `step_index` authoritative again, including in fallback code or tests.
- Do not create another persisted visual-state store in `LearnSession.state`, React context, a component, or a browser event bus.
- Do not solve uncertainty with a new rigid `if response == ...` teaching decision tree. Normalize learner signals deterministically, then let the bounded tutor choose pedagogy; deterministic rules are fallback/invariants only.
- Do not add more interaction types before this migration is complete.
- Do not declare a learner-behavior phase complete from unit tests alone.
- Do not silently fall back to legacy progression and report the agent path as working.
- Do not redesign the architecture unless a statement in this plan is factually incompatible with the repository. If that occurs, document the contradiction before changing the plan or code.
- Do not mutate learner evidence from model output or scene-tool output.
- Do not copy `TutorDecision.transitionMessage`, diagnosis, hypothesis, rationale, or evaluation evidence directly into a public scene block.
- Do not compose or repair a scene inside `_session_payload()` or any GET handler.
- Do not client-merge arbitrary scene patches or dispatch global visual-control events.
- Do not append remediation or prerequisite steps to the persisted plan.
- Do not keep compatibility behavior after Phase 9 merely because an old test still asserts it; migrate the test and delete the duplicate path.

## 1. Final target runtime

### 1.1 One learner-facing source of truth

For an active session, the only authoritative learner-facing state is:

```text
LearnSession.state.currentScene
```

`currentScene` is a validated, persisted `LearningScene` revision. It owns:

- the active objective and target concept;
- all learner-facing explanation, example, visual, practice, feedback, and tutor-message blocks;
- the single response-bearing interaction, if one exists;
- the current visual identity and state;
- the learner-facing objective/progress copy needed by the workspace;
- source provenance for every source-dependent block;
- the scene revision used for concurrency/staleness checks.

The frontend renders `session.scene` only. It does not independently render `session.step`, `session.feedback`, `session.action`, model rationale, or learner-state fields.

### 1.2 Authoritative LearnSession data

The following remain authoritative on `LearnSession`:

- `id`, `user_id`, `document_id`, `note_id`;
- `goal`, `familiarity`, `status`, `ended_reason`, `report`;
- `plan`: immutable objective/source/candidate-asset library for the session version;
- `state.concepts`: concept-level learner evidence;
- `state.currentScene`: public, answer-safe active scene;
- `state.currentScenePrivate`: private grading data for the active response-bearing block;
- `state.sceneHistory`: bounded scene summaries, not full unbounded scenes;
- `state.currentObjectiveId`: transition target used only while no active scene exists; while a scene is active it must equal `state.currentScene.objectiveId` and cannot independently select content;
- `state.revisitQueue`, review due data, and concept review state;
- `state.branchStack`: bounded prerequisite return stack keyed by concept IDs and scene IDs;
- bounded recent attempts, previous strategies/modalities, and last validated tutor decision/tool results.

`LearnAttempt` remains the append-only record of learner submissions and evaluations. Its `step_id` becomes the stable interaction ID of the scene practice block. Scene, block, interaction, action, and concept IDs remain separate.

### 1.3 Role of LearnPlan and objective steps

`LearnPlan.objectives` remains the bounded, source-grounded learning scope. Each objective continues to hold:

- stable ID, title, outcome, bottleneck, content policy, prerequisites;
- source section/block IDs;
- authored/generated candidate assets currently stored under `steps`.

`objectives[].steps[]` is no longer an ordered lesson or runtime cursor. It is an immutable candidate asset library used for:

- source-grounded deterministic fallback;
- reusable visual/Note component references;
- reusable validated practice interactions;
- expected-answer and grading material;
- backwards compatibility with existing sessions.

The model may select an authorized candidate or propose a complete validated scene-local interaction. It may not advance through the array by position.

After the migration proves stable, rename `steps` to `assets` only in a separate versioned plan migration if the clarity benefit justifies it. Renaming is not required to remove authority.

### 1.4 Fate of objective_index and step_index

- `objective_index` remains a derived reporting/compatibility column for this migration. It is written from `state.currentObjectiveId`, is never read by runtime control flow, and is not dropped by the cleanup migration. Any later removal is a separate API/reporting decision outside this contract.
- `step_index` loses all runtime authority in the first scene-authority cutover. The legacy-session adapter may read its pre-existing value exactly once to seed a version-2 scene, but no code writes it after the cutover. It is removed from router logic, API responses, tests, and finally the database column.
- New sessions must not use positional step progression.

### 1.5 Learner evidence

Concept evidence remains in `LearnSession.state.concepts` and `LearnAttempt`. The deterministic runtime alone updates it after a validated learner event. `TutorDecision` may state expected evidence, diagnosis, and desired scaffold, but may never write evidence.

The active scene references evidence targets by semantic name. The private practice payload contains the exact grading contract. A teaching-only scene produces no graded attempt.

### 1.6 Visual state

The sole persisted visual owner is `state.currentScene.visualState`:

```text
visualState:
  visualKey
  renderer
  stage
  highlightedElementIds[]
  revealedElementIds[]
  parameters{}
  playback
  interactionMode
```

The corresponding visual block contains either `visualSpec` or `visualRef`. No duplicate `state.visualStage`, `state.visualHighlight`, or frontend-owned canonical stage remains. Frontend animation progress between canonical stages may be ephemeral, but any learner-significant change is submitted as a scene event and returned in a new scene revision.

### 1.7 Ask Lucent entry

`POST /learn-sessions/{session_id}/ask` remains the guarded public endpoint. After rate limiting, relevance gating, ownership checks, and retrieval, it creates an `ASK_LUCENT` tutor event and invokes the same runtime used by normal learner events. It receives the current authoritative scene and may request validated scene operations. The API returns the complete authoritative scene revision, not a loosely merged client patch.

Ask Lucent cannot mutate learner evidence. A question can add a bounded uncertainty observation for subsequent planning, but evidence changes only through the normal deterministic evaluator.

### 1.8 Scene revisions

- Initial composition creates revision `1`.
- Each accepted response, teaching-only continue, hint that changes the teaching surface, Ask Lucent recomposition, visual state change, prerequisite transition, or review transition produces exactly one new revision.
- The canonical revision is stored only at `state.currentScene.revision`. There is no independent `state.sceneRevision` counter. A legacy `state.sceneRevision` value is consumed by the adapter once and then removed.
- Requests include `sceneId` and `sceneRevision`. A stale request returns `409` with the latest public session payload; it does not double-apply evidence or tools.
- `sceneHistory` stores at most eight summaries: scene ID, revision, objective ID, response interaction ID, strategy key, timestamp, and reason. Full prior public scenes are not retained indefinitely.
- Scene IDs are stable bounded hashes of session, revision, objective, and event ID; they never embed growing remediation strings.

## 2. Keep / adapt / remove matrix

| Item | Classification | Current responsibility | Target responsibility and exact migration action | Dependencies / safe deletion point |
|---|---|---|---|---|
| `LearnSession` model | KEEP | Owns plan, JSON state, cursors, status, report | Remains session aggregate; JSON state owns current scene/evidence/runtime. Add no new table for initial cutover. | Always retained. |
| `LearnAttempt` | KEEP | Persists graded step attempts | Persists attempts against scene interaction IDs. Store scene ID/revision in the existing `evaluation` JSON for this migration; do not add attempt columns. | Always retained. |
| `LearnTutorEvent` | KEEP | Telemetry/rate-limit records | Continue bounded structured telemetry for observation, decision, tools, fallbacks, validation and scene revision. | Always retained. |
| `LearnPlan.objectives[]` | KEEP | Ordered objective list | Immutable source-backed objective set and concept graph. Selection is by stable objective ID, not cursor position. | Always retained. |
| `LearnPlan.objectives[].steps[]` | ADAPT | Prebuilt ordered lesson | Treat as unordered candidate asset library. Never append remediation/prerequisite steps. Expose sanitized catalog to tutor observation. | Can be renamed in a later plan-version migration; must not control runtime after Phase 3. |
| `session.objective_index` | TEMPORARY COMPATIBILITY | Selects current objective | Derive from `currentObjectiveId` only for old API/report consumers. Stop reading it in runtime decisions. | Retain as derived-only reporting metadata in this migration; deletion is explicitly out of scope. |
| `session.step_index` | TEMPORARY COMPATIBILITY, then REMOVE | Selects current step and progression | Legacy adapter reads once to seed a scene. New runtime never reads or writes it. | Frontend stops consuming it in Phase 6; remove from API and DB in Phase 9. |
| `_choose_next_step()` | REMOVE | Scans later step positions and rotates modalities | Replace with tutor decision over authorized objective/candidate catalog plus deterministic fallback scene planner. | Delete immediately after response endpoint uses `process_tutor_event()` exclusively. |
| `_append_remediation()` | REMOVE | Appends generated repair steps to mutable plan | Replace with scene operations that add teaching and a new scene-local practice interaction. Never mutate plan. | Delete after remediation tests use scene-local interactions. |
| `_append_prerequisite_branch()` | REMOVE | Appends a prerequisite question into current objective steps | Replace with validated `branch_to_prerequisite` operation that pushes concept/scene return data and composes a prerequisite scene. | Delete after prerequisite branch/resume tests pass. |
| `_leave_degenerate_repair_loop()` | ADAPT then REMOVE | Escapes recursively growing repair steps | Move bounded-loop protection into runtime invariants: failed strategy/modalities, max repeated target turns, review scheduling, objective selection. | Delete with other step-repair functions. |
| `_next_objective()` | ADAPT | Uses queue and indexes to choose objective | Become stable-ID `select_target_objective()` fallback only. It proposes a target when the model cannot; it never chooses learner-facing blocks. | Retain renamed deterministic fallback. |
| `_action_for()` | REMOVE | Derives action from step type and concept state | Model/fallback scene planner chooses goal then action. Executor validates action against current context. | Delete after no route or payload depends on legacy `TutorAction`. |
| `_strategy_for()` | ADAPT, then REMOVE from runtime | Maps step type to strategy | Content policies remain fallback priors in `adaptive_policy.py`; runtime must not infer strategy from selected interaction. | Delete router helper after tutor observation/fallback planner owns it. |
| `_tutor_observation()` | ADAPT | Builds observation from current legacy step | Move to `learn_runtime.py`; derive from current scene, private practice, concept evidence, candidate assets, current visual and retrieved source. Add explicit event/uncertainty fields. | Retain as core builder under new name. |
| `choose_tutor_decision()` | KEEP/ADAPT | Model chooses bounded metadata/candidate step | Receive authoritative scene observation; allow complete typed scene plan and scene-local interaction; remove `allowed_step_ids` as the only meaningful action boundary, replacing it with authorized asset IDs/source IDs/tool schemas. | Retained provider boundary. |
| `TutorDecision.nextStepId` | TEMPORARY COMPATIBILITY, then REMOVE | Chooses legacy candidate cursor | Map to `use_asset` during adapter phase; new decisions use scene block/operation directives. | Delete from schema/provider prompt after legacy sessions are converted. |
| `TutorDecision.transitionMessage` | ADAPT | Free-form model text sometimes rendered or phrase-filtered | Rename/replace with optional validated `studentMessage`; internal transition rationale stays internal. Student message must pass the learner-content validator. | Remove old field after provider fixtures migrate. |
| `TutorToolCall.arguments` | REMOVE/REPLACE | Accepts an allowlisted tool name with an untyped `dict` | Replace with discriminated `SceneOperation` models whose fields are tool-specific and `extra="forbid"`; authorization remains runtime-side. | Delete free-form arguments in Phase 3; remove the old compatibility parser in Phase 9. |
| `TutorSceneBlockPlan` | ADAPT | Describes optional generated scene content | Becomes the private model-authored payload used only inside typed content operations; it never becomes a public block until source/content validation succeeds. | Retain renamed `TutorContentBlockDraft` in Phase 3. |
| `TutorScenePlan` | ADAPT | Optional composition metadata layered over step selection | Fold its immediate scene intent into `TutorDecision.operations`; do not persist a separate plan or sub-runtime. | Delete old class after fake-provider fixtures and decision parsing use operations in Phase 3. |
| `TutorObservation` | KEEP/ADAPT | Contains legacy current-step and learner-state context | Remove cursor/next-step framing; add current public scene summary, private interaction type, event, visual state, recent relevant attempts, failed/successful strategies/modalities, prerequisite/review candidates, and bounded retrieved blocks. | Retain as the sole model input contract. |
| `compose_learning_scene()` | ADAPT | Rebuilds a wrapper from current legacy step | Convert into pure `execute_scene_plan()`/scene compiler taking prior scene plus validated tool results. It must not inspect `step_index` or select neighboring steps. | Retain module, replace function contract in Phase 3. |
| `_execute_tutor_tools()` | ADAPT | Validates a few visual tools; returns `accepted` for most | Move to `learn_scene.py` or `learn_runtime.py`; every successful teaching tool returns a concrete block/visual/practice/branch operation. No no-op acceptance. | Replace before model scene authority is enabled. |
| `_session_payload()` | ADAPT | Reconstructs scene and legacy step from cursors | Serialize persisted `currentScene`; upgrade legacy state once if absent. Never compose on GET. | Retain serializer; delete legacy reconstruction after compatibility window. |
| `_persist_scene()` | ADAPT | Writes currentScene and bounded history | Become atomic `persist_scene_revision()` with stale-revision check and private/public scene payload handling. | Retain renamed core behavior. |
| `LearningScene.responseStepId` | ADAPT | Points at legacy plan step | Rename to `responseInteractionId`; identifies the one private/public practice interaction in the scene, regardless of origin. Accept old alias during compatibility. | Remove old JSON alias after persisted sessions have upgraded. |
| `sceneInterruption` | REMOVE | Stores Ask Lucent question/answer for compiler append | Ask Lucent generates normal scene operations and an optional `tutor_message` block. Do not persist raw chat history in session state; keep the panel's current answer client-local and store only bounded structured Ask telemetry. | Delete after Ask endpoint uses shared runtime. |
| `state.lastFeedback` / `lastFeedbackKind` | TEMPORARY COMPATIBILITY, then REMOVE | Standalone feedback copied into API and scene | Feedback exists only as a learner-facing scene block; evaluation stays private. Adapter converts legacy feedback into one block once. | Delete after frontend stops rendering session-level feedback. |
| `state.visualStage` / `visualHighlight` | REMOVE | Parallel visual state | Migrate into `currentScene.visualState`; reject direct writes elsewhere. | Delete once controlled visual renderers use scene state. |
| `state.currentScene` | KEEP/ADAPT | Persisted snapshot currently ignored by GET | Becomes authoritative public scene returned verbatim after validation. | Core target. |
| legacy `state.sceneRevision` | REMOVE | Duplicates the revision on `currentScene` | Adapter copies the greatest valid legacy value to `currentScene.revision` once, then deletes this key. | Delete in Phase 2 normalization. |
| `state.sceneHistory` | KEEP/ADAPT | Stores scene summaries | Enforce bounded history for every scene event; each entry records the canonical `currentScene.revision`. | Core target. |
| `state.lastTutorDecision` / tool results | KEEP | Internal orchestration telemetry/state | Remain internal only; never copied to public scene text automatically. | Retained, bounded. |
| `TutorAction` and response `action` | TEMPORARY COMPATIBILITY, then REMOVE publicly | Exposes selected action metadata | Keep internal action/tool records; remove from `LearnSessionResponse`. | Delete public field after frontend/tests use scene only. |
| response `step` | TEMPORARY COMPATIBILITY, then REMOVE | Main frontend interaction | During rollout derive from scene practice block only; frontend ignores it. Remove once old clients are no longer supported. | Delete in Phase 9 cleanup. |
| response `feedback` / `evaluation` | TEMPORARY COMPATIBILITY, then REMOVE publicly | Standalone UI feedback/internal evaluation | Return learner-facing feedback inside scene only. Keep evaluation internal or expose only a student-safe result token if accessibility needs it. | Delete after scene renderer handles feedback. |
| `LearnView` in `web/src/pages/Notes.tsx` | ADAPT | Owns onboarding, session state, legacy step rendering, Ask panel, focus | Keep route/mode integration, extract runtime hook and render authoritative `LearningSceneView`; remove direct step branch. | Retain component shell; simplify in frontend phase. |
| `SceneSupportBlocks` | REMOVE | Renders non-practice scene blocks above legacy practice | Replace with one ordered `LearningSceneView` that renders every block, including practice. | Delete when scene renderer lands. |
| `ComponentView` in `Notes.tsx` | ADAPT | Renders Notes visual components | Extract to shared `SectionComponentRenderer` used by Notes and Learn controlled visual wrapper. | Delete local function only after both consumers migrate. |
| `StructuredVisual` | KEEP/ADAPT | Owns local stage and listens to global event | Make controlled: `visualState`, `onVisualEvent`; local state only for ephemeral animation. Remove global listener. | Retain renderer. |
| `StepThroughMechanism` | KEEP/ADAPT | Owns local stage/prediction state | Add controlled stage/highlight/parameter interface and emit semantic visual events. | Retain renderer. |
| global `lucent-visual-stage` event | REMOVE | Imperatively changes StructuredVisual only | Replace with React props from authoritative scene and API visual-event responses. | Delete after all visual renderers are controlled. |
| Ask Lucent `scenePatch` | ADAPT | Optional unversioned replacement patch | Return required full authoritative `scene` plus revision; do not client-merge arbitrary blocks. Accept `scenePatch` alias temporarily. | Remove alias after frontend/API tests migrate. |
| Ask Lucent answer panel | KEEP/ADAPT | Shows detached chat answer | Keep lightweight input/history, but answer content also enters active scene when pedagogically relevant. | Retain UI, integrate with runtime. |
| `learner_text_quality_issues()` / `student_facing_quality_issues()` | KEEP/ADAPT | Phrase/internal-token linting | Move to explicit shared learner-content boundary; validate all public blocks and interactions against source, not generated text. Phrase filtering becomes defense-in-depth only. | Retain validation behavior, change placement. |
| `evaluate_step()` / `diagnose_response()` | KEEP/ADAPT | Grades legacy steps; optional semantic diagnosis | Grade scene-private interaction by ID. Normalize explicit uncertainty before grading. Persist evaluation privately and create separate student feedback. | Retain core evaluation. |
| `adaptive_policy.py` | KEEP/ADAPT | Deterministic strategy/content/scaffold/review helpers | Keep invariant and fallback policies only. Remove step-type-to-strategy authority from router. | Retained fallback/safety module. |
| `retrieve_note_context()` | KEEP | Bounded lexical retrieval | Remains grounded source retrieval for this migration. | Retained. |

## 3. New authoritative control flow

Create `backend/app/services/learn_runtime.py` as the one orchestration service. Routers remain HTTP/auth/transaction adapters. Do not create a second policy layer: move existing router logic into this service and delete the old branches as each event migrates.

### 3.0 Route-to-event ownership

| API route / function | Accepted runtime event | Runtime behavior |
|---|---|---|
| `POST /documents/{document_id}/learn-sessions` / `learn.py::create_learn_session()` | `START` | Build the initial observation/decision/scene and persist revision 1. |
| `GET /learn-sessions/{session_id}` / `learn.py::get_learn_session()` | none | Normalize old state once via `ensure_runtime_state()`, then serialize only. |
| `GET /documents/{document_id}/learn-sessions/active` / `learn.py::get_active_learn_session()` | none | Same read/normalization rule as the session GET. |
| `POST /learn-sessions/{session_id}/responses` / `learn.py::submit_learn_response()` | `RESPONSE` or `CONTINUE` | `LearnResponseRequest.eventType` defaults to `RESPONSE` when an interaction ID/payload exists and must be `CONTINUE` for a teaching-only scene. Both call `process_tutor_event()`. |
| `POST /learn-sessions/{session_id}/hints` / `learn.py::get_learn_hint()` | `HINT` | Validate the active interaction and create a revised scene containing the hint/scaffold change. |
| `POST /learn-sessions/{session_id}/ask` / `learn.py::ask_lucent()` | `ASK_LUCENT` | Keep security/relevance/rate-limit/retrieval checks, then call the shared runtime. |
| `POST /learn-sessions/{session_id}/visual-events` / new `learn.py::handle_learn_visual_event()` | `VISUAL_RESPONSE` | Validate the current visual and apply presentation/evidence-bearing visual events through the same runtime. |
| `POST /learn-sessions/{session_id}/stop` / `learn.py::stop_learn_session()` | terminal stop command | Persist the current scene/evidence/report without asking the model to mark completion. |

No generic second event endpoint is added. Existing route names remain stable; request schemas gain scene/revision identity and the visual-event route is the only new API route.

### 3.1 A. Normal learner response

```text
LearnView/LearningSceneView
  -> POST /learn-sessions/{id}/responses
     {sceneId, sceneRevision, interactionId, response payload}
  -> learn.py: ownership + active-session check
  -> learn_runtime.process_tutor_event(RESPONSE)
  -> load/validate state.currentScene and currentScenePrivate
  -> reject stale scene or wrong interaction ID
  -> deterministic evaluate_step()/diagnose_response()
  -> compute prospective LearnAttempt/evidence/review changes in memory
  -> retrieve_note_context() for current concept/event
  -> build_tutor_observation() from updated evidence + prior scene
  -> choose_tutor_decision()
  -> validate decision/tool IDs/provenance/content
  -> execute_scene_plan(previous_scene, decision, event)
  -> reload/lock session and recheck revision/idempotency
  -> persist attempt/evidence/review plus persist_scene_revision() atomically
  -> commit
  -> _session_payload() serializes persisted scene
  -> React replaces session.scene and renders it
```

No call to `_choose_next_step()`, no `step_index` mutation, and no plan append occurs.

### 3.2 B. Ask Lucent message

```text
AskLucentPanel
  -> POST /learn-sessions/{id}/ask
     {sceneId, sceneRevision, message}
  -> ownership, durable rate limit, relevance gate
  -> retrieve_note_context()
  -> process_tutor_event(ASK_LUCENT)
  -> observation includes current scene/visual, prior teaching attempts,
     evidence, user request and source blocks
  -> same bounded tutor decision path
  -> execute only presentation/branch-proposal tools
  -> mutate/augment the current scene while preserving active practice unless
     the decision explicitly and validly replaces it
  -> persist one new scene revision
  -> return concise answer + full authoritative scene
  -> React renders returned scene; no global event or client patch merge
```

### 3.3 C. Visual interaction

Add `POST /learn-sessions/{id}/visual-events` with a discriminated request:

```text
{sceneId, sceneRevision, visualKey, eventType, elementId?, stage?, value?}
```

Allowed event types initially: `SET_STAGE`, `REVEAL`, `HIGHLIGHT`, `PREDICT`, `LABEL`, `MANIPULATE`, `REPLAY_COMPLETE`. The router authorizes the visual key and element IDs against the current scene. Presentation-only events update visual state and revision deterministically. Evidence-bearing events pass through `process_tutor_event(VISUAL_RESPONSE)` and the evaluator before replanning.

### 3.4 D. Session resume

```text
GET active/session
  -> load owned LearnSession
  -> ensure_runtime_state()
     if currentScene exists: validate and return it unchanged
     if absent: legacy adapter resolves objective/step once, creates revision 1,
       stores private response data, and marks runtimeVersion=2
  -> no model call on ordinary GET
  -> no scene recomposition on serialization
```

### 3.5 E. Prerequisite branch

The tutor proposes `branch_to_prerequisite` with an authorized concept ID and reason. Deterministic execution:

1. verifies prerequisite is present in plan/source concept set and evidence is weak;
2. enforces branch depth and cycle bounds;
3. pushes `{fromConceptId, returnSceneId, returnObjectiveId, prerequisiteConceptId, reason}`;
4. composes/persists a prerequisite teaching scene;
5. evaluates prerequisite evidence normally;
6. on validated return decision, pops the stack and replans the original concept using the new evidence.

No prerequisite step is appended to the source objective.

### 3.6 F. Delayed review

Review scheduling remains deterministic. When due:

1. `select_target_objective()` exposes due concept candidates in the observation;
2. the model may select `DELAYED_RECHECK` or another pedagogically justified action;
3. the executor composes a different scene-local interaction/modal representation;
4. independent delayed evidence updates the concept;
5. the review item is cleared or rescheduled deterministically.

The queue selects a concept candidate, never a legacy step index.

## 4. Scene executor contract

### 4.1 Location and public interface

Adapt `backend/app/services/learn_scene.py` into the deterministic executor/compiler. Its central function becomes:

```python
execute_scene_plan(
    *,
    session: LearnSession,
    previous_scene: LearningScene | None,
    decision: TutorDecision,
    observation: TutorObservation,
    event: TutorEvent,
    objective: LearningObjective,
    authorized_assets: AuthorizedAssetCatalog,
    source_context: RetrievedContext,
) -> SceneExecutionResult
```

`SceneExecutionResult` contains:

- public `LearningScene`;
- private response interaction, if any;
- applied/rejected tool results;
- proposed branch/review/objective transition for deterministic runtime application;
- validation/fallback metadata;
- no learner-evidence mutations.

The implementation must place the contracts exactly as follows; the implementation agent does not choose alternate locations:

- `TutorEvent` and its discriminated payloads: Pydantic models in `backend/app/schemas/learn.py`, because router requests and runtime tests validate them.
- `AuthorizedAssetCatalog`: frozen typed dataclass in `backend/app/services/learn_runtime.py`, because it contains private `LearnStep` grading assets and must never enter OpenAPI.
- `SceneExecutionResult`: frozen typed dataclass in `backend/app/services/learn_scene.py`, because it is the private return contract of `execute_scene_plan()` and must never be serialized directly.
- Public `StudentMessage`, `StudentFeedback`, `LearningSceneBlock`, and `LearningScene`: Pydantic models in `backend/app/schemas/learn.py`.
- Private active-interaction state: Pydantic `ScenePrivateState` in `backend/app/schemas/learn.py`, persisted under `LearnSession.state.currentScenePrivate` but excluded from every response model.

```text
TutorEvent
  id                         bounded idempotency key
  type                       START | CONTINUE | RESPONSE | HINT |
                             ASK_LUCENT | VISUAL_RESPONSE |
                             PREREQUISITE_RETURN | DELAYED_REVIEW
  sceneId
  sceneRevision
  interactionId?             required for RESPONSE/HINT
  response?                  typed existing response payload
  message?                   required for ASK_LUCENT
  visualEvent?               required for VISUAL_RESPONSE

AuthorizedAssetCatalog
  objectiveIds[]
  conceptIds[]
  candidateInteractions{}    private LearnStep by stable ID
  visualAssets{}             VisualSpec or authorized Note component reference
  sourceSectionIds[]
  sourceBlockIds[]

SceneExecutionResult
  scene                      public LearningScene
  privateScene               active private interaction only
  toolResults[]              applied or rejected, with concrete delta summary
  transitionProposal?        branch/review/advance/finish proposal
  usedFallback               boolean
  fallbackReason?            bounded enum
```

### 4.1.1 Layer ownership

| Concern | Sole owner | Inputs | Output / mutation |
|---|---|---|---|
| `TutorObservation` construction | `learn_runtime.build_tutor_observation()` | persisted scene, private interaction, learner evidence, recent attempts, authorized asset summaries, retrieved blocks, current event | Bounded internal observation; no persistence mutation. |
| `TutorDecision` generation | `learn_tutor.choose_tutor_decision()` | observation, allowed concept/asset/source IDs, deterministic fallback decision | Validated internal decision; no persistence mutation. |
| Decision/tool authorization | `learn_runtime.validate_tutor_decision()` | decision plus authorized catalog/current session | Validated operations or structured rejection; no learner-facing output yet. |
| Scene operation execution | `learn_scene.execute_scene_plan()` | previous scene, validated decision/operations, source context, authorized assets | New public scene, private practice payload, concrete tool results. |
| Objective grading | `learn_engine.evaluate_step()` and `learn_tutor.diagnose_response()` where semantic judgment is necessary | private practice plus learner response and bounded source context | Private `LearnEvaluation`. |
| Evidence mutation | `learn_runtime.apply_evaluation()` | previous evidence, private evaluation, assistance/scene context | Updated `state.concepts`, review schedule, `LearnAttempt`; model cannot write these fields. |
| Learner feedback | `learn_runtime.build_student_feedback()` plus scene executor | private evaluation, validated source context, optional validated model student message | One public feedback block attached to the evaluated interaction. |
| Scene persistence/revision | `learn_runtime.persist_scene_revision()` | previous `currentScene.revision`, execution result, event ID | Atomic replacement of `currentScene`/`currentScenePrivate` and bounded history update. The new revision exists only on the new scene. |
| HTTP serialization | `learn.py::_session_payload()` | persisted session only | Public response; never composes or mutates a scene. |
| React rendering | `LearningSceneView` | returned public scene | UI only; no inference or canonical-state merge. |

The order for a response event is fixed: validate event → grade → update evidence → observe → decide → validate tools → execute scene → persist one revision. For non-evidence events, skip grade/evidence mutation but retain the same observe/decide/execute/persist path.

“Update evidence” before the decision means compute a prospective deterministic evidence snapshot in memory. Do not flush learner evidence before the decision and do not leave an open write transaction around a provider call. The transaction sequence is fixed:

1. load/authorize a snapshot and validate the submitted scene revision;
2. normalize an old session in its own committed transaction if required, then restart from the normalized snapshot;
3. compute evaluation and prospective evidence in memory;
4. build observation and call the provider with no pending database write transaction;
5. validate/execute the decision as pure in-memory work;
6. open the final transaction, lock/reload `LearnSession`, recheck scene revision and event idempotency, and return `409` if stale;
7. atomically write `LearnAttempt`/evidence, transition state, `currentScene`, `currentScenePrivate`, history, and required telemetry;
8. isolate nonessential telemetry with a savepoint so it cannot abort the main transaction; commit once.

This ordering prevents both long-running write locks and a provider/telemetry failure from poisoning the session transaction.

### 4.2 Validated decision

`TutorDecision` must express:

- internal hypothesis/diagnosis/confidence;
- pedagogical goal and strategy;
- target concept and proposed scaffold level;
- ordered typed scene operations, maximum four;
- expected evidence;
- optional prerequisite/review/objective transition proposal;
- optional natural `studentMessage` explicitly marked learner-facing.

Remove free-form `arguments: dict`. Use a discriminated union in `backend/app/schemas/learn.py` so unknown tools/fields fail before execution.

The exact replacement models are:

- `TutorContentBlockDraft`: learner-facing title/content plus authorized source IDs; no diagnosis/rationale/state fields;
- `ContentSceneOperation`: discriminator `op` in `add_explanation | replace_explanation | add_example | add_counterexample | add_analogy | add_comparison | add_worked_example | add_guided_step | add_reflection`, with `blockKey` and `content`;
- `VisualSceneOperation`: discriminator `op` in `use_visual_asset | add_visual_spec | set_visual_stage | highlight_visual_elements | reveal_visual_elements | set_visual_parameter | replay_visual`, with only the fields applicable to that operation;
- `PracticeSceneOperation`: discriminator `op` in `add_practice | replace_practice | remove_practice`, accepting exactly one of `assetId` or `interactionDraft` for add/replace;
- `FeedbackSceneOperation`: discriminator `op` in `append_feedback | replace_feedback`, with `respondsToInteractionId` and optional validated `studentMessage`;
- `TransitionSceneOperation`: discriminator `op` in `branch_to_prerequisite | return_from_prerequisite | schedule_revisit | advance_objective | finish_session`, with stable authorized IDs/reason enum only;
- `SceneOperation`: the discriminated union of the five operation families above.

Every operation model sets Pydantic `extra="forbid"`. Existing `TutorToolCall` and `TutorScenePlan` are compatibility input models only until their Phase-3 provider fixtures are converted, then are removed in Phase 9.

### 4.3 Scene operations

Support these bounded operations, each producing a real result:

- `add_explanation`, `replace_explanation`;
- `add_example`, `add_counterexample`, `add_analogy`, `add_comparison`;
- `add_worked_example`, `add_guided_step`;
- `use_visual_asset`, `add_visual_spec`;
- `set_visual_stage`, `highlight_visual_elements`, `reveal_visual_elements`, `set_visual_parameter`, `replay_visual`;
- `add_practice`, `replace_practice`, `remove_practice`;
- `append_feedback`, `replace_feedback`;
- `add_reflection`;
- `branch_to_prerequisite`, `return_from_prerequisite` as validated transition proposals;
- `schedule_revisit`, `advance_objective`, `finish_session` as validated runtime proposals.

An operation is never successful merely because it is allowlisted. It is either `applied` with a concrete block/state delta or `rejected` with a reason.

### 4.4 Block mutation rules

- Preserve prior explanatory/visual context when a response only adds feedback or a scaffolded follow-up.
- Replace a block only by stable block role/key, not array position.
- At most one `practice` block can accept a response.
- Adding new practice replaces the previous active practice but may keep it as noninteractive context only if pedagogically useful and bounded.
- Feedback is attached to the evaluated practice using `respondsToInteractionId` and rendered once.
- Blocks are ordered semantically by the executor; the model chooses intent/order but never CSS/layout.
- Maximum six public blocks and one private practice payload.

### 4.4.1 Public and private scene shapes

The target public `LearningScene` contains exactly: `id`, `revision`, `objectiveId`, `objective`, `targetConcepts`, ordered `blocks`, `sourceSectionIds`, `sourceBlockIds`, `visualState`, `responseInteractionId`, and learner-facing `progress`. Remove `pedagogicalGoal`, `tutorHypothesis`, `strategy`, `scaffoldLevel`, and internal `completionCondition` from this public model.

`ScenePrivateState` contains exactly: `sceneId`, `revision`, optional private `interaction`, `objectiveId`, `targetConceptIds`, `evidenceTargets`, internal completion condition, applied strategy/scaffold/action metadata, and the bounded decision reference needed for future observation. It is stored only in `state.currentScenePrivate` and is never returned by `_session_payload()`.

### 4.5 Visual mutation

Visual operations require the current scene's `visualKey`. They validate stage, element, parameter, and renderer support. Mutations update the same visual block and `scene.visualState`; they do not create a second visual unless the model explicitly chooses a new authorized representation.

### 4.6 Practice insertion and grading privacy

`add_practice` accepts either:

- an authorized candidate asset ID from `LearnPlan.objectives[].steps[]`; or
- a complete validated private `LearnStep` draft with authorized source IDs.

The executor stores the answer-bearing step under `state.currentScenePrivate.interaction`. The public scene block stores only `LearnStepView`. `responseInteractionId` points to the private/public pair. The plan is never mutated.

### 4.7 Evidence update boundary

`learn_runtime.py` evaluates and updates evidence before asking for the next decision. The executor receives the resulting observation but cannot edit evidence. Tool result types contain no evidence mutation fields. This is enforced by schema and tests.

### 4.8 Provenance and learner-content validation

Every source-dependent content, practice, and visual operation must reference a subset of:

- current document SectionNote section/block IDs;
- current objective source IDs;
- retrieved source result IDs;
- authorized prerequisite concept source IDs.

Validation occurs before a block enters the scene. Generated text is checked against source evidence and learner-content rules. Retrieved text remains untrusted data and cannot define tools or policy.

### 4.9 Bounded execution

- maximum four model-requested operations;
- maximum one response-bearing practice;
- maximum six public blocks;
- maximum one provider retry for schema/content correction;
- bounded source context and output tokens using the existing provider abstraction;
- maximum prerequisite depth four;
- bounded scene history eight;
- repeated-strategy/modality checks prevent unchanged remediation loops.

### 4.10 Persistence and failure

After the provider-free snapshot phase described in 4.1.1, the runtime applies the already-validated evidence, scene, branch/review transitions, and required audit telemetry inside one short final transaction. Nonessential telemetry is isolated by savepoint. `currentScene.revision` increments only after a valid scene is produced; no separate revision counter is written. A concurrent/stale final check returns the latest scene with `409` and discards the uncommitted evaluation/decision rather than replaying it against new state.

If the model is unavailable or invalid:

1. use deterministic content-policy fallback to choose teach/test intent;
2. reuse a grounded candidate asset or prior visual;
3. construct source-specific learner text;
4. if no valid practice exists, return a teaching-only scene;
5. never fall back to `_choose_next_step()` or append to the plan;
6. persist fallback telemetry without poisoning the main transaction.

## 5. Model authority contract

### 5.1 Model controls within validated bounds

- whether the next scene should teach, probe, practice, review, transfer, or move on;
- whether to stay on the current concept or propose an authorized related/prerequisite concept;
- pedagogical goal and strategy;
- explanation, example, analogy, comparison, visual, worked-example, or prerequisite-repair selection;
- proposed scaffold level;
- reuse versus replacement of an existing visual;
- appropriate question/interaction type and complete grounded content;
- when a delayed recheck or transfer task is pedagogically useful within deterministic scheduling bounds;
- concise natural learner-facing message;
- the composition of the immediate scene only.

### 5.2 Deterministic backend controls

- authentication, document/session ownership, authorization;
- persistence, transactions, idempotency, and stale revision handling;
- deterministic grading where objective and bounded semantic evaluation otherwise;
- all concept evidence mutation;
- provenance validation and source-ID authorization;
- schemas, learner-content validation, tool allowlists and argument validation;
- rate limits, timeouts, maximum model/tool steps and token bounds;
- review queue persistence and allowed due categories;
- prerequisite branch validation/depth/cycle prevention;
- completion invariants and reports;
- telemetry and deterministic fallback.

The backend must not hardcode teach-versus-test, strategy/modality choice, whether to stay on the concept, or scaffold reduction as the normal path. Deterministic policy supplies safe fallback and invariant enforcement only.

### 5.3 Fallback observability contract

`LearnTutorEvent` must make model authority measurable. Record one bounded structured event for every decision attempt and every compatibility/fallback branch. Do not persist raw prompts, source text, learner free-form answers, or chain-of-thought.

Required event types and metadata:

| Event | Required metadata |
|---|---|
| `tutor_model_disabled` | session ID via relation, objective ID, scene revision, event type, configured provider name if known |
| `tutor_provider_failure` | objective ID, scene revision, bounded error class, latency, retry number |
| `tutor_output_validation_failure` | objective ID, scene revision, schema/content/provenance issue codes, retry number |
| `tutor_tool_rejected` | objective ID, scene revision, tool name, rejection reason; no unsafe raw arguments |
| `tutor_fallback_used` | objective ID, prior/new scene revision, fallback reason enum, selected fallback goal/operation kinds |
| `learn_legacy_compatibility_used` | prior runtime version, old objective/step cursor, conversion result, new scene revision |
| `tutor_decision_applied` | objective ID, prior/new scene revision, pedagogical goal, strategy, operation kinds, provider/fallback flag, model latency/token usage if available |

Required fallback reason enum:

```text
MODEL_DISABLED
PROVIDER_UNAVAILABLE
PROVIDER_TIMEOUT
PROVIDER_ERROR
STRUCTURED_OUTPUT_INVALID
CONTENT_INVALID
PROVENANCE_INVALID
TOOL_AUTHORIZATION_FAILED
NO_SAFE_MODEL_ACTION
LEGACY_SESSION_UPGRADE
```

Tests must assert that a fallback scene is still produced by `execute_scene_plan()`, has a new persisted revision, remains source-grounded, and emits the correct event. A provider fallback that changes `step_index` or calls `_choose_next_step()` is a test failure.

## 6. Frontend migration

### 6.1 Files and components

Change:

- `web/src/api/client.ts`: authoritative scene/event request and response types; deprecate step/action/feedback fields.
- `web/src/pages/Notes.tsx`: retain material mode/onboarding/report shell, extract active Learn runtime and remove direct legacy practice rendering.
- `web/src/index.css`: preserve Focus Mode styles while moving selectors to scene blocks and controlled visual layout.
- `web/src/learning/visuals/StructuredVisual.tsx`: controlled visual state and semantic event callbacks; remove global event listener.
- `web/src/learning/experiences/StepThroughMechanism.tsx`: controlled visual state/event callbacks.

Add:

- `web/src/learn/useLearnSession.ts`: session fetch/start/event/response/hint/Ask state, stale-scene recovery.
- `web/src/learn/LearningSceneView.tsx`: sole active-session scene renderer.
- `web/src/learn/LearningSceneBlockView.tsx`: block-kind dispatcher.
- `web/src/learn/LearnInteractionView.tsx`: extracted existing interaction controls.
- `web/src/learn/LearnVisualSurface.tsx`: shared controlled wrapper for StructuredVisual and Note/StepThrough references.
- `web/src/learn/AskLucentPanel.tsx`: lightweight Ask input/history using authoritative scene response.
- `web/src/learning/components/SectionComponentRenderer.tsx`: extracted Notes `ComponentView` shared by Notes and Learn.

### 6.2 Scene-only rendering cutover

Once the backend guarantees `scene` for active sessions:

- `LearningSceneView` iterates every scene block in server order;
- the `practice` block renders through `LearnInteractionView` inside the same scene;
- feedback is rendered from the single scene feedback block next to its practice;
- `LearnView` does not render `session.step`, `session.feedback`, or `session.action`;
- compatibility responses lacking a scene are upgraded by the backend, not reconstructed in React.

### 6.3 Ask Lucent

`AskLucentPanel` submits the current scene ID/revision. It receives a full updated session/scene, replaces local authoritative session state, and preserves unsent input only on failure. It does not dispatch browser-global events or merge blocks locally.

### 6.4 Focus Mode

Preserve the current fixed fullscreen overlay and centered teaching surface. Active Learn enters focus by default. The refactor must preserve:

- explicit exit and Escape;
- body-scroll lock;
- objective/progress as secondary chrome;
- contained Ask Lucent panel;
- focus transfer to new scene heading after revision;
- responsive stacking at laptop/narrow widths;
- visible keyboard focus and reduced-motion behavior.

## 7. Visual state migration

### 7.1 One owner

Canonical visual state lives only in `LearningScene.visualState`. Remove these competing authorities:

- top-level `session.state.visualStage`;
- top-level `session.state.visualHighlight`;
- legacy current `step.visualSpec` as runtime state;
- React `StructuredVisual` canonical stage state;
- the `lucent-visual-stage` global browser event.

The visual spec/ref is immutable content for a scene lineage; `visualState` is mutable revisioned state.

### 7.2 Visual lifecycle

1. **Create:** scene operation chooses an authorized Note component or validated `VisualSpec`, assigns bounded `visualKey`, and initializes state.
2. **Reuse:** later scene plans reference the same `visualKey`; executor preserves spec/ref and prior state unless explicitly changed.
3. **Stage/highlight/reveal:** visual event or tutor operation validates against the spec and creates a new scene revision.
4. **Animate:** renderer deterministically animates the transition between old and new canonical state; reduced motion jumps to the resulting state.
5. **Manipulate:** learner input is submitted with scene revision and parameter ID; server validates range/meaning and returns updated state.
6. **Assess:** prediction/label/solve practice references the same `visualKey` and stores its answer contract privately.
7. **Feedback:** feedback operation changes highlights/stage/narration on the same visual while preserving practice context.
8. **Transfer:** tutor may alter an allowlisted parameter or stage within the visual's semantic contract and replace practice, without discarding the visual lineage.
9. **Resume:** GET returns persisted scene and controlled renderers initialize exactly from `visualState`.

## 8. Student-facing language boundary

### 8.1 Internal-only models and fields

The following remain server/internal and must not be rendered or automatically copied into public blocks:

- `TutorObservation`;
- `TutorDecision.hypothesis`, `diagnosis`, `confidence`, `rationale`;
- `pedagogicalGoal`, `pedagogicalStrategy`, `teachingAction`;
- `scaffoldLevel`, concept/evidence state, review state;
- failed/successful strategies and modalities;
- remediation category/reason;
- tool names, arguments, results, validation failures;
- `expectedEvidence`, completion-policy diagnostics;
- provider/fallback metadata.

Remove `tutorHypothesis`, `strategy`, `pedagogicalGoal`, and `scaffoldLevel` from the public `LearningScene` API. Persist the latest validated values only in bounded `state.lastTutorDecision` and `LearnTutorEvent`; never duplicate them inside the public scene.

### 8.2 Learner-facing contracts

Public scene content is explicit:

```text
StudentMessage
  tone: encourage | clarify | correct | prompt | summarize
  text
  sourceSectionIds[]
  sourceBlockIds[]

StudentFeedback
  result: correct | partially_correct | incorrect | insufficient_evidence
  message
  correction?             optional subject-specific teaching
  respondsToInteractionId
```

Scene blocks contain only learner-facing content. Evaluation evidence and misconception records are transformed into `StudentFeedback` by a dedicated backend builder using the source context and validated tutor output.

### 8.3 Generation and validation point

Natural messages are generated in the tutor decision as explicitly marked `studentMessage`/content operations, then validated in `learn_scene.py` before persistence. Deterministic fallback messages are built from actual source propositions/entities only by `backend/app/services/learner_content.py`; no router or executor-local fallback wording is allowed.

Phrase filtering remains defense-in-depth. It is not the primary separation boundary. Frontend TypeScript scene types must not even include internal tutor fields.

## 9. Backwards compatibility and migration

### 9.1 Existing sessions

Implement `ensure_runtime_state(session)` in `learn_runtime.py`:

- if `state.runtimeVersion == 2` and `currentScene` validates, require a matching `currentScenePrivate` only when `responseInteractionId` is non-null; require `currentScenePrivate` to be absent/null for a teaching-only scene; then return unchanged;
- if `state.runtimeVersion == 2` but the persisted scene is corrupt, do not use the cursor runtime. Record validation failure and rebuild one grounded fallback scene from `currentObjectiveId`, objective source data, and authorized candidate assets; increment the revision once;
- if `currentScene` exists in the current draft format, accept old `responseStepId`, strip internal public fields, normalize it to `responseInteractionId`, copy old top-level `visualStage`/`visualHighlight` into `scene.visualState`, copy the greatest valid value from legacy `state.sceneRevision` and `currentScene.revision` into the normalized scene, recover the private interaction by exact ID from the objective candidate library, persist the normalized scene, delete `state.sceneRevision`, and mark `runtimeVersion=2`;
- if there is no persisted scene, read `objective_index`/`step_index` exactly once, locate that legacy objective/candidate, compose a source-grounded revision-1 compatibility scene, persist its private interaction, record `learn_legacy_compatibility_used`, and mark `runtimeVersion=2`;
- if the old cursor is out of range or the candidate is malformed, choose the first valid source-grounded objective by stable ID and create a teaching-only fallback scene; do not increment or scan the cursor as live progression;
- preserve concept evidence, attempts, misconceptions, revisit queue, branch stack, report, and stable legacy step IDs;
- treat old `LearnPlan.objectives[].steps[]` as read-only candidate assets after conversion; never append new steps during or after upgrade;
- remove old `sceneInterruption`, `visualStage`, `visualHighlight`, and standalone feedback keys after their information has been represented once in the normalized scene;
- make conversion idempotent: a second GET produces byte-equivalent scene content and the same revision.

### 9.2 Database migration

The authority cutover does not require a database migration because `LearnSession.state` and `plan` are JSON and already persisted. Add exactly `state.runtimeVersion=2` and `state.planSemanticsVersion=2`. Do not add a new top-level `LearnPlan` schema field in this migration. Existing plan JSON remains structurally unchanged; `state.planSemanticsVersion=2` records that `steps` are interpreted as a candidate library rather than an ordered runtime.

After the compatibility window and full acceptance suite pass, add one Alembic cleanup migration, expected next revision after `0008_learn_tutor_events`, to drop `learn_sessions.step_index`. Retain `objective_index` in this migration as a derived reporting/compatibility column, write it from `currentObjectiveId`, and prohibit runtime reads. Removing `objective_index` is outside this migration and requires a separate future data/API decision; the implementation agent does not need to decide its fate.

Dropping the cursor is preceded by an explicit convergence job, `backend/scripts/backfill_learn_runtime_v2.py`. It batches all active/stopped `LearnSession` rows, invokes the deterministic one-way adapter without provider calls, persists a valid version-2 scene/private pair (or a valid teaching-only/completed state), and records conversion telemetry. The script exits nonzero if any convertible row fails. `0009_drop_learn_step_index.py::upgrade()` must query for active/stopped rows whose JSON `runtimeVersion` is not `2` and abort with an actionable error instead of dropping the column. After the migration succeeds, delete the cursor-reading branch of `ensure_runtime_state()` and retain only normalization of old scene JSON fields that still exist inside `state`.

### 9.3 API compatibility

During rollout:

- active responses always include `scene`;
- `step`, `feedback`, `action`, `evaluation`, `stepIndex`, and `objectiveIndex` remain deprecated fields derived from scene/internal state for one compatibility phase;
- response/hint/Ask requests accept old payloads only for runtimeVersion 1 sessions; version 2 requires scene identity/revision;
- Ask response accepts `scenePatch` as an alias but also returns authoritative `scene`.

Phase 6 switches the repository frontend to scene-only rendering. Phase 9 removes `step`, `feedback`, `action`, `evaluation`, `stepIndex`, `scenePatch`, and `responseStepId` from current public schemas and TypeScript types. `objectiveIndex` remains as derived progress metadata for this migration but is never a content selector. After the Phase-9 backfill and migration, no deprecated public alias or cursor-reading compatibility path survives; `ensure_runtime_state()` may normalize old scene JSON but cannot read a removed database cursor.

### 9.4 Rollback/fallback

Before deleting `step_index`, rollback means reverting the scene-runtime commits together; runtime-version-2 sessions must not be routed through legacy progression. Once the deletion migration runs, rollback requires downgrading the migration (which restores a nullable column but does not reconstruct historical cursor values) and reverting application code together. The pre-drop database backup is therefore the only lossless rollback for legacy cursor values. The compatibility adapter is a one-way data normalization path for old records, not a selectable runtime or feature flag.

## 10. Execution phases

### Phase 1 — Freeze contracts and add migration characterization

**Goal:** lock the target public/private contracts and characterize old persisted formats before behavior changes.

**Add:** in `backend/app/schemas/learn.py`, add `TutorEvent`, discriminated event payloads, `LearningVisualState`, `StudentMessage`, `StudentFeedback`, `ScenePrivateState`, and a discriminated union of typed tutor tool calls. Add private `SceneExecutionResult` as a frozen dataclass in `backend/app/services/learn_scene.py`, and private `AuthorizedAssetCatalog` as a frozen dataclass in `backend/app/services/learn_runtime.py`. Create `backend/app/services/learner_content.py` and move `learner_text_quality_issues()` and `student_facing_quality_issues()` into it behind `validate_student_message()`, `validate_student_feedback()`, and `validate_public_scene()`; retain re-export shims in `learn_engine.py` through Phase 8. Add old-session and old-scene fixtures to `backend/tests/test_learn_scene.py` and `backend/tests/test_learn_api.py`.

**Modify:** change `LearningScene.responseStepId` to `responseInteractionId`; remove its public `pedagogicalGoal`, `tutorHypothesis`, `strategy`, `scaffoldLevel`, and internal `completionCondition`; make `visualState` strict; constrain `LearningSceneBlock` to learner-facing contracts. Update `compose_learning_scene()` in `backend/app/services/learn_scene.py` only enough to emit the new public shape while preserving current behavior. Add `sceneId`, `sceneRevision`, `interactionId`, and `eventType` to `LearnResponseRequest`; add scene/revision/interaction identity to the hint request model introduced here and to `AskLucentRequest`; add required authoritative `scene` to `AskLucentResponse` while retaining `scenePatch` as an alias. Mirror these types in `web/src/api/client.ts` without switching rendering yet.

**Routes/components touched:** request/response contracts consumed by `POST /learn-sessions/{session_id}/responses`, `POST /learn-sessions/{session_id}/hints`, and `POST /learn-sessions/{session_id}/ask`; `web/src/pages/Notes.tsx::LearnView` remains behaviorally unchanged and continues using deprecated fields during this phase.

**Bypass:** none; this phase is wire-compatible.

**Delete:** remove internal tutor fields from the new public scene model immediately. They remain only in `TutorDecision` and internal persisted state.

**Temporary compatibility:** accept `responseStepId` when parsing old scene JSON. Retain public `step`, `action`, `feedback`, `evaluation`, `stepIndex`, and `scenePatch` aliases until Phases 6 and 9.

**Dependencies:** none.

**Automated completion tests:** run `backend/venv/bin/pytest backend/tests/test_learn_scene.py backend/tests/test_learn_engine.py -q` and `(cd web && npm test)`. Assert zero/one response target, matching public/private IDs, bounded structures, strict tool arguments, internal-field exclusion, old-scene parsing, and invalid provenance rejection.

**Browser proof:** load one current Genetics and Pendulum session and record the existing scene ID/content as before-state fixtures. The application must still start and render; no behavioral acceptance is claimed.

**Completion criteria:** public scene construction cannot accept hypothesis/strategy/confidence, arbitrary tool arguments fail validation, and every old persisted format currently present in tests has a conversion fixture.

**Commit boundary:** `refactor: define authoritative learn scene contracts`. Do not begin Phase 2 until focused backend and existing frontend suites pass.

### Phase 2 — Introduce one tutor runtime and legacy adapter

**Goal:** create the sole runtime entry point and make persisted scenes authoritative on create/read/resume.

**Add:** implement the Phase-1 `backend/app/services/learn_runtime.py` with exact functions `ensure_runtime_state()`, `load_current_scene()`, `build_authorized_asset_catalog()`, `build_tutor_observation()`, `process_tutor_event()`, `apply_evaluation()`, `build_student_feedback()`, `persist_scene_revision()`, and `select_target_objective()`. Add `RUNTIME_VERSION = 2`, `PLAN_SEMANTICS_VERSION = 2`, and bounded stable-ID helpers.

**Modify:** update `create_learn_session()`, `get_learn_session()`, and `get_active_learn_session()` in `backend/app/routers/learn.py` to call the runtime. Make `_session_payload()` a pure serializer. Extend `backend/tests/test_learn_api.py` with idempotent GET and one-time conversion cases.

**Routes/components touched:** `POST /documents/{document_id}/learn-sessions`, `GET /learn-sessions/{session_id}`, and `GET /documents/{document_id}/learn-sessions/active`; no frontend component changes beyond consuming the still-compatible payload.

**Bypass:** all scene reconstruction inside `_session_payload()` and all cursor reads after `ensure_runtime_state()` returns version 2.

**Delete:** delete router `_persist_scene()` after callers use `learn_runtime.persist_scene_revision()`. Delete the scene-composition branch from `_session_payload()` in this phase.

**Temporary compatibility:** only `ensure_runtime_state()` may read old `objective_index`, `step_index`, `responseStepId`, `sceneInterruption`, `visualStage`, `visualHighlight`, and standalone feedback, exactly once. It writes normalized version-2 state and never runs legacy progression.

**Dependencies:** Phase 1.

**Automated completion tests:** run `backend/venv/bin/pytest backend/tests/test_learn_api.py backend/tests/test_learn_scene.py -q`. Assert revision 1 on start, byte-equivalent repeated GET, no GET provider call/revision increment, one-time old-session upgrade, grounded teaching-only recovery for malformed cursors, bounded history, and one compatibility telemetry event.

**Browser proof:** refresh an active session twice. Objective, blocks, interaction, visual state, scene ID, and revision remain unchanged; network inspection shows no provider request caused by GET.

**Completion criteria:** every active response contains a persisted scene and valid `currentScene` is never rebuilt during serialization.

**Commit boundary:** `refactor: centralize learn session runtime`. Run focused API tests and FastAPI import smoke before Phase 3.

### Phase 3 — Make scene executor and model decision authoritative

**Goal:** make the tutor decision plus scene executor—not step position—the authority for response, continue, and hint events.

**Add:** concrete scene-operation executors in `backend/app/services/learn_scene.py`; private scene-local interaction storage under `state.currentScenePrivate`; explicit uncertainty-signal normalization in `learn_runtime.py`; `extract_source_propositions()` and source-specific fallback scene/block builders in `backend/app/services/learner_content.py`.

**Modify:** replace `compose_learning_scene()` with `execute_scene_plan()` using Section 4's contract. Change `learn_tutor.py::choose_tutor_decision()` to receive current scene, event, evidence, failed strategies/modalities, authorized asset summaries, and retrieved source and to return typed operations. Restrict `adaptive_policy.py` to fallback intent and invariants. Make `evaluate_step()`/`diagnose_response()` grade `currentScenePrivate.interaction`. Rewrite `submit_learn_response()` and `get_learn_hint()` as thin runtime calls. Update `Notes.tsx`/`api/client.ts` requests to send scene/revision/interaction IDs while compatibility rendering remains.

**Routes/components touched:** `POST /learn-sessions/{session_id}/responses` and `POST /learn-sessions/{session_id}/hints`; `backend/app/schemas/learn.py::{TutorDecision,TutorObservation,TutorContentBlockDraft,SceneOperation,ScenePrivateState,LearnResponseRequest}`; `web/src/pages/Notes.tsx::LearnView` submit/hint handlers and `web/src/api/client.ts::{submitLearnResponse,getLearnHint}`.

**Bypass:** all cursor-based response selection and future-step scanning.

**Delete:** `_choose_next_step()`, `_append_remediation()`, `_leave_degenerate_repair_loop()`, `_action_for()`, and router `_strategy_for()` at the end of this phase. `_append_prerequisite_branch()` remains unused only until Phase 4 replaces and deletes it.

**Temporary compatibility:** public response `step` is derived from the scene practice block for the old frontend; `step_index` is never read or written after adapter conversion.

**Dependencies:** Phases 1–2.

**Automated completion tests:** run `backend/venv/bin/pytest backend/tests/test_learn_scene.py backend/tests/test_learn_api.py backend/tests/learn_agent_scenarios -q`. Assert multi-block model decisions, concrete applied tool deltas, immutable plan JSON, teaching before checking for “I don't know,” different operations for uncertainty and misconception, modality change after repeated failure, safe provider fallback, and no 500s.

**Browser proof:** in Genetics, submit a wrong answer and then `I don't know`. Each produces a different natural intervention in one scene lineage and neither advances merely to the next plan entry.

**Completion criteria:** code search finds no runtime call to deleted step selectors/appenders; model or scene fallback is the only source of next visible content; every applied teaching tool changes a block or visual state.

**Commit boundary:** `feat: drive learn through tutor scenes`. Run the scenario suite and focused backend tests before Phase 4.

### Phase 4 — Integrate prerequisite/review/completion transitions

**Goal:** implement stable-ID prerequisite, review, completion, and objective transitions without generating legacy steps.

**Add:** in `learn_runtime.py`, add `validate_branch_proposal()`, `push_prerequisite_branch()`, `return_from_prerequisite()`, `select_due_review()`, `apply_review_schedule()`, and scene-based `completion_met()`. Persist branch records with original concept, prerequisite concept, reason, depth, return scene ID, and return objective ID.

**Modify:** update `adaptive_policy.py::prerequisite_ids()` and `review_due()` for stable concept IDs/evidence; update `stop_learn_session()` and report generation in `learn.py` to avoid cursor assumptions; add learner-facing progress fields to `LearningScene`; extend `test_learn_api.py` and scenario harness.

**Routes/components touched:** `POST /learn-sessions/{session_id}/responses` for branch/return/review/advance, `POST /learn-sessions/{session_id}/stop`, and all three session create/read routes for restored branch/review state; public `LearningScene.progress`; no new frontend component is added here.

**Bypass:** `_next_objective()` positional behavior and any revisit-queue conversion to a step index.

**Delete:** `_append_prerequisite_branch()` and `_next_objective()` after new tests pass. Delete every remaining `session.step_index` write outside `ensure_runtime_state()`.

**Temporary compatibility:** `objective_index` is written as a derived value from `currentObjectiveId` for old report/UI consumers; it is never read to choose content.

**Dependencies:** Phase 3.

**Automated completion tests:** A depends on B/B weak branches and returns; B demonstrated does not branch; cyclic or depth-5 branch rejects; delayed review uses a different interaction/modality; Stop preserves branch/review/current scene; completion rejects unresolved required review. Run `backend/venv/bin/pytest backend/tests/test_learn_api.py backend/tests/learn_agent_scenarios -q`.

**Browser proof:** a procedural fixture visibly branches to prerequisite teaching, refreshes safely during the branch, and returns to the original problem with context restored.

**Completion criteria:** all transitions operate on concept/scene IDs and plan hash remains unchanged.

**Commit boundary:** `feat: transition learn concepts through scenes`. Full scenario suite must pass before Phase 5.

### Phase 5 — Make Ask Lucent a scene event

**Goal:** make Ask Lucent another event in the same observation/decision/executor path.

**Add:** `ASK_LUCENT` handling in `learn_runtime.process_tutor_event()` and an executor preservation rule that keeps active practice unless a validated decision explicitly replaces it.

**Modify:** retain `_get_owned_session()`, `_ask_rate_allowed()`, `_ask_scope()`, `_record_tutor_event()`, and `retrieve_note_context()` in `learn.py::ask_lucent()`, then call the shared runtime. Update the Ask prompt in `learn_tutor.py` to use the common decision/operation schema and current scene context. Return a concise answer plus required authoritative `scene`. Update frontend `askLucent()` to replace the session scene returned by the server.

**Routes/components touched:** `POST /learn-sessions/{session_id}/ask`; `backend/app/schemas/learn.py::{AskLucentRequest,AskLucentResponse,TutorEvent,TutorDecision}`; `web/src/api/client.ts::{AskLucentResponse,askLucent}`; the Ask handler inside `web/src/pages/Notes.tsx::LearnView` until it is extracted in Phase 6.

**Bypass:** keyword-to-action mapping and separate Ask scene-plan construction in the router.

**Delete:** production `sceneInterruption` reads/writes, Ask-only fallback block construction, and Ask tool paths that only set a tool string without a concrete mutation.

**Temporary compatibility:** `AskLucentResponse.answer` remains for lightweight panel history; `scenePatch` aliases `scene` until Phase 9. The old global visual event exists only until Phase 7 and is not used by the new Ask path.

**Dependencies:** Phases 2–4.

**Automated completion tests:** exact prompts “Explain another way,” “Give me an example,” and “Show me visually”; authorized existing/no-existing visual cases; invalid tool/ID; evidence immutability; persisted refresh; rate limit, relevance, prompt injection, and telemetry transaction safety. Run `backend/venv/bin/pytest backend/tests/test_learn_api.py backend/tests/learn_agent_scenarios -q`.

**Browser proof:** all three prompts visibly and persistently alter the central scene when appropriate. Chat text alone fails the example and visual cases.

**Completion criteria:** both normal response and Ask routes invoke `process_tutor_event()` and `execute_scene_plan()`; code search finds no production `sceneInterruption` access.

**Commit boundary:** `feat: route ask lucent through tutor scenes`. Security and transaction tests must pass before Phase 6.

### Phase 6 — Cut frontend over to scene-only rendering

**Goal:** make `session.scene` the only active Learn renderer while preserving Focus Mode and existing interaction mechanics.

**Add:** `web/src/learn/useLearnSession.ts`, `LearningSceneView.tsx`, `LearningSceneBlockView.tsx`, `LearnInteractionView.tsx`, `LearnVisualSurface.tsx`, and `AskLucentPanel.tsx`. Extract `web/src/learning/components/SectionComponentRenderer.tsx` from `Notes.tsx::ComponentView()`.

**Modify:** retain onboarding/report/mode/focus shell in `Notes.tsx::LearnView`; delegate active sessions to the hook/view. Update `api/client.ts` to require scene identity/revision for response/hint/Ask. Update `index.css` for one integrated scene canvas, responsive Ask containment, focus behavior, and one feedback location.

**Routes/components touched:** all existing Learn client methods for create/get/active/response/hint/ask/stop; `LearnView`, new `LearningSceneView`, `LearningSceneBlockView`, `LearnInteractionView`, `LearnVisualSurface`, `AskLucentPanel`, and shared `SectionComponentRenderer`.

**Bypass:** direct reads of `session.step`, `session.feedback`, `session.action`, and `session.evaluation` in active Learn.

**Delete:** `SceneSupportBlocks`, legacy practice JSX inside `LearnView`, duplicate feedback rendering, local resets derived from `updated.step`, and local `ComponentView` after both consumers use the shared renderer.

**Temporary compatibility:** backend deprecated fields may still exist until Phase 9, but no repository JSX reads them. Runtime-version-1 records are normalized server-side.

**Dependencies:** Phases 2–5.

**Automated completion tests:** active-session tests in `LearnTutorSmoke.test.tsx` plus tests under `web/src/learn/` for ordered multi-block rendering, one practice form, feedback once, all existing interaction payloads, response/Ask replacement, stale `409` recovery, Focus Mode Escape/focus/scroll, and internal-field non-rendering. Run `(cd web && npm test)` and `(cd web && npm run build)`.

**Browser proof:** Genetics and Pendulum each display explanation, visual/example, practice, and feedback in one centered continuous scene; the Ask panel is contained at laptop/narrow widths.

**Completion criteria:** `rg "session\.step|SceneSupportBlocks|session\.feedback|session\.action" web/src/pages web/src/learn` finds no active-session rendering use.

**Commit boundary:** `feat: render authoritative learning scenes`. Frontend suite/build and focused backend API tests must pass before Phase 7.

### Phase 7 — Unify visual state and controlled renderers

**Goal:** establish one canonical visual state and make existing renderer families controlled.

**Add:** `POST /learn-sessions/{session_id}/visual-events` in `backend/app/routers/learn.py`; visual operation validation/execution in `learn_scene.py`; controlled visual props/event types in `LearnVisualSurface`.

**Modify:** `StructuredVisual.tsx` and `StepThroughMechanism.tsx` accept canonical `visualState` and `onVisualEvent`; local state is limited to ephemeral animation/modal presentation. `SectionComponentRenderer` accepts controlled Learn props while Notes remains static. Ask/remediation use the same scene visual operations.

**Routes/components touched:** new `POST /learn-sessions/{session_id}/visual-events` handled by `backend/app/routers/learn.py::handle_learn_visual_event()`; `backend/app/schemas/learn.py::{LearningVisualState,VisualEventRequest,TutorEvent}`; `LearnVisualSurface`, `StructuredVisual`, `StepThroughMechanism`, and `SectionComponentRenderer`.

**Bypass:** top-level session visual fields and imperative browser events.

**Delete:** `lucent-visual-stage` listener/dispatch, production reads/writes of `state.visualStage` and `state.visualHighlight`, and component-local canonical stage initialized independently after mount.

**Temporary compatibility:** only `ensure_runtime_state()` reads old visual fields and converts them once. Notes may keep local navigation because it is not persisted Learn state.

**Dependencies:** Phase 6 and Phase 5 Ask integration.

**Automated completion tests:** backend authorized/stale visual events, invalid stage/element, persistence, and prediction evidence; frontend controlled rerender, stable `visualKey`, reduced motion, fullscreen state, and Notes regression. Run `backend/venv/bin/pytest backend/tests/test_learn_scene.py backend/tests/test_learn_api.py -q`, `(cd web && npm test)`, and `(cd web && npm run build)`.

**Browser proof:** Pendulum retains one visual through WATCH → PREDICT → wrong answer → reveal/highlight → explanation → transfer. Refresh restores the exact stage/highlight; Ask changes the surface without a global event.

**Completion criteria:** code search finds one persisted visual-state path, `currentScene.visualState`, and every learner-significant change creates a server revision.

**Commit boundary:** `feat: persist tutor controlled visual state`. Visual resume and reduced-motion tests must pass before Phase 8.

### Phase 8 — Student-language boundary and content-quality cutover

**Goal:** make internal orchestration structurally impossible to expose and require source-specific educational content.

**Add:** extend the existing `backend/app/services/learner_content.py` boundary with structured issue codes, plausible-distractor validation, source-aware identifier handling, and one bounded provider correction retry; add no second content service.

**Modify:** remove the Phase-1 re-export shims from `learn_engine.py` and update every remaining caller to import `learner_content.py`; make `learn_runtime.build_student_feedback()` transform private evaluation/diagnosis; validate every public block in `learn_scene.execute_scene_plan()`; make `learn_tutor.py` request explicit learner-facing fields. Remove internal tutor metadata from public backend and TypeScript contracts.

**Routes/components touched:** every route returning `LearnSessionResponse` or `AskLucentResponse`; `backend/app/schemas/learn.py::{LearningScene,LearningSceneBlock,StudentMessage,StudentFeedback,LearnSessionResponse,AskLucentResponse}`; `web/src/api/client.ts` matching public types; `LearningSceneBlockView` and `LearnInteractionView` as the only student-message/feedback renderers.

**Bypass:** raw evaluation evidence, misconception, transition, strategy, state, or rationale as UI copy.

**Delete:** phrase-replacement logic in `_session_payload()`/old scene compiler, public action/evaluation/internal scene fields, and JSX displaying them.

**Temporary compatibility:** the adapter may parse internal fields from old scenes but strips them before writing version 2. No current API returns them.

**Dependencies:** Phase 6 scene-only rendering and Phase 1 public/private contracts.

**Automated completion tests:** reject meta phrases, schema names, unsupported snake_case, raw IDs, generic/duplicate distractors, and contextless prompts; allow source-supported code identifiers; require source-specific Genetics/Pendulum/procedural fallbacks and exactly one feedback block. Run `backend/venv/bin/pytest backend/tests/test_learn_engine.py backend/tests/test_learn_scene.py backend/tests/test_learn_api.py backend/tests/learn_agent_scenarios -q`, `(cd web && npm test)`, and `(cd web && npm run build)`.

**Browser proof:** correct, incomplete, misconception, `idk`, and `I'm not sure` show concise natural tutoring, no duplicate feedback, and no “next move,” state, evidence, strategy, or schema language in the DOM.

**Completion criteria:** public OpenAPI/TypeScript scene types contain no internal tutor fields and every persisted public scene passes the shared validator.

**Commit boundary:** `fix: enforce learner facing tutor language`. Backend scenario and frontend suites/build must pass before cleanup.

### Phase 9 — Gold scenarios, stress, and compatibility removal

**Goal:** prove vertical behavior, delete compatibility APIs/control paths, and make duplicate authority impossible.

**Add:** scene-aware traces to `backend/tests/learn_agent_scenarios/harness.py`; deterministic gold providers/browser fixtures; `backend/scripts/backfill_learn_runtime_v2.py`; `backend/migrations/versions/0009_drop_learn_step_index.py` with `down_revision = "0008_learn_tutor_events"`, a precondition rejecting unconverted active/stopped sessions, dropping `learn_sessions.step_index` on upgrade, and restoring a nullable integer column on downgrade.

**Modify:** update scripted/E2E/API/frontend tests to assert Section 12; finalize `LearnSessionResponse` and `api/client.ts`; allow `objective_index` writes only as derived reporting metadata; remove `step_index` from `backend/app/models/learn.py::LearnSession`; remove the cursor-reading branch from `ensure_runtime_state()` after the backfill/migration gate.

**Routes/components touched:** final contracts for every Learn route in Section 3.0; `backend/app/models/learn.py::LearnSession`; `backend/app/routers/learn.py`; `backend/app/schemas/learn.py`; `web/src/api/client.ts`; `web/src/pages/Notes.tsx::LearnView`; every component under `web/src/learn/`; controlled visual renderers; scenario, API, frontend, and migration tests.

**Bypass:** none. No selectable legacy runtime exists at phase end.

**Delete:** every item in Section 11, deprecated public aliases, obsolete fake-provider fields, cursor-progression tests, and unused imports/functions found by `rg`.

**Temporary compatibility:** none for cursor progression at phase end. `ensure_runtime_state()` remains only as an idempotent old-scene-JSON sanitizer; it cannot read `step_index`, choose content by position, or run after a valid `runtimeVersion=2` scene is present.

**Dependencies:** Phases 1–8.

**Automated completion tests:** run `backend/venv/bin/pytest backend/tests/test_learn_scene.py -q`; `backend/venv/bin/pytest backend/tests/learn_agent_scenarios -q`; `backend/venv/bin/pytest backend/tests -q`; `backend/venv/bin/python -m compileall -q backend/app backend/tests`; `(cd backend && venv/bin/python -c 'from app.main import app; assert app')`; `(cd web && npm test)`; `(cd web && npm run build)`; on an isolated copy of the migration-test database run `backend/venv/bin/python backend/scripts/backfill_learn_runtime_v2.py --apply`, then `backend/venv/bin/python backend/scripts/backfill_learn_runtime_v2.py --check`, `backend/venv/bin/alembic -c backend/alembic.ini upgrade 0009_drop_learn_step_index`, `backend/venv/bin/alembic -c backend/alembic.ini downgrade 0008_learn_tutor_events`, and `backend/venv/bin/alembic -c backend/alembic.ini upgrade heads`; then run `git diff --check`. Include the 50-cycle bounded-state/no-loop/no-500 stress, a migration-precondition failure fixture, and static `rg` assertions proving deleted paths absent.

**Browser proof:** execute every Section 12 scenario at desktop and narrow widths, including model-disabled/provider-failure fallback; record input, prior/new scene revision, visible mutation, and restored state after refresh.

**Completion criteria:** all Section 13 gates pass, cleanup migration is applied, and no runtime/frontend path can derive visible content from `step_index`.

**Commit boundary:** `refactor: remove legacy learn progression`. Run all final validation before committing; do not push.

## 11. Deletion phase

Deletion is staged; obsolete code must be removed as soon as its replacement has passed the named gate. Do not wait until the final commit when earlier deletion is safe.

| Obsolete path/state | Delete in | Deletion unlocked by | Required verification immediately before deletion |
|---|---|---|---|
| `_session_payload()` rebuilding `currentScene` from cursors | Phase 2 | `ensure_runtime_state()` persists/returns valid scenes | Idempotent GET and old-session conversion tests. |
| router `_persist_scene()` | Phase 2 | all writes use `persist_scene_revision()` | Scene revision/history tests and call-site `rg`. |
| `_choose_next_step()` | Phase 3 | response/continue/hint all call `process_tutor_event()` | Ignorance, wrong answer, provider fallback and no-plan-mutation tests. |
| `_append_remediation()` | Phase 3 | executor can add teaching plus scene-local practice | Repeated-failure scenario proves no plan mutation. |
| `_leave_degenerate_repair_loop()` | Phase 3 | bounded runtime strategy/review policy exists | 50-cycle unit subset and bounded state test. |
| `_action_for()` | Phase 3 | decision/fallback emits typed scene operations | Provider and fallback scene tests. |
| router `_strategy_for()` | Phase 3 | model chooses strategy; `adaptive_policy.py` supplies fallback only | Test showing same interaction can receive different strategies from evidence. |
| `_append_prerequisite_branch()` | Phase 4 | stable-ID branch push/pop is implemented | A→B→A, demonstrated-B, cycle/depth and refresh tests. |
| `_next_objective()` cursor behavior | Phase 4 | `select_target_objective()` and scene transitions work | review/objective completion tests. |
| `sceneInterruption` compatibility logic | Phase 5 | Ask Lucent uses shared runtime operations | Ask recomposition/persistence tests and `rg` excluding adapter fixture handling. |
| Router Ask keyword scene construction | Phase 5 | Ask decision/fallback both use executor | exact three-prompt Ask tests. |
| `SceneSupportBlocks` | Phase 6 | `LearningSceneView` renders all blocks | active multi-block frontend tests. |
| direct `session.step` rendering | Phase 6 | `LearnInteractionView` reads scene practice | all interaction frontend tests and browser response submission. |
| standalone frontend/session feedback | Phase 6 | one feedback scene block renders | duplicate-feedback test. |
| global `lucent-visual-stage` event | Phase 7 | controlled visual event route/props work | Ask visual, wrong prediction and resume tests. |
| top-level `visualStage`/`visualHighlight` production state | Phase 7 | `currentScene.visualState` works | persisted visual-state tests. |
| transition phrase-replacement/rendering path | Phase 8 | explicit `StudentMessage`/`StudentFeedback` boundary works | content validator and DOM leakage tests. |
| `LearningScene.responseStepId` current alias | Phase 9 | all old scenes normalize and clients use `responseInteractionId` | legacy normalization plus API/frontend code search. |
| `TutorDecision.nextStepId` | Phase 9 | typed scene operations/provider fixtures fully migrated | provider schema/fake tests and production `rg`. |
| free-form `TutorToolCall.arguments` | Phase 9 | every tool has typed schema | malformed/unknown argument tests. |
| public `step`, `action`, `feedback`, `feedbackKind`, `evaluation`, `stepIndex` | Phase 9 | repository frontend has used scene-only responses since Phase 6 | full frontend/API suite and API-contract fixtures. |
| Ask `scenePatch` alias | Phase 9 | all clients consume required `scene` | frontend/API code search. |
| old-session adapter's `session.step_index` read | Phase 9, after backfill | convergence script reports zero unconverted active/stopped sessions | backfill idempotency/failure tests plus production code search. |
| all other live `session.step_index` reads/writes | Phase 9 | version-2 runtime has been authoritative since Phase 3 | production code search before migration. |
| `learn_sessions.step_index` column | Phase 9 cleanup migration | backfill succeeds, migration precondition reports zero unconverted rows, and no code/test/API reference remains | full suites plus upgrade/downgrade/precondition smoke. |

During Phases 2–8, `ensure_runtime_state()` is the isolated one-way old-session adapter and may read an old cursor exactly once. In Phase 9, run the convergence job, drop `step_index`, and delete that cursor branch. Retain `ensure_runtime_state()` only for idempotent normalization/recovery of old scene JSON; it may not be selected by configuration, run for a valid version-2 scene, or perform progression. Retain `objective_index` solely as a derived reporting column in this migration; no control flow may read it.

## 12. Vertical acceptance tests

Each test must traverse browser event → endpoint → observation → decision → concrete scene operations → persisted revision → API response → React rendering. Unit-only proof is insufficient. Capture the before/after scene IDs and revisions, rendered text, block kinds, visual key/state, private evidence delta, and fallback telemetry.

| Scenario | Exact input | Expected tutor reasoning category | Required scene mutation | Expected visible UI | Expected evidence/state change | Explicit pass/fail |
|---|---|---|---|---|---|---|
| “I don't know” | Submit `I don't know` to a teach-back/free-response prompt | `INSUFFICIENT_EVIDENCE` or knowledge gap; goal `BUILD_INTUITION`/`EXPLAIN_CONCEPT` | Preserve relevant context; add grounded explanation plus example/visual; optionally add a simpler later check, never an immediate equivalent/harder check alone | Natural message such as “No problem—let's build the idea first,” followed by actual instruction | Record uncertainty/insufficient evidence and attempt; do not add misconception or demonstration | Pass only if teaching is visible before new evidence is demanded and no duplicate question appears. |
| “I'm not sure” | Submit `I'm not sure` | `UNCERTAINTY`; minimal clarification/probe | Preserve scene and add a small hint, distinction, or confidence-calibrating probe; do not perform full misconception correction without evidence | Concise acknowledgement and limited scaffold distinct from “I don't know” | Record uncertainty/insufficient evidence; no confident misconception; scaffold may increase at most one level | Pass only if intervention differs visibly from ignorance and confident misconception. |
| Confident misconception | In Pendulum, submit “Kinetic energy is highest at the turning point because all the energy is there” | `MISCONCEPTION`; goal `CORRECT_MISCONCEPTION` | Append specific feedback; reuse/change visual or add contrast/counterexample; later create a different independent check | Names velocity-versus-total-energy distinction without internal diagnosis labels | Persist misconception only at sufficient confidence; mark failed strategy/modality; schedule later review | Pass only if the scene teaches the exact distinction and later tests a different case. |
| Repeated failure | Give two incorrect answers to the same concept/representation | repeated unresolved misconception/knowledge gap; switch strategy or inspect prerequisite | Replace failed representation, preserve useful context, and optionally branch/schedule review; never clone the question | Learner sees a genuinely different explanation, example, visual, worked step, or prerequisite lesson | Increment attempts; retain failed strategies/modalities; bounded branch/review state | Fail on identical/equivalent question, harder unscaffolded question, growing repair IDs, or >4 branch depth. |
| Ask: explain another way | Ask `Explain this another way.` while practice is active | learner-requested alternate representation; usually `ANALOGY`, `CONTRAST_CASE`, or concise explanation | Add/replace explanation block while preserving active practice and visual unless explicitly changed | Alternate grounded explanation appears on central teaching surface; panel may also show concise reply | No graded evidence mutation; scene revision increments once; tutor-action history updates internally | Pass only if central scene visibly changes and refresh preserves it. |
| Ask: give example | Ask `Give me an example.` | concrete example supporting current goal | Add grounded example block tied to current concept/source; preserve active practice | Subject-specific example appears in active scene | No graded evidence mutation; one scene revision; provenance stored | Pass only if example is source-grounded, visible centrally, and not chat-only. |
| Ask: show visually | Ask `Show me visually.` on a visual-suitable concept | `VISUAL_MODEL`/`ANIMATED_MECHANISM` | Reuse current authorized visual and change stage/highlight, or add an authorized visual block with `visualKey` | Central scene shows/changes visual plus useful narration | No graded evidence mutation; canonical visual state changes in scene; one revision | Fail if only chat text/tool metadata changes or if global event state disappears on refresh. |
| Wrong visual prediction | Choose wrong answer to a prediction attached to Pendulum/process visual | misconception/knowledge gap tied to current visual evidence | Keep same `visualKey`; reveal/animate/highlight explanatory state; append targeted feedback; add explanation or scaffolded follow-up using the same surface | Prediction, reveal, explanation, and next task remain one visual lesson | Record incorrect prediction and failed modality only as appropriate; schedule later recheck | Pass only if the same visual changes meaningfully and feedback explains the visible change. |
| Prerequisite repair | Fail a quantitative task where authorized prerequisite evidence is weak | `PREREQUISITE_GAP`; goal `REPAIR_PREREQUISITE` | Push branch, compose prerequisite scene, then restore/recompose original concept scene after prerequisite evidence | Workspace clearly teaches prerequisite and later returns to original problem | Branch stack persists; prerequisite evidence updates separately; original concept not falsely demonstrated | Pass only if refresh works mid-branch, loops are bounded, and return target is preserved. |
| Scaffold fading | Complete guided quantitative steps correctly without extra hints | `GUIDE_PRACTICE` then `REDUCE_SCAFFOLDING` | Successive scenes visibly remove equation/structure/hints: FULL → GUIDED → PARTIAL → INDEPENDENT → TRANSFER | Learner sees progressively less supplied work, not only changed metadata | Assisted success remains developing; independent success strengthens application; transfer strengthens transfer evidence | Pass only if prompt/surface materially changes at every level and heavy assistance never marks demonstrated alone. |
| Transfer problem | After independent success, solve a differently framed application | `TEST_TRANSFER` | Replace practice with a new-context problem while preserving concise relevant concept context | Different application/context, not longer paraphrase | Correct result increments transfer evidence and may support demonstration/future review | Pass only if source concept is the same, context is meaningfully new, and no answer leakage exists. |
| Refresh/resume | Refresh after response, Ask mutation, visual state change, and during prerequisite branch | no new tutor reasoning on GET | No mutation; serialize stored scene exactly | Exact objective, blocks, feedback, practice, visual state, and branch context restored | No attempt/evidence/revision/provider event added | Pass only if repeated GETs are idempotent and visually identical. |
| Provider/model failure fallback | Disable model, simulate timeout, invalid structured output, and invalid tool separately | deterministic safe fallback with reason telemetry | Scene executor creates grounded teaching/practice mutation using authorized assets; never legacy progression | Coherent subject-specific scene with no error/debug wording | Normal deterministic evidence changes only for submitted response; fallback event stored | Fail if `step_index` changes, plan mutates, generic/meta text appears, response 500s, or fallback event is missing. |

Gold subject runs:

- **Genetics:** proto-oncogene versus tumor suppressor comparison, wrong classification, targeted contrast, teach-back, independent transfer.
- **Pendulum:** persistent energy visual, prediction, wrong turning-point misconception, reveal/highlight, explanation, amplitude transfer.
- **Procedural/math:** worked example, substitution error, targeted guided step, scaffold fading, independent and transfer problem.

## 13. Stop conditions

The migration is not complete unless all are true:

- active `LearningScene` is persisted and authoritative on every active response;
- `step_index` does not independently choose learner-visible progression;
- `LearnPlan.steps` is not mutated and is not interpreted as a script;
- Ask Lucent enters the same tutor runtime and mutates the same authoritative scene;
- every successful teaching tool produces a concrete scene or visual mutation;
- visual state has exactly one canonical owner;
- frontend active Learn renders only `session.scene`;
- legacy rendering/progression code is deleted or confined to a one-time compatibility adapter;
- internal tutor metadata is absent from public frontend types and cannot render directly;
- learner-facing text is subject-specific, source-grounded and validated;
- uncertainty, ignorance, misconception and repeated failure produce visibly different appropriate teaching;
- prerequisite, delayed review, scaffold fading and transfer work through scene transitions;
- refresh/resume is idempotent and restores the same scene revision;
- Genetics, Pendulum and procedural browser scenarios pass;
- scenario/stress, backend, frontend, build, compile/startup and diff validation pass.

Passing schema tests, mocked decisions, or scene JSON assertions alone does not satisfy these conditions.

### Final deletion gate

Phase 9 cannot be marked complete and the cleanup commit cannot be created until all of the following are simultaneously true:

- duplicate learner-facing authorities are gone;
- `_choose_next_step()`, remediation/prerequisite step appenders, `_action_for()`, router `_strategy_for()`, and cursor-based scene rebuilding are deleted from production code;
- old frontend `session.step` and standalone feedback rendering are deleted;
- `currentScene.visualState` is the only persisted visual owner and the global visual event path is deleted;
- Ask Lucent invokes the same runtime and executor as normal responses;
- persisted scene restore is idempotent across response, Ask, visual, review, and prerequisite states;
- deprecated response fields/aliases listed in Section 11 are removed;
- the cleanup migration drops `step_index` and passes upgrade/downgrade smoke tests;
- every vertical acceptance scenario passes in the real browser or is explicitly marked blocked by an external environment restriction, never inferred from unit tests.

If any item fails, the migration remains incomplete even if all unit tests pass.

## 14. Contradiction audit and resolved ownership

The following apparent dual-ownership cases were found in the pre-migration plan/current repository and are resolved here. Implementation must preserve the resolution in the rightmost column.

| Concern | Conflicting current owners | Final sole authority | Resolution |
|---|---|---|---|
| Learner-visible progression | `step_index`, `_choose_next_step()`, model `nextStepId`, and scene compiler | `learn_runtime.process_tutor_event()` applying a validated `TutorDecision` through `execute_scene_plan()` | Cursors are compatibility input only; `nextStepId` is removed; model/fallback scene operations choose immediate experience. |
| Current scene | Recomputed `_session_payload()` scene and persisted `state.currentScene` | persisted `state.currentScene` | GET serializes only. Scene creation/mutation occurs only in runtime/executor. |
| Scene revision | legacy `state.sceneRevision` and `currentScene.revision` | `state.currentScene.revision` | Adapter folds the old counter into the scene once and deletes it; persistence increments only the new scene's revision. |
| Current interaction | `session.step`, plan step at cursor, scene practice block, `responseStepId` | scene public practice block plus matching `state.currentScenePrivate.interaction` | Response requests use `responseInteractionId`; standalone `step` is deleted. |
| Visual state | top-level session state, `LearningScene.visualState`, step spec, component local state, global event | `state.currentScene.visualState` | Spec/ref is content; scene visual state is canonical; local motion is ephemeral. |
| Learner communication | transition message, evaluation evidence, misconception, session feedback, scene blocks | validated `StudentMessage`/`StudentFeedback` blocks | Internal outputs are never public; phrase filtering is secondary only. |
| Ask Lucent | Ask model/tool loop, router keyword patch logic, normal tutor loop | normal tutor runtime/executor with `ASK_LUCENT` event | Router retains only security/relevance/retrieval adapter responsibilities. |
| Pedagogical strategy | `_strategy_for()`, content policy map, model decision | bounded model decision; deterministic fallback only on explicit model failure | Remove router mapping; fallback usage is observable and uses the same executor. |
| Objective selection | `objective_index`, `state.currentObjectiveId`, `_next_objective()`, review queue, model target | active `currentScene.objectiveId`; otherwise a validated runtime transition target | `state.currentObjectiveId` is transition-only and must equal the active scene objective; `objective_index` is derived reporting metadata only. |
| Remediation | plan-appended repair steps and model scene actions | scene operations chosen by tutor/fallback | Plan never mutates; repeated failures update evidence and create bounded scene revisions. |
| Prerequisite control | appended prerequisite step and branch stack | validated stable-ID branch stack plus scene transition | No prerequisite step generation; return target is a scene/concept ID. |
| Resume | cursor reconstruction and persisted scene | persisted scene; one-time adapter only when absent/old | GET never replans or advances a version-2 session. |

No unresolved ownership contradiction remains in this plan. If implementation discovers a new competing writer/renderer, it must be assigned to the authoritative runtime or deleted before the phase completes.

## 15. Final file-by-file execution checklist

Work down this list in order:

- [ ] **Phase 1 — Contracts and characterization**
  - Files: `backend/app/schemas/learn.py`, `backend/app/services/learn_scene.py`, new `backend/app/services/learn_runtime.py`, new `backend/app/services/learner_content.py`, `backend/app/services/learn_engine.py`, `backend/tests/test_learn_scene.py`, `backend/tests/test_learn_api.py`, `backend/tests/test_learn_engine.py`, `web/src/api/client.ts`.
  - Changes: typed events/tools, strict visual state, public/private scene and student-language contracts, central content boundary, compatibility aliases/fixtures.
  - Tests: focused scene/engine tests and existing frontend suite.
  - Browser proof: current Genetics/Pendulum sessions still load for before-state capture.
  - Deletion unlocked: internal tutor fields from public scene contract.

- [ ] **Phase 2 — Runtime and one-way legacy adapter**
  - Files: new `backend/app/services/learn_runtime.py`; `backend/app/routers/learn.py`; `backend/tests/test_learn_api.py`; `backend/tests/test_learn_scene.py`.
  - Changes: persisted-scene reads, one-time old-session normalization, pure payload serialization, atomic revision/history.
  - Tests: idempotent GET, no GET provider call, old/no/malformed scene conversion, bounded history.
  - Browser proof: two refreshes return identical scene/revision.
  - Deletion unlocked: `_session_payload()` scene rebuilding and router `_persist_scene()`.

- [ ] **Phase 3 — Authoritative tutor decision and scene executor**
  - Files: `learn_runtime.py`, `learn_scene.py`, `learn_tutor.py`, `adaptive_policy.py`, `learn_engine.py`, `learn.py`, `Notes.tsx`, `api/client.ts`, scene/API/scenario tests.
  - Changes: response/continue/hint enter common runtime; model/fallback emits typed operations; executor makes concrete scene mutations; private scene-local practice is graded.
  - Tests: ignorance, uncertainty, misconception, repeated failure, model failure, immutable plan, applied tool deltas, no 500.
  - Browser proof: wrong and `I don't know` Genetics responses create different teaching scenes without positional advancement.
  - Deletion unlocked: `_choose_next_step()`, `_append_remediation()`, `_leave_degenerate_repair_loop()`, `_action_for()`, router `_strategy_for()`.

- [ ] **Phase 4 — Stable concept transitions**
  - Files: `learn_runtime.py`, `adaptive_policy.py`, `learn.py`, `test_learn_api.py`, scenario harness/tests.
  - Changes: prerequisite branch stack, delayed review, stable objective target, completion/stop/report integration.
  - Tests: A→B→A, demonstrated prerequisite, cycle/depth, review, Stop/resume, completion.
  - Browser proof: procedural prerequisite branch survives refresh and returns to original problem.
  - Deletion unlocked: `_append_prerequisite_branch()`, `_next_objective()` cursor behavior, all non-adapter `step_index` writes.

- [ ] **Phase 5 — Ask Lucent through the same runtime**
  - Files: `learn.py::ask_lucent()`, `learn_runtime.py`, `learn_tutor.py`, `learn_scene.py`, `api/client.ts`, `Notes.tsx`/`AskLucentPanel`, API/scenario tests.
  - Changes: Ask event observation/decision/execution, scene-preserving explanation/example/visual operations, authoritative returned scene.
  - Tests: exact three Ask prompts, security, relevance, rate limit, transaction safety, invalid tool/ID, evidence immutability, refresh.
  - Browser proof: explanation, example and visual requests change the central persisted scene.
  - Deletion unlocked: `sceneInterruption`, router keyword scene logic, Ask-only fallback scene, no-op Ask tools.

- [ ] **Phase 6 — Scene-only frontend**
  - Files: new `web/src/learn/*`; new shared `SectionComponentRenderer.tsx`; `Notes.tsx`; `api/client.ts`; `index.css`; frontend tests.
  - Changes: active Learn renders ordered scene blocks including practice/feedback; one session hook owns requests; Focus Mode preserved.
  - Tests: multi-block scene, every existing interaction renderer, feedback once, Ask update, stale recovery, keyboard/focus/scroll, build.
  - Browser proof: Genetics/Pendulum are continuous centered teaching surfaces at desktop and narrow width.
  - Deletion unlocked: `SceneSupportBlocks`, direct `session.step` JSX, standalone feedback JSX, local `ComponentView`.

- [ ] **Phase 7 — One visual-state owner**
  - Files: `learn.py` visual-event route, `learn_runtime.py`, `learn_scene.py`, `LearnVisualSurface.tsx`, `StructuredVisual.tsx`, `StepThroughMechanism.tsx`, shared renderer, tests.
  - Changes: controlled visual props/events, authorized persisted stage/highlight/reveal/parameter operations, visual reuse across scenes.
  - Tests: stale/invalid/authorized events, prediction evidence, controlled rerender, resume, reduced motion, Notes regression.
  - Browser proof: one Pendulum visual persists through prediction, correction, explanation and transfer, including refresh.
  - Deletion unlocked: global visual event and top-level/session/component canonical visual state.

- [ ] **Phase 8 — Learner-language and content boundary**
  - Files: `backend/app/services/learner_content.py`; `learn_engine.py`; `learn_runtime.py`; `learn_scene.py`; `learn_tutor.py`; `backend/app/schemas/learn.py`; `web/src/api/client.ts`; `web/src/learn/LearningSceneBlockView.tsx`; `web/src/learn/LearnInteractionView.tsx`; tests.
  - Changes: explicit student feedback/messages, source-proposition fallback, all-public-block validation, internal metadata removed from API/UI.
  - Tests: banned leakage, source-aware identifiers, plausible distractors, grounded fallback, one feedback block, DOM inspection.
  - Browser proof: correct/incomplete/misconception/idk/uncertain states show natural distinct tutoring with no debug language.
  - Deletion unlocked: phrase-rewrite path and public action/evaluation/tutor metadata.

- [ ] **Phase 9 — Vertical proof and legacy deletion**
  - Files: scenario harness/tests, browser/E2E fixtures, final schemas/API types, `learn.py`, `learn_runtime.py`, `backend/app/models/learn.py`, `backend/scripts/backfill_learn_runtime_v2.py`, `backend/migrations/versions/0009_drop_learn_step_index.py`, `Notes.tsx`, and visual renderers.
  - Changes: full traces, gold providers, runtime-v2 data convergence, removal of all Section 11 paths including the cursor-reading adapter branch, drop `step_index`; `objective_index` remains derived-only.
  - Tests: `backend/venv/bin/pytest backend/tests/test_learn_scene.py -q`; `backend/venv/bin/pytest backend/tests/learn_agent_scenarios -q`; `backend/venv/bin/pytest backend/tests -q`; `backend/venv/bin/python -m compileall -q backend/app backend/tests`; frontend tests/build; FastAPI startup; migration smoke; `git diff --check`; static `rg` deletion assertions.
  - Browser proof: every Section 12 scenario at desktop/narrow width, including provider fallback and refresh/resume.
  - Deletion unlocked: none; this is the final deletion gate. Commit only when every Section 13 condition is true. Do not push.
