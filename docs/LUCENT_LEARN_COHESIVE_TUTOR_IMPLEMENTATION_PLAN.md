# Lucent Learn: Cohesive Autonomous Tutor Implementation Plan

Status: implementation handoff plan  
Prepared from repository state: 2026-09-05  
Branch at audit: `feature/public-auth-flow`  
Last committed revision at audit: `65bfa0b fix: stabilize autonomous tutor replanning`

## Purpose

This plan completes the transition from Lucent's current adaptive sequence of individual `LearnStep` records to a cohesive, immersive tutor experience organized around bounded `LearningScene` tutor turns.

The implementation must preserve the existing security, persistence, evidence, provenance, interaction, visual, and provider infrastructure. It must not introduce a second Learn runtime or pre-generate a whole lesson. The model is the bounded pedagogical planner; the backend remains the validator, authorizer, state owner, and tool executor.

## Non-goals for this pass

- Do not build embedding/vector RAG. Keep `retrieve_note_context()` as the grounded retrieval path.
- Do not redesign Notes, Flashcards, Quiz, authentication, ingestion, or SectionNote generation.
- Do not replace working interaction renderers or visual renderers when they can be extracted and reused.
- Do not persist hidden chain-of-thought. Store only structured observations, decisions, tool outcomes, and concise rationale summaries.
- Do not add arbitrary model-generated React, HTML, CSS, SVG coordinates, JavaScript, Python, SQL, or URLs.

## 1. Audit of the current repository

### Working tree

The repository was clean at commit `65bfa0b` before the current Learning Scene work began. The audit found these uncommitted changes:

- Modified: `backend/app/routers/learn.py`
- Modified: `backend/app/schemas/learn.py`
- Modified: `backend/app/services/learn_engine.py`
- New: `backend/app/services/learn_scene.py`

These changes are an incomplete start, not a finished implementation. Preserve them while correcting the issues listed below. Do not reset or discard them.

### Persisted backend model

`backend/app/models/learn.py` currently provides:

- `LearnSession`: owner, material, goal, familiarity, JSON `plan`, JSON `state`, objective/step cursors, status, report, timestamps.
- `LearnAttempt`: stable objective/step identity, submitted response, result, hints, structured evaluation.
- `LearnTutorEvent`: bounded telemetry for tutor decisions, Ask Lucent, rate limits, validation, and fallbacks.

Migrations already exist in:

- `backend/migrations/versions/0006_learn_sessions.py`
- `backend/migrations/versions/0007_adaptive_learn_evidence.py`
- `backend/migrations/versions/0008_learn_tutor_events.py`

The current JSON session state already persists concept evidence, misconceptions, strategy/modality outcomes, scaffolding, revisit state, branch state, recent attempts, and the most recent tutor decision. This is sufficient to persist the active Learning Scene without an immediate database migration.

### Current Learn contracts

`backend/app/schemas/learn.py` already defines:

- all major interaction step types;
- `LearningObjective` and `LearnPlan`;
- `ConceptEvidence` and rich evaluation results;
- `TutorObservation`, `TutorDecision`, `TutorAction`, and bounded tool names;
- visual specifications and source provenance;
- reports and Ask Lucent contracts.

The uncommitted work adds `LearningSceneBlock`, `LearningScene`, `LearnSessionResponse.scene`, and `AskLucentResponse.scenePatch`. These additions are directionally correct but are not yet the authoritative runtime contract.

### Current generation and runtime flow

`backend/app/services/learn_engine.py` currently:

1. converts SectionNotes into a bounded `LearnPlan`;
2. creates a predetermined list of teaching and interaction steps per objective;
3. creates deterministic visual specs from Note components;
4. exposes answer-safe `LearnStepView` records;
5. grades deterministic interaction types;
6. contains the initial learner-facing content quality checks.

`backend/app/routers/learn.py` currently:

1. creates/resumes a `LearnSession`;
2. selects a current step by `objective_index` + `step_index`;
3. grades a response and updates concept evidence;
4. selects or appends another step;
5. invokes `choose_tutor_decision()` after the deterministic selection;
6. stores the decision and may change the selected candidate;
7. returns a single `step` plus action/feedback.

The model therefore influences candidate selection, but the product unit is still one step. Many tutor tools are accepted without producing visible teaching content. Remediation and prerequisite branches still append synthetic steps into the plan.

### Current tutor provider boundary

`backend/app/services/learn_tutor.py` provides one injectable structured provider boundary used by:

- semantic free-response diagnosis;
- Ask Lucent;
- next tutor decision selection.

It already has bounded context, time/token limits, schema validation, fake-provider support, safe fallback behavior, concept/step authorization, and tool-argument checks. Preserve this boundary. Extend its schema and prompts rather than adding another provider abstraction.

### Current deterministic policy and evidence

`backend/app/services/adaptive_policy.py` supplies content-type policies, scaffold progression, review scheduling, prerequisite IDs, and fallback diagnosis. `backend/app/routers/learn.py` owns the actual evidence mutation and completion/report logic. Preserve that separation: model decisions propose; deterministic runtime validates and commits.

### Current retrieval

`backend/app/services/retrieval.py` performs bounded lexical retrieval over SectionNotes and returns section/block provenance. It is sufficient for this pass and remains the fallback even after a future semantic retriever is introduced.

### Current Notes and visual systems

Notes are generated as typed SectionNote components in `backend/app/semantic/section_notes.py`. The frontend renders these in the local `ComponentView` function inside `web/src/pages/Notes.tsx`:

