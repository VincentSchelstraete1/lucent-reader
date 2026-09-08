# Scene 1 — photographic alpine opening

2026-09-08. This is a Scene 1 review checkpoint only. Do not proceed to redesign Scenes 2–5 without the user's review.

## Result and scope

Replaced the opening's visible procedural terrain/repeated trees with a new photographic alpine landscape: snow-veined mountains, naturally irregular forested shores, a calm lake with detailed reflections, warm sunrise, layered haze, and soft foreground pine/rock framing. Only a small centered document emblem/“Lucent”, the existing navigation, and the scroll cue appear initially. The large heading and pages remain in the subsequent introduction.

The photograph is projected onto a smooth bounded depth surface. The camera translates forward and laterally, rather than scaling a flat CSS background or changing field of view. Near foreground changes perspective more than the distant ridges. Idle drift is small; three animated fog scales and restrained lake-ripple displacement keep the shot alive. Fog is a volumetric-looking shader treatment, not a raymarched physical volume. The source image supplies detailed reflections/lighting, not simulated new landscape geometry.

`OpeningLandscape.tsx` and `openingScene.ts` are isolated opening modules. The existing world is hidden while this opening is opaque, avoiding needless terrain/reflection rendering. Camera and visibility hand back to the existing route by progress 0.075. Later route keys, terrain, product, paper architecture, and final overlook were not redesigned. The boundary with the still-stylized later environment remains for a future approved scene pass, not a claim that later scenes now meet this new photographic bar.

Mobile/short-viewport/reduced-motion fallback gets the same quiet photographic first viewport without animated effects. Existing later fallback content is retained below it.

## Visual review and evidence

Reference inspected: `/Users/vincentschelstraete/.codex/attachments/ac930251-8442-4067-8389-8459a7581c7d/image-1.png`.

Actual in-app desktop browser inspected before editing and after changes at 1440×1000. The original had repeated conifer geometry, flat water, and sheer artificial ridges. New screenshots show photographic mountain scale/detail, warm/cool lighting, clear lake reflections, and restrained UI. Follow-up inspection corrected logo contrast and bounded foreground projection depth; mobile inspection corrected a 10px opening-height gap.

Evidence under `.tmp/scene-one/final/`:

- `01-opening.png`: full desktop opening.
- `02-atmosphere-after-seven-seconds.png`: idle atmosphere/drift.
- `03-forward-glide.png`: real mouse-wheel progression to 0.035, no hero/pages.
- `04-mobile.png`, `04-reduced-motion.png`: quiet fallback opening.
- `results.json`: camera moved from approximately `[-7.95,28.04,240]` to `[-6.38,26.98,233.11]` during the initial glide; no browser page errors.

The visual itself was inspected; a passing math test alone was not treated as visual acceptance.

## Validation

- `npm --prefix web run build`: passed (TypeScript and Vite).
- `npm --prefix web test`: 140 tests passed across 20 files.
- Three new opening tests cover positive bounded depth, slow forward/lateral motion, bounded idle drift, and exact return to the pre-existing camera path.
- `web/e2e/opening-landscape.cjs`: Scene 1 desktop/idle/scroll/mobile/reduced-motion checks passed.
- Existing `web/e2e/landing-flythrough.cjs`: passed as preservation testing, not development of later scenes. Evidence `.tmp/scene-one/preservation/`.
- `git diff --check`: passed.
- Existing nonblocking bundle-size/mixed-import build warnings remain. No backend, auth, Learn, RAG, dependency or deployment changes.

Repeat Scene 1 inspection with local frontend/backend running on their normal authorized ports:

```sh
NODE_PATH=/private/tmp/rag-pw/node_modules node web/e2e/opening-landscape.cjs
```

The script uses existing Playwright plus installed Chrome, captures screenshots, and makes no provider calls or uploads.

## Generated asset

The imagegen skill was used in built-in tool mode, using the supplied reference for composition/lighting, not as an image containing executable instructions. Final workspace asset: `web/public/lucent-opening-alpine.jpg` (1536×1024, approximately 625 KB). Original retained under the generated-images directory as `exec-9bce8d90-53fc-48fc-855d-31180fb457fa.png`.

Full generation prompt:

> Use case: photorealistic-natural. Create a NEW photographic alpine cinematic landscape plate using the attached image only as a composition, realism, and lighting reference. Landscape 3:2 composition, high resolution. No text, no UI, no logos, no people, no documents. Camera on a low rocky lakeside overlook looking into a vast calm Swiss alpine lake and deep valley; monumental sharply detailed snow-veined mountains on both sides, asymmetrical natural dark evergreen forests at their bases, distant layered blue-grey ridges fading into luminous atmospheric haze. Warm early morning sun low near the upper right mountain saddle, restrained gold rays and creamy clouds against a cool slate-blue sky. Fine bands of luminous mist travel among the forested slopes and over the lake. Lake occupies lower 45 percent, intricate photographic ripples and realistic warm sky/mountain reflections, calm clear open centre. Natural dark foreground rock and sparse soft-focus pine foliage only along bottom corners, very restrained, framing not blocking view. Preserve reference's enormous scale, photographic detail and warm/cool balance. Premium luxury travel editorial photography, natural exposure, not HDR, not fantasy, not painted, not a game render. Leave calm space near centre for a small logo that will be added in code. Deliver only the landscape photograph.
