# Lucent landing page visual specification

## Visual system

- A restrained alpine atmosphere uses charcoal, fog, warm paper, sage, and
  forest green. Editorial serif statements carry the story; compact sans-serif
  copy and controls remain recognizably Lucent.
- The central object is a physical stack of source pages. Soft shadows, page
  edges, overlap, perspective, and foreground silhouettes establish depth
  without decorative 3D clutter.

## Continuous scroll narrative

One sticky composition spans five beats across a 600svh desktop timeline:
source material, page separation, structured understanding, the interactive
Lucent learning surface, and the closing invitation. The source sheets open
at different Z depths; the visual explanation sheet comes forward and turns
edge-on into the product surface. The product then recedes to the right,
remaining visible in the same landscape behind the closing invitation.
There is no separate full-screen CTA panel or hard environment cut.

## Motion and 3D strategy

CSS 3D transforms and Framer Motion map scroll progress to translation, Z
depth, rotation, scale, and opacity. The camera remains fixed while layered DOM
objects move through its perspective. This avoids a continuous WebGL render
loop and keeps product text crisp when the composition resolves into Lucent.
Every timeline explicitly includes progress 0 and 1. Browser inspection caught
native scroll animations interpolating back to their initial opacity when the
last authored keyframe ended early; full-range endpoints prevent ghosted copy.
The landscape and masked foreground move at different rates along a continuous
forward/right camera drift, without returning to the opening camera position.
There is no cream veil over the environment during the product interval.
Three restrained CSS fog banks drift behind, between, and in front of the
sheets; foreground fog thins during interaction. Pages separate by up to 155px
in Z and rotate independently on X/Y/Z. The demo itself approaches from negative
Z, settles into a readable flat interval, and recedes to negative Z at the end.
Inactive controls are inert, including the receded product in the final scene.

## Real product reuse

The product stage uses Lucent's actual navigation language, study-mode styling,
tutor explanation, Ask Lucent controls, and the unchanged production
`StructuredVisual` component. Its deterministic interaction demonstrates the
same explain–visualize–practice relationship as the application without
inventing a separate dashboard or unsupported capability.

The visible example concerns cellular protein quality control. The same source
idea appears on the opening document, its simplified/analogy/visual sheets, and
the interactive preview. Choosing the repair misconception changes the tutor
explanation and highlights the signal/response relationship. A correct choice
highlights the protective response. The two Ask controls provide distinct,
bounded explanations and replace the previous answer. Reset returns the example
to its initial state. The preview is labelled "Interactive example"; it does not
claim a live provider session or show invented learner metrics.

## Responsive and reduced motion

Desktop receives the full sticky 3D timeline. Viewports at or below 950px wide,
or 620px high, use a vertical reading sequence with a smaller physical paper
stack. Teaching and practice stack on tablet/phone. Phone visuals can be panned
or expanded; enlarged visual controls remain in view while panning.
`prefers-reduced-motion` presents the entire narrative in normal flow without
parallax or camera movement. Changing the preference or viewport live is supported.

The demo's expanded visual traps keyboard focus, supports Escape, and restores
focus to Expand. Source paper text fits its surface, the phone headline fits at
320px, and a short desktop viewport bounds the preview with internal scrolling.
Ask answers scroll into view within that preview without moving the page.

## Assets and dependencies

- `web/public/lucent-landscape.jpg`: generated alpine atmosphere, 1672×941,
  approximately 348 KiB. Generated with the built-in imagegen tool, then encoded
  as a JPEG for delivery. This is scenery only; all text, paper layers and UI are
  rendered by the application.
- `web/public/fonts/instrument-serif-{regular,italic}.ttf`: the existing editorial
  typeface, locally served under a landing-specific family name. Combined size
  approximately 124 KiB. License: `web/public/fonts/INSTRUMENT-SERIF-LICENSE.txt`.
- Existing Framer Motion and React are sufficient. No dependencies added.
- The demo is lazily mounted/imported near its entrance. No background video or
  continuous WebGL loop is used. The preview disables idle node pulsing.

Final image-generation prompt:

> Use case: photorealistic-natural. Asset type: wide 16:9 landscape background photograph for a restrained editorial learning website. Create a cinematic natural Alpine mountain lake at early morning, muted forest green, slate gray, warm ivory mist, faint amber sunlight from upper right. Wide composition: layered rugged mountain ridges in upper middle, distant haze receding through valley, dark conifer forest shoreline in lower half, calm lake in bottom third with low mist and fine horizontal reflections. Darker shaded left half with quiet low contrast space for ivory typography. Right half light mist and open sky to frame floating paper documents added later in HTML. A few dark out-of-focus pine boughs and rocks at very bottom corners for foreground depth but keep central scene open. Premium landscape photography, subtle natural grain, realistic rock and tree texture, soft atmospheric perspective, restrained contrast. No people, no buildings, no text, no website, no graphics, no paper, no UI, no watermark. Generate 16:9 at high resolution.

## Verification — 2026-09-08

Repeated rendered inspection used the in-app browser and installed Playwright
Chromium. The final production build was served on the existing authorized
`http://127.0.0.1:5173` origin with Vite preview. A first attempt on 4173 exposed
the existing backend origin restriction; validation moved to 5173 without
changing auth/CORS configuration.

Production browser matrix: **PASS** at 1440×900, 1280×720, 820×1180, 390×844,
320×740, and 1440×900 with reduced motion. Assertions cover:

- source text and headline containment; no horizontal page overflow;
- distinct 3D transformations; departed headings remain invisible;
- functioning preview anchor and an interactive, fully opaque product stage;
- wrong answer → specific teaching → changed semantic visual highlights;
- distinct Ask answers replacing each other, correct answer and reset;
- expanded visual keyboard containment, Escape, and focus restoration;
- coherent closing invitation; no uncaught errors or failed local resources.

An additional production smoke passed direct `/#learn-in-action` entry,
reload at that fragment, live desktop/phone resizing, live reduced-motion
changes, continuous wheel scrolling, and signup navigation. Direct entry first
failed because the lazy-mounted route did not exist during the browser's
initial fragment lookup; a mount-time fragment resolution fixes it without
altering application routing. Resource inspection confirms the landing page
does not load the unrelated Lanyard/WebGL or Mermaid application chunks.

Evidence: `.tmp/landing/final/` contains per-viewport hero, paper layers,
clarity, transition, product, remediation, expanded visual, and closing PNGs,
plus `report.json` and `smoke.json`. Inspection/acceptance scripts remain in
`.tmp/landing-*.cjs`.

Validation: `npm run typecheck` passed; `npm test` passed (18 files, 128 tests);
`npm run build` passed; `git diff --check` passed. Existing Vite plugin
deprecation warnings and large optional application-chunk warnings remain.

### Spatial-continuity refinement

Live before/after browser inspection confirmed the previous cream overlay
visually disconnected the demo from the landscape. It is now removed, with
landscape visible around a smaller paper-edged demo. A detailed 13-position
scroll inspection also caught overlapping source/demo text during a dissolve;
the handoff now occurs while both surfaces are nearly edge-on. Closing copy
waits for the receding demo to clear it. The static mobile treatment also drops
the isolated cream section backdrop. Fog and camera movement are disabled for
compact/reduced-motion layouts.

Evidence in `.tmp/landing/spatial/`: intermediate transition screenshots,
`fog-on.png` / `fog-off.png` rendered comparison, and `state.json` recording
independent page, fog, product, and landscape transforms. The six-layout
interaction suite also checks that the product persists visually at the end
but remains inert, and that no full-screen backdrop veil returns.

Presentation limits: this is a CSS/DOM spatial composition, not an orbitable 3D
scene. The public interaction is a deterministic demonstration using the real
visual renderer; a signed-in Learn session remains the full adaptive experience.
Phone diagrams favor readable horizontal panning over shrinking every node.

## Changed files and preservation

`LandingPage.tsx`, `MarketingNav.tsx`, and the marketing CSS now compose the
new narrative. `SpatialStory.tsx` owns the scroll presentation and
`LucentProductDemo.tsx` isolates the public interaction. The landscape, local
font files/license, and this specification are the only added assets/docs.
No dependency, backend, auth, RAG, Learn runtime, or shared visual-renderer code
changed. Existing unrelated worktree changes remain untouched. Local frontend
development and backend services are left running for review.