- explanation and definition;
- flow and relationship map;
- structure/hierarchy;
- comparison;
- equation and worked example;
- walkthrough/StepThrough mechanism.

Learn also uses:

- `web/src/learning/visuals/StructuredVisual.tsx` for validated graph-like visual specs;
- `web/src/learning/experiences/StepThroughMechanism.tsx` for staged vector, sequence, ordered-items, and semantic mechanism scenes.

The current Learn path sometimes converts richer Note components into a less expressive `VisualSpec`. The finished scene renderer must be able to reference and render the original Note component when it is the stronger representation.

### Current frontend Learn experience

`LearnView` in `web/src/pages/Notes.tsx` currently owns all of the following in one component:

- onboarding;
- active-session loading and resume;
- focus mode;
- response state for every interaction type;
- hints;
- stop/report state;
- Ask Lucent;
- rendering the current single `LearnStepView`.

Focus mode is a fixed overlay around the same single card. It does not automatically become the primary active-session experience. Visuals, practice, feedback, and Ask Lucent are separate vertical regions. Ask Lucent visual changes use a global browser event and are not consistently persisted in backend scene state.

### Current automated coverage

The backend already has substantial unit/API coverage in:

- `backend/tests/test_learn_engine.py`
- `backend/tests/test_learn_api.py`
- `backend/tests/learn_agent_scenarios/harness.py`
- `backend/tests/learn_agent_scenarios/test_scripted_learners.py`
- `backend/tests/learn_agent_scenarios/test_e2e_smoke.py`

The scenario harness records observations, decisions, tools, selected steps/actions, learner responses, evidence, and session state. It includes a 50-cycle stress scenario and key safety invariants.

Frontend Learn coverage is currently shallow. `web/src/pages/LearnTutorSmoke.test.tsx` server-renders onboarding only. It does not exercise an active session, scene composition, interactions, Ask Lucent, or focus behavior.

### Browser findings from the current run

The real authenticated application was inspected on Genetics and Pendulum materials.

- Genetics resumed into an isolated repair question with generic wording rather than a coherent comparison lesson.
- Pendulum started with `WATCH`, `Build the mental model`, a paragraph, a detached visual, and a generic stage narration.
- Focus mode showed one centered interaction card followed by Ask Lucent, not one teaching workspace.
- The current experience visibly remains `one step -> submit -> another step`.
- Some old active-session content can still contain generic remediation language.

## 2. Architecture to preserve

The following are established foundations and should remain authoritative:

1. `LearnSession` is the account-owned persisted session.
2. `LearnAttempt` is the source of truth for submitted learner evidence.
3. `LearnTutorEvent` stores bounded operational telemetry, not raw chain-of-thought.
4. SectionNotes and their source block IDs remain the grounding substrate.
5. `TutorObservation` is the bounded input to model reasoning.
6. `TutorDecision` is the bounded output from model reasoning.
7. The provider injection in `learn_tutor.py` supports production and deterministic fakes.
8. The backend owns grading, evidence mutation, review scheduling, completion, authorization, tool execution, and persistence.
9. Existing interaction schemas/renderers remain reusable response primitives.
10. Existing Notes, StructuredVisual, and StepThrough renderers remain reusable visual assets.
11. Existing stable-ID, remediation-bound, transaction-safety, relevance, rate-limit, provenance, and prompt-injection protections must not regress.

## 3. Target architecture

### 3.1 Immutable source/objective library versus adaptive runtime

Treat the persisted `LearnPlan` as a bounded objective and teaching-asset library, not a script.

- Objectives, source scope, prerequisites, source-backed explanations, Note visual references, and candidate interaction material remain stable.
- The immediate scene, block ordering, teaching strategy, selected practice, scaffold, feedback, and visual state are adaptive.
- Do not create 20 future scenes. Compose one scene after each meaningful event.

For backward compatibility, `LearningObjective.steps` can remain during this implementation as the candidate asset pool. Rename it only in a future migration. The runtime must stop assuming that list order is the learner-facing order.

### 3.2 The authoritative runtime unit

The active runtime unit becomes a versioned `LearningScene` stored under `LearnSession.state.currentScene` and returned as `LearnSessionResponse.scene`.

Recommended persisted state keys:

```text
stateSchemaVersion: 2
currentScene: LearningScene
sceneRevision: integer
sceneHistory: bounded summaries of the last 8 scenes
currentVisualState: { visualKey, stage, highlightedElementIds, expanded? }
currentResponseStepId: stable step/interaction ID or null
lastFeedback: concise learner-facing feedback
lastFeedbackKind: correct | incorrect | info
lastTutorDecision: validated TutorDecision
lastTutorToolResults: bounded structured results
sceneInterruption: bounded Ask Lucent contribution or null
```

The scene itself contains at most six coordinated blocks and at most one response-bearing practice block in V1. This keeps submission unambiguous while allowing explanation + visual + example + practice + feedback to coexist.

### 3.3 Final LearningScene contract

Evolve the current uncommitted schema to the following responsibilities:

```text
LearningScene
  id                         stable bounded hash, not derived from growing text
  revision                   monotonic within session
  objectiveId
  objective                  learner-facing outcome
  targetConcepts
  pedagogicalGoal
  tutorHypothesis            concise validated summary; not chain-of-thought
  strategy
  scaffoldLevel
  blocks[]                   1..6
  evidenceTargets[]
  sourceSectionIds[]
  sourceBlockIds[]
  visualState
  completionCondition
  responseStepId             nullable; identifies the only graded block
```

