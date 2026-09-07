# Lucent Learn Golden Experience

## Purpose

This is the browser acceptance journey for the authoritative Learn runtime. It is intentionally a learner journey, not a schema or API checklist. A checkpoint passes only when the learner can see the change in the active LearningScene and continue naturally.

## Sources

Run the journey twice from completely fresh sessions using substantive saved notes:

1. **Humn5 Essay (1).pdf** — the Enlightenment satire sections are the primary journey. The lesson must teach the distinction between direct argument, pure comedy, and satirical exaggeration, including how irony exposes social critique.
2. **final_holdout_pendulum.pdf** — repeat the meaningful subset with pendulum energy conservation, using the same visual across prediction, explanation, reveal, and transfer.

The source boundary is part of the test: metadata, extraction diagnostics, empty sections, and placeholder/error text must never become objectives, explanations, questions, distractors, or visuals. If a source is not substantive, Learn must show a clear source error before tutoring begins.

## Golden journey

Start a fresh Learn session from the real document UI. Enter Focus Mode and capture `01-initial-teaching.png`. The viewport must be an immersive learning workspace with objective/progress, Ask Lucent, and one cohesive scene. The initial scene must contain a concise subject-specific explanation plus a meaningful visual/comparison or example and an active prediction/practice block where appropriate.

Submit a plausible misconception (for satire: classify pure comedy as the mechanism that exposes hypocrisy). Capture `02-wrong-answer.png`. The response must be persisted against the active interaction and must not reappear as the same unanswered interaction.

Before another ordinary assessment, the scene must visibly add targeted teaching that explains why the answer is wrong. It must preserve useful context and, when the mechanism is visualizable, autonomously reuse or change the visual (stage/highlight/reveal/replay) so the explanation points to what changed. Capture `03-targeted-remediation.png` and `04-visual-adaptation.png`.

The follow-up practice must directly test the taught distinction, not merely swap formats. Capture `05-guided-practice.png`. If the learner says `I don't know`, the scene must teach/build the idea (explanation, example, contrast, visual, or worked reasoning) and increase support before asking an ordinary check. Capture that teaching state. `I'm not sure` must produce uncertainty-aware support rather than confident-misconception language.

After a guided success, the next scene must visibly reduce assistance: fewer hints, a less scaffolded prompt, or an independent response mode. Capture `06-reduced-scaffold.png`. A supported success must remain distinct from independent evidence. Capture `07-independent-application.png` when the learner solves a changed but same-concept application task.

Trigger a genuine prerequisite weakness using a controlled scenario fixture if the source journey does not naturally expose one. The active scene must branch to an authorized prerequisite, teach and practice it, retain a bounded return context, then return to the original concept without losing its evidence. Capture `08-prerequisite-branch.png` and `09-prerequisite-return.png`.

Schedule the weak/assisted concept for within-session review. Teach another concept, then bring the original concept back with a different representation and stronger evidence demand (for example recognition to explanation or guided calculation to independent application). Capture `10-delayed-review.png`.

Continue to a changed-context transfer task, not a near-duplicate question. Capture `11-transfer.png`. Completion or objective transition must be justified by evidence, never by exhausting an authored array.

During the same session use Ask Lucent as an interruption to the same tutor:

- “Explain this another way” must change the main explanation/representation when useful.
- “Why was I wrong?” must refer to the learner’s actual response and current concept.
- “Give me an example” must add a grounded example to the active scene.
- “Show me visually” must add or mutate a valid visual in the main workspace.
- “Ask me another question” may intentionally replace practice with a new grounded interaction.

Capture the resulting main-scene mutation as `12-ask-lucent.png`; a sidebar-only answer is a failure. Ask responses may be conversational only when no scene change is pedagogically useful, but they must still use the same TutorObservation → TutorDecision → scene executor runtime.

Refresh after an Ask/visual mutation. The exact currentScene revision, active interaction, visual state, objective, evidence, and answered-interaction history must resume; no stale interaction may resurrect. Capture a resume screenshot if useful.

## Evidence required at each checkpoint

For every screenshot, record the browser action, visible scene blocks, active interaction ID/revision, and the corresponding runtime trace: observation summary, decision goal/strategy, scene operations, persisted revision, and response payload. Internal diagnosis, strategy, confidence, tool arguments, provider/fallback metadata, and grading rationale must not be rendered to the learner.

## Pass/fail rules

The journey passes only if the learner can observe:

- teaching before retest after wrong/uncertain responses;
- a specific intervention that addresses the actual misconception;
- visual explanation and practice coexisting in one evolving scene;
- visibly increased then decreased support;
- prerequisite branch → repair → return;
- delayed review in a different representation;
- independent application and transfer;
- Ask Lucent changing the same main scene;
- refresh/resume preserving the authoritative scene.

Any `question → answer → another question` with no substantive teaching, any repeated interaction without a deliberate new ID/context, generic/template wording, orphan text, duplicate headings, empty visuals, or source diagnostics in learner content is a failed checkpoint.

## Screenshot location

Save browser screenshots under `.tmp/learn-golden/` with the names above. The directory is disposable local evidence and must not become application state.