```text
LearningSceneBlock
  id                         stable bounded hash
  kind                       explanation, visual, animation, example,
                             counterexample, analogy, comparison,
                             worked_example, guided_step, practice,
                             feedback, reflection, tutor_message
  label                      Watch, Predict, Compare, Solve, Explain, etc.
  title/content              learner-facing and linted
  step                       existing LearnStepView for practice
  visualSpec                 existing structured visual contract
  visualRef                  SectionNote component reference
  sourceSectionIds[]
  sourceBlockIds[]
```

Add `revision` to prevent stale frontend writes and to make Ask Lucent scene patches explicit. Keep `step` and `action` on `LearnSessionResponse` temporarily as deprecated compatibility fields until all active-session consumers and tests use `scene`.

### 3.4 Tutor scene directive

The model must compose the immediate teaching experience rather than merely select a step. Extend `TutorDecision` with a validated `scenePlan` made of bounded directives.

```text
TutorScenePlan
  objective
  transitionMessage
  blocks[]                   maximum 5 planned blocks
  responseCandidateId       optional existing candidate step ID
  expectedEvidence[]
  completionCondition
```

Each planned block is either:

- a reference to an existing grounded asset (`stepId`, `visualRef`, or component reference); or
- a content-bearing allowlisted tutor tool request whose text/interaction is schema-validated and provenance-validated.

Do not give the model raw layout control. The model chooses semantic block kinds and order; the frontend owns presentation.

### 3.5 Typed tool calls

Replace the current untyped `TutorToolCall.arguments: dict` validation with a discriminated union of allowlisted calls. Examples:

- `ExplainConceptCall`: concept ID, concise content, source references.
- `GiveExampleCall` / `GiveCounterexampleCall` / `GiveAnalogyCall`: content and source references.
- `ShowVisualCall`: authorized candidate visual key/reference and initial stage.
- `SetVisualStageCall`: authorized visual key and bounded stage.
- `AskQuestionCall`: authorized existing candidate ID or a fully validated `LearnStep` draft with provenance.
- `GuideProblemStepCall`: a validated worked-step interaction and scaffold level.
- `ScheduleRevisitCall`: current authorized concept and supported due category.
- `BranchToPrerequisiteCall`: concept from the authorized objective set and bounded return target.

The model can request these tools. `learn.py` validates every ID and source reference against the owned session/document before execution. Tool execution returns renderable block data or a rejection; it never directly mutates evidence.

### 3.6 Scene composition flow

The immediate runtime flow should be:

```text
meaningful event
  -> load owned session and current objective/concept evidence
  -> retrieve bounded source context
  -> build TutorObservation
  -> construct deterministic safe fallback decision
  -> ask provider for TutorDecision + TutorScenePlan
  -> validate decision, tools, IDs, provenance, and learner-facing content
  -> execute allowlisted tools
  -> compile successful tool results into one LearningScene
  -> persist currentScene and a bounded history summary
  -> return the scene
```

Meaningful events include session start, continue after a teaching-only scene, answer submission, hint use, Ask Lucent, visual request, and completion/return from a prerequisite branch.

The agent may request a short intervention such as explanation -> visual -> prediction, but no more than four tool calls and six final blocks. It replans after the learner response rather than reserving later steps.

## 4. Backend changes

### 4.1 `backend/app/schemas/learn.py`

Complete and tighten the uncommitted scene types:

- add `revision` and optional `visualKey` to `LearningScene`/blocks;
- add `TutorScenePlan` and typed block directives;
- replace free-form tutor tool argument dictionaries with strict typed tool-call unions;
- preserve the existing `LearnStep` interaction union inside practice blocks;
- extend Ask Lucent response with the authoritative updated scene (preferred) or a revisioned scene patch;
- cap all text, arrays, actions, blocks, IDs, and source references;
- require source provenance for source-dependent generated blocks;
- prohibit more than one response-bearing practice block in a scene validator.

Completion criteria:

- malformed/multi-response scenes fail validation;
- every source-dependent block carries valid provenance;
- IDs remain <= 60 characters;
- model output cannot express arbitrary state mutation or UI commands.

### 4.2 `backend/app/services/learner_content.py` (new)

Move the partially added content checks out of `learn_engine.py` into a shared learner-facing validator used by plans, scenes, remediation, Ask Lucent, and provider output.

It should return structured issue codes for:

- banned meta phrases;
- schema names/internal enum labels;
- raw ID patterns;
- accidental snake_case leakage;
- generic placeholder prompts/distractors;
- identical or implausible multiple-choice distractors;
- missing subject-specific tokens;
- missing/invalid source references.

The snake_case rule must be source-aware so legitimate code identifiers present in technical source material are allowed. Do not whitelist an identifier merely because it appears in a generated prompt; compare against retrieved/SectionNote source text.

On invalid model output:

1. retry once with validation errors;
2. if still invalid/unavailable, compile a source-specific deterministic fallback;
3. if no valid practice can be constructed, return a grounded teaching-only scene rather than a fabricated question.

Completion criteria:

- all listed internal terms are rejected unless genuinely present as source subject matter;
- bad distractors and meta prompts never reach `public_step()` or a scene response;
- technical source identifiers remain usable when explicitly source-supported.

### 4.3 `backend/app/services/learn_engine.py`

Preserve deterministic grading and existing interaction types. Narrow this module to:

- build objectives and grounded candidate assets from SectionNotes;
- expose answer-safe interaction views;
- perform deterministic grading;
- produce source-specific fallback assets.

Replace template fallbacks such as “What outcome should occur when … is applied here?” with proposition-aware builders:

- definition -> definition/example/non-example or free recall;
- comparison -> actual paired dimensions/effects and plausible swapped/nearby distractors;
- process -> actual next transition or ordering;
- structure -> actual labels/relationships;
- worked example/equation -> actual next step/result;
- takeaway -> direct explanation or subject-specific short answer.

Never raise a learner-visible 500 merely because a fallback cannot be generated. Return no practice candidate and let the scene compiler provide grounded teaching.

Change the plan fingerprint to a versioned value such as `learn-v2-scene` for newly created sessions while keeping active legacy sessions resumable.

Completion criteria:

- the plan is a candidate library, not the execution schedule;
- generated fallback content names actual source concepts/propositions;
- Genetics comparison fallback and Pendulum process fallback are coherent without topic-specific code.

### 4.4 `backend/app/services/learn_tutor.py`

Extend the existing provider schema and prompt rather than adding a new client.

The tutor prompt must explicitly:

- choose a pedagogical goal before modality;
- decide whether to teach or check;
- compose a short coherent scene;
- use multiple coordinated blocks when useful;
- use prior failed strategies/modalities;
- treat uncertainty, “I don't know,” partial understanding, and misconception differently;
- reuse the current visual when appropriate;
- keep all claims grounded in supplied source context;
- avoid generic/meta/schema wording;
- emit no more than four actions and one graded practice;
- output concise learner-facing transition/feedback text.

Validation must check allowed concepts, candidate IDs, source IDs, visual IDs/stages, and content quality. One bounded retry may include validation issue codes. After that, return the deterministic fallback.

Completion criteria:

- fake-provider tests prove explanation + visual + practice composition;
- an “I don't know” observation can yield a teaching-only or teach-then-check scene;
- a misconception can yield contrast/visual + a different check;
- invalid actions fall back without changing evidence or returning 500.

### 4.5 `backend/app/services/learn_scene.py`

Keep this new module as the sole scene compiler, but refine it before integration.

Required corrections to the current draft:

- do not treat generated prompts as trusted source text when applying the linter;
- compile actual tool results, not just generic text inferred from the current step;
- preserve a useful prior visual across adjacent scenes using `visualKey` and `currentVisualState`;
- allow teaching-only scenes and teaching + visual + practice scenes;
- guarantee only one response-bearing practice;
- persist stable bounded IDs based on session/objective/revision/block role;
- ensure feedback is specific and appears before the next intervention;
- include Ask Lucent tutor messages without duplicating or displacing current practice;
- select the original SectionNote visual via `visualRef` when it is richer than a synthesized `VisualSpec`;
- use source-specific deterministic fallbacks only.

Completion criteria:

- one scene can contain feedback + explanation + visual + practice;
- visual state survives scene recomposition;
- all blocks pass provenance/content validation;
- scene size remains bounded during the 50-cycle stress test.

### 4.6 `backend/app/routers/learn.py`

Keep the current endpoints, authorization, rate limits, telemetry isolation, and transaction protections. Refactor orchestration into small service calls instead of growing this router further.

Required route behavior:

#### Session creation/resume

- create plan/objective library and initial evidence;
- compose and persist an initial scene immediately;
- when resuming a legacy active session without `currentScene`, upgrade its state and compose one safely;
- return `scene` as the primary active-session payload.

#### Response submission

- identify the response target from `currentScene.responseStepId`, not blindly from `step_index`;
- authorize and parse that exact existing or generated interaction;
- grade and persist `LearnAttempt`;
- update evidence deterministically;
- create the next observation and replan;
- persist/return the replacement scene;
- reject stale scene revisions with a recoverable 409 and current session payload.

#### Teaching-only continuation

- accept an empty/continue event only when the current scene has no response target;
- record scene acknowledgement, not a graded attempt;
- replan immediately.

#### Hints

- operate on the current scene response block;
- persist hint dependence;
- recompose only the affected practice/feedback region or return the updated full scene.

#### Ask Lucent

- keep the relevance gate before any model call;
- use the same current observation, source context, learner state, and tutor provider;
- validate tool calls against the current owned scene/document/concept;
- apply allowed visual changes to persisted `currentVisualState`;
- add a bounded tutor-message block and, when appropriate, recompose teaching blocks while preserving the active practice;
- return the updated scene/revision;
- never grade or mutate evidence directly from chat.

#### Stop/completion

- persist the current scene summary, evidence, unresolved review needs, and report;
- preserve existing honest report behavior.

Also fix issues present in the draft before merging:

- remove the duplicated `TutorAction(...)` assignment in `_session_payload()`;
- make `_safe_step()` use trusted source context for content validation;
- replace the generic `_append_remediation()` fallback instead of raising from normal request flow;
- stop appending adaptive teaching content indefinitely to `plan.steps` once scene generation is authoritative.

Completion criteria:

- every meaningful event produces at most one bounded replan;
- active responses cannot target a stale/hidden step;
- Ask Lucent safely changes scene/visual state and refresh survives;
- no valid learner sequence returns 500.

### 4.7 `backend/app/services/adaptive_policy.py`

Keep this as deterministic fallback and guardrail policy, not the primary teacher.

- expose safe fallback scene recipes by content type;
- enforce scaffold/review/completion constraints;
- ensure heavy assistance cannot become demonstrated evidence;
- give the provider policy metadata, but do not hard-code the primary scene order;
- retain bounded prerequisite depth and review behavior.

Completion criteria:

- provider-off operation remains coherent and source-specific;
- deterministic rules never override a valid safe model decision merely to rotate interaction formats.

### 4.8 Persistence and migration decision

No new SQL table is required for the first cohesive-scene implementation. Persist `currentScene`, scene revision, visual state, and bounded summaries in the existing JSON `LearnSession.state`. This avoids a destructive migration and keeps existing sessions compatible.

Implement a pure `_upgrade_session_state()`/`upgrade_session_state()` function that:

- defaults `stateSchemaVersion`;
- normalizes review enums;
- removes invalid legacy `sceneInterruption` payloads;
- validates or discards an invalid saved scene;
- never discards concept evidence, attempts, misconceptions, revisit queue, or branch stack.

A future normalized scene-event table is optional and should only be added if product analytics or multi-device concurrent scene editing requires it.

## 5. Frontend changes

### 5.1 `web/src/api/client.ts`

Add exact TypeScript mirrors for:

- `LearningSceneBlock`;
- `LearningScene`;
- scene revision/current visual state;
- updated Ask Lucent scene response.

Keep `LearnSession.step` temporarily optional for compatibility. New rendering must prefer `session.scene`.

### 5.2 Split `LearnView` without changing routes

Keep `LearnView` exported from `web/src/pages/Notes.tsx` so the existing material route and mode tabs do not change. Move active Learn behavior into focused components:

- `web/src/learn/LearnWorkspace.tsx`
  - onboarding, active/finished state switch, focus lifecycle, session orchestration.
- `web/src/learn/useLearnSession.ts`
  - API calls, response state reset, stale revision handling, resume, hints, Ask Lucent.
- `web/src/learn/LearningSceneView.tsx`
  - scene-level header, objective/progress, block layout, integrated feedback and controls.
- `web/src/learn/SceneBlockRenderer.tsx`
  - explanation/example/comparison/visual/practice/feedback/tutor-message blocks.
- `web/src/learn/InteractionRenderer.tsx`
  - extract and reuse all current multiple-choice, free/numeric, prediction, ordering, matching, labeling, fill-blank, worked-step, and teach-back controls.
- `web/src/learn/AskLucentPanel.tsx`
  - contextual interruption, rate-limit state, scene updates, concise answer history.
- `web/src/learn/LearningVisual.tsx`
  - controlled visual stage/highlight and shared Note/StructuredVisual/StepThrough resolution.

`Notes.tsx` should retain only a thin `LearnView` wrapper passing the current SectionNote collection/material context into `LearnWorkspace`.

Completion criteria:

- no duplicated interaction implementation exists;
- existing material routes and Notes/Flashcards/Quiz behavior remain unchanged;
- active Learn renders from `session.scene`.

### 5.3 Share Notes visual rendering

Extract the existing local `ComponentView` into:

- `web/src/learning/components/SectionComponentRenderer.tsx`

Both Notes and Learn use it. `LearningVisual` chooses:

1. original SectionNote component via authorized `visualRef` when available;
2. StepThrough mechanism when the component contains one;
3. StructuredVisual when the scene carries a validated spec;
4. no visual when none adds value.

Make `StructuredVisual` and `StepThroughMechanism` controlled-capable:

- `stage`/`initialStage`;
- `highlightedElementIds`;
- `onStageChange`;
- preserve internal state when the scene revision changes but the `visualKey` stays the same;
- respect reduced motion.

Remove reliance on the global `lucent-visual-stage` event after the controlled path is connected.

Completion criteria:

- practice can render beside/below the same active visual;
- Ask Lucent can change the active visual stage through React state derived from the server scene;
- the visual does not remount/reset between related scene revisions.

### 5.4 Fullscreen/focus behavior

An active Learn session should enter the immersive workspace by default. This is not a modal around a card.

Desktop layout:

```text
top bar: back/exit | concise objective + progress | stop

main teaching canvas
  primary teaching/visual region
  integrated explanation/practice/feedback region

contextual Ask Lucent dock/panel
```

Requirements:

- fixed full viewport with warm Lucent background;
- one cohesive scene canvas rather than separate cards for every block;
- responsive one-column layout at narrow widths;
- Ask Lucent contained within viewport, never clipped at bottom-left;
- body scroll locked only while focus is active;
- internal scene area scrolls when needed;
- Escape exits focus but does not leave the material or lose state;
- explicit re-enter focus control;
- keyboard focus moves to the scene heading after a new revision;
- feedback uses `aria-live` without stealing focus;
- visible focus styles and semantic controls;
- reduced-motion support;
- no background app controls are reachable while the focus overlay is active.

The scene layout should infer composition from block kinds:

- visual + practice: responsive two-region or stacked composition;
- explanation + visual + practice: explanation integrated above/alongside the same canvas;
- feedback: appears in context next to the affected practice;
- tutor message: appears as a concise intervention, not a chat transcript card.

Completion criteria:

- Genetics and Pendulum each read as one continuous teaching surface;
- visual/practice/feedback remain together after submission;
- Ask Lucent remains usable without covering controls;
- fullscreen works at laptop and narrow widths.

### 5.5 Styling

Move or organize Learn-specific rules from `web/src/index.css` into `web/src/learn/learn.css` if doing so does not disrupt the build. Preserve Lucent's warm cream, charcoal, botanical accent, serif headings, thin borders, and quiet editorial character.

Avoid nested cards, admin-table patterns, giant empty canvases, and chat-first presentation. The current action should be visually obvious without exposing strategy/scaffold enum names.

## 6. How existing interactions are reused

All grading schemas remain `LearnStep` variants. A scene practice block wraps the public view of one variant. The backend keeps answers private; the frontend keeps its existing interaction mechanics.

The interaction renderer must support:

- multiple choice and prediction as selectable options;
- matching and labeling as structured mappings;
- ordering with accessible move controls;
- free response, fill blank, numeric, worked-step, problem, and teach-back inputs;
- hints and submit readiness;
- response restoration when the same scene is resumed;
- source-specific feedback after evaluation.

The scene changes composition, not the evidence contract. `LearnAttempt.step_id` remains the stable ID of the response-bearing interaction, separate from scene ID, block ID, and tutor action ID.

## 7. How hard-coded teaching is replaced safely

The current hard-coded `build_learn_plan()` interactions become grounded candidate assets and deterministic fallback material. They are no longer the primary sequence.

The model composes one immediate scene using:

- retrieved source blocks;
- objective metadata;
- available Note components/visual assets;
- concept evidence and misconception history;
- failed/successful strategies/modalities;
- scaffolding and review state;
- the current scene/visual state;
- a bounded candidate asset catalog.

For generated practice, the model must return a complete typed `LearnStep` draft with actual subject content, answer/evaluation data, and source references. It may not return an interaction type alone. The backend validates, lints, authorizes, and only then adds it to the current scene. It need not append ephemeral scene practice to the immutable plan; persist the validated private interaction under `state.currentScenePrivate` or an equivalent bounded private scene payload so it can be graded/resumed.

Deterministic fallback generation uses SectionNote propositions/entities, never schema-derived wording. If no safe question exists, teach and invite continuation; do not create a meta-question.

## 8. Ask Lucent integration

Ask Lucent remains the same tutor and the same session, not a parallel chatbot.

Flow:

```text
question
  -> existing durable rate limit
  -> existing relevance gate
  -> retrieve current source context
  -> build current TutorObservation plus learner question event
  -> Ask Lucent model response + bounded tool calls
  -> server validates tool IDs/arguments against current scene
  -> execute presentation-only tools
  -> persist visual state and scene interruption
  -> recompose only the necessary scene blocks
  -> return updated scene revision
```

Allowed effects:

- add a concise grounded tutor-message/explanation/example block;
- reveal/highlight/change the current authorized visual;
- suggest a prerequisite branch for the normal tutor runtime;
- mark uncertainty in bounded context for the next replan.

Disallowed effects:

- direct concept-evidence mutation;
- direct mastery/state changes;
- arbitrary frontend commands;
- unowned document/concept/visual references;
- replacing the active practice with an unrelated question.

The frontend merges nothing optimistically except loading state. It renders the updated authoritative scene from the server, preserving the active response control and visual key.

## 9. Agent and tool boundaries

### Model authority

- pedagogical goal and strategy;
- teach versus check;
- depth and scaffolding proposal;
- scene block selection/order;
- grounded explanation/example/analogy content;
- appropriate existing visual and stage;
- practice content and evidence target;
- prerequisite/revisit proposal;
- concise transition and feedback interpretation.

### Backend authority

- authentication and ownership;
- source/ID/provenance authorization;
- schema and content validation;
- provider retry/timeout/action limits;
- tool execution;
- grading and evidence mutation;
- scaffold/review/completion invariants;
- prerequisite branch stack;
- stable IDs and revisions;
- persistence and transactions;
- telemetry and rate limits;
- deterministic fallback.

### Frontend authority

- semantic layout of block kinds;
- interaction state before submission;
- visual animation/rendering;
- focus management and accessibility;
- responsive composition.

## 10. Test plan

### 10.1 Backend unit tests

Add `backend/tests/test_learn_scene.py` covering:

- scene schema bounds and exactly one response target;
- explanation + visual + practice composition;
- feedback + changed strategy + new practice composition;
- teaching-only scenes;
- preservation of visual key/stage across revisions;
- stable bounded scene/block/action/step IDs;
- provenance subset validation;
- source-specific fallback construction;
- rejection of internal/meta/template language;
- source-aware allowance for legitimate technical identifiers;
- malformed provider scene plans falling back safely.

Extend `backend/tests/test_learn_engine.py` for content-linter and proposition fallback cases.

Extend `backend/tests/test_learn_api.py` for:

- create returns an initial scene;
- teaching-only continue replans;
- response targets the scene interaction;
- stale revision behavior;
- scene resume after refresh;
- Ask Lucent returns an updated revision and persists visual stage;
- old sessions without a scene upgrade safely.

### 10.2 Scenario harness

Extend `backend/tests/learn_agent_scenarios/harness.py` so every turn records:

- `TutorObservation`;
- `TutorDecision` and `scenePlan`;
- tool calls/results;
- `LearningScene` before and after;
- scene block kinds and learner-facing text;
- visual key/stage;
- response-bearing step;
- evaluation/evidence delta;
- session state and HTTP status.

Add invariants:

- 1..6 scene blocks;
- at most one response target;
- no learner-facing content issues;
- all source-dependent blocks grounded;
- no repeated identical scene/question after failed strategy;
- visual key stable when reused;
- model cannot directly alter evidence;
- bounded scene history/state size;
- every tool result is applied or explicitly rejected;
- no unauthorized tools/IDs;
- no valid sequence returns 500.

Keep the existing 50-cycle stress case and add assertions that scene count/history and private scene interaction storage remain bounded.

### 10.3 Gold fake-provider scenarios

Add deterministic providers that emit complete scene directives for:

#### Genetics

1. concise side-by-side comparison explanation/visual;
2. integrated classification/matching check;
3. incorrect classification diagnosed as gain-of-function versus loss-of-function confusion;
4. changed contrast/example intervention;
5. teach-back with reduced scaffold;
6. later independent transfer case.

#### Pendulum

1. objective + persistent pendulum visual + prediction;
2. wrong turning-point prediction;
3. feedback naming velocity versus total-energy misconception;
4. same visual advanced/highlighted with PE/KE explanation;
5. learner explanation;
6. amplitude-change transfer prediction.

#### Procedural/math

1. worked example + guided step in one scene;
2. procedural/substitution error diagnosis;
3. targeted guidance only;
4. partial scaffold;
5. independent problem;
6. transfer problem.

#### Uncertainty

- “I don't know” produces teaching before another check.
- “I'm not sure” produces a minimal probe/scaffold distinct from a confident misconception.

#### Ask Lucent

- request for another explanation changes strategy while preserving practice;
- request for a visual changes persisted visual stage/highlight;
- out-of-scope, malformed tool, unauthorized ID, prompt injection, and rate-limit behavior remain safe.

### 10.4 Frontend tests

Add component tests under `web/src/learn/` for:

- multiple coordinated scene blocks render as one scene;
- visual and practice coexist;
- feedback stays in the same scene;
- each existing interaction renderer submits the correct payload;
- Ask Lucent server scene update changes visual stage without losing response input;
- focus mode Escape/exit/re-entry and body scroll lock;
- keyboard navigation/focus after scene revision;
- narrow layout and no Ask Lucent clipping;
- internal/meta text is never rendered from a rejected fixture;
- report/onboarding regressions.

Replace the current onboarding-only smoke test with an active-session fixture in addition to retaining onboarding coverage.

## 11. Browser acceptance plan

Use the real authenticated development environment. Prefer fresh sessions (`restart: true` through the normal UI/API path) so legacy state does not mask results. Capture screenshots before and after the adaptive turn.

### Genetics acceptance

- enter Learn and focus mode;
- verify objective and actual proto-oncogene/tumor-suppressor teaching before or alongside practice;
- verify comparison visual and practice share one scene;
- answer classification incorrectly;
- verify specific misconception feedback and visibly different contrast/example strategy;
- answer teach-back correctly;
- verify reduced scaffold and later transfer case;
- use Ask Lucent without leaving/replacing the scene;
- inspect all text for schema/internal leakage.

### Pendulum acceptance

- enter fresh session;
- verify persistent animated/staged visual plus prediction in one scene;
- answer “kinetic energy is highest at the turning point”;
- verify feedback identifies velocity versus total energy;
- verify the same visual changes stage/highlight and explanation appears in context;
- answer explanation;
- verify amplitude/scenario transfer while the visual remains active;
- ask for another explanation and a visual highlight;
- verify refresh/resume preserves scene and visual stage.

### Procedural/math acceptance

- verify worked example + guided step coexist;
- make a substitution/procedural error;
- verify only the failed step is scaffolded;
- proceed through partial, independent, and transfer states;
- verify visible differences in assistance.

### General browser checks

- correct, partial, incorrect, “I don't know,” and “I'm not sure”;
- hints;
- Stop for now and resume;
- completion/report;
- focus enter/exit and Escape;
- laptop and narrow viewport;
- keyboard-only path;
- Ask Lucent 429 state;
- screenshots show one learning canvas, no clipped Ask panel, no detached visual card, and no generic prompts.

For every gold session, record a short critique against objective clarity, teaching-before-testing, integration, mistake response, specificity, visual utility, scaffold adaptation, continuity, and Ask Lucent cohesion. Fix general causes, restart a fresh session, and rerun before acceptance.

## 12. Sequential implementation phases

### Phase 0: Stabilize the uncommitted scene draft

Work:

- preserve the four current uncommitted files;
- remove duplicate/unsafe draft behavior;
- add unit tests for the existing draft before broad refactoring;
- centralize the content validator.

Completion criteria:

- current backend tests pass;
- `git diff --check` passes;
- no generic remediation can raise a normal-flow 500;
- working tree contains an internally coherent scene foundation.

Dependencies: none.

### Phase 1: Finalize scene and typed tutor-tool contracts

Work:

- finalize `LearningScene`, `TutorScenePlan`, scene revisions, and typed tool unions;
- add source/provenance/content validators;
- extend provider fake/schema tests.

Completion criteria:

- strict model output can describe explanation + visual + practice;
- invalid IDs, source refs, tools, and multiple response targets are rejected;
- deterministic fallback decision remains valid.

Dependencies: Phase 0.

### Phase 2: Make scene composition authoritative

Work:

- implement the scene compiler and tool-result compilation;
- persist current scene/private answer data in session state;
- upgrade legacy session state;
- change create/resume/respond/hint to use the current scene response target;
- stop relying on sequential `step_index` for learner-facing progression.

Completion criteria:

- session creation returns a persisted initial scene;
- response triggers observe -> decide -> tools -> new scene;
- refresh returns the same scene/revision;
- teaching-only scenes continue without fake evidence;
- all API tests pass.

Dependencies: Phase 1.

### Phase 3: Integrate Ask Lucent into scene recomposition

Work:

- feed Ask Lucent the current scene observation;
- validate/apply visual tools to persisted visual state;
- recompose tutor-message/teaching blocks without losing current practice;
- return the authoritative updated scene;
- retain relevance, rate limit, telemetry, prompt-injection, and transaction safeguards.

Completion criteria:

- Ask Lucent can change a visual and explanation in the same scene;
- refresh preserves the change;
- chat cannot mutate graded evidence;
- security/transaction tests pass.

Dependencies: Phase 2.

### Phase 4: Build the frontend Learning Scene workspace

Work:

- add TS scene types;
- extract `useLearnSession`, interaction renderer, scene renderer, Ask panel, and visual wrapper;
- render `session.scene` in the existing material Learn mode;
- retain legacy step fallback only for old backend responses.

Completion criteria:

- a scene visibly combines multiple blocks;
- every current interaction remains usable;
- response/hint/Ask updates replace or recompose the scene correctly;
- frontend unit tests pass.

Dependencies: Phase 2; Phase 3 for final Ask behavior.

### Phase 5: Share visual intelligence and make visuals stateful

Work:

- extract `SectionComponentRenderer` from Notes;
- let Learn render original Note visuals by reference;
- make StructuredVisual/StepThrough controlled-capable;
- preserve a visual key/stage across related scenes;
- integrate visual + practice + feedback in one workspace.

Completion criteria:

- Pendulum reuses its visual through prediction, reveal, explanation, and transfer;
- Genetics reuses a comparison visual through classification and remediation;
- Notes rendering does not regress;
- reduced-motion/accessibility tests pass.

Dependencies: Phase 4.

### Phase 6: Fullscreen product integration and polish

Work:

- make active Learn immersive by default;
- implement cohesive desktop/narrow layouts;
- fix Ask Lucent containment;
- implement focus/scroll/keyboard behavior;
- add scene transitions/loading/error states.

Completion criteria:

- workspace is visually distinct from Notes without changing routes;
- no detached card sequence or clipped panel;
- Escape/focus/keyboard/responsive checks pass;
- screenshots meet Lucent's calm editorial standard.

Dependencies: Phases 4-5.

### Phase 7: Experience-quality and stress coverage

Work:

- extend scenario traces with scenes;
- add Genetics, Pendulum, procedural, uncertainty, and Ask Lucent gold providers;
- add content-linter and no-loop invariants;
- retain and expand the 50-cycle stress run;
- add active-session frontend smoke tests.

Completion criteria:

- tests prove experience properties, not only enum/schema changes;
- no internal/meta text, repeated identical failure loop, unbounded state growth, ungrounded block, or unauthorized tool;
- valid simulated sequences never return 500.

Dependencies: Phases 1-6; tests should be added alongside each phase and consolidated here.

### Phase 8: Browser QA, critique, and final validation

Work:

- run fresh Genetics, Pendulum, and procedural sessions end to end;
- intentionally exercise correct/partial/wrong/uncertain responses, hints, Ask Lucent, visuals, stop/resume, and completion;
- capture and inspect desktop/narrow screenshots;
- fix general causes and rerun affected sessions;
- run all automated validation.

Completion criteria:

- each gold session feels like one tutor-led lesson;
- learner mistakes visibly and specifically change the scene;
- visual, explanation, practice, and feedback remain integrated;
- Ask Lucent is recognizably the same tutor;
- all final validation commands pass.

Dependencies: all prior phases.

## 13. Validation commands

Run from the repository root unless noted:

```bash
backend/venv/bin/pytest backend/tests/test_learn_scene.py -q
backend/venv/bin/pytest backend/tests/learn_agent_scenarios -q
backend/venv/bin/pytest backend/tests -q
backend/venv/bin/python -m compileall -q backend/app backend/tests
cd web && npm test
cd web && npm run build
git diff --check
```

Also run the FastAPI import/startup smoke test used by the repository and the authenticated browser application before acceptance.

## 14. Recommended coherent commits

1. `feat: add validated tutor learning scenes`
2. `feat: orchestrate learn sessions through scenes`
3. `feat: integrate ask lucent with learning scenes`
4. `feat: render cohesive learn workspace`
5. `feat: preserve visuals across tutor turns`
6. `test: evaluate cohesive tutor experiences`
7. `fix: polish immersive learn sessions`

Run the relevant focused tests before each commit. Do not push.

## 15. Final acceptance checklist

- [ ] `LearningScene` is the authoritative active-session unit.
- [ ] One scene can combine teaching, visual, practice, and feedback.
- [ ] The model composes the immediate scene through bounded validated directives/tools.
- [ ] Backend evidence mutation remains deterministic and authorized.
- [ ] Existing interactions are reused end to end.
- [ ] Current Note/StepThrough visuals can be reused without downgrade.
- [ ] Visual state persists across tutor turns and Ask Lucent changes.
- [ ] Active Learn opens into a cohesive fullscreen workspace.
- [ ] Ask Lucent updates the same scene and never becomes a separate chatbot.
- [ ] Internal identifiers, enum names, and meta placeholders are rejected.
- [ ] Deterministic fallback teaching is source-specific.
- [ ] Legacy active sessions resume through a non-destructive state adapter.
- [ ] Genetics demonstrates comparison, misconception repair, reduced scaffold, and transfer.
- [ ] Pendulum demonstrates persistent visual, prediction, targeted remediation, and transfer.
- [ ] Procedural material demonstrates worked, guided, partial, independent, and transfer support.
- [ ] Scenario traces and the 50-cycle stress test remain bounded.
- [ ] Backend, frontend, build, compile, startup, diff, accessibility, and browser checks pass.

The implementation is complete only when the real browser experience demonstrates these behaviors. Passing schemas or unit tests alone is not sufficient.
