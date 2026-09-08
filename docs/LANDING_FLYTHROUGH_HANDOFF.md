# Landing flythrough checkpoint

Updated: 2026-09-08. Scope: the public marketing landing page only. No Learn runtime, RAG, authentication, API, database, dependency, or deployment architecture changes.

## Implemented journey

One persistent Three.js world and one spline-driven perspective camera replace the disconnected scene treatment. Scroll translates the camera more than 500 world units, changes elevation, turns its gaze, and gently banks; the field of view remains fixed. The five beats are:

1. An unobstructed alpine opening with a scroll invitation.
2. Sliding introductory typography and physically descending source pages. Manual arrows/clicks turn pages; scrolling does not cycle them.
3. Pages separate and descend into depth-positioned mist while the camera approaches the open lake.
4. Curved, closed paper ribbons descend and spiral into architecture around the camera. World-space feature surfaces and the existing interactive product preview are encountered inside it. The camera passes beside, not through, the solid preview board.
5. Paper structures unravel and fall away; the camera reaches a lake overlook with a small back-facing human silhouette.

Terrain, trees, water, paper, and fog occupy the same world. The distant photographic environment is a matte, not a separate scrolling background. Native HTML is perspective-projected for the interactive preview and depth-occluded by geometry. Its projected wrapper is fixed to the viewport so focusing controls cannot reset the document scroll/camera.

Mobile, short viewports, reduced motion, and unavailable/lost WebGL use a normal-flow, accessible fallback with manual cards and the same preview. The interactive preview keeps its state when scrolling away and returning.

## Ownership

- `web/src/components/marketing/flythrough.ts`: authored camera route, document/architecture timing, smooth closed paper geometry, terrain geometry.
- `HeroScene.tsx`: persistent environment, physical documents/architecture, embedded feature surfaces, camera, and final overlook.
- `SpatialStory.tsx` and `marketing.module.css`: scroll driver, restrained copy/navigation, projected HTML, fallback behavior.
- `LucentProductDemo.tsx`: only exports the existing quality-control visual specification for reuse; its tutoring behavior is unchanged.
- `flythrough.test.ts`: nine geometry, timing, continuity, and collision regressions.
- `web/e2e/landing-flythrough.cjs`: repeatable browser journey and fallback/interaction checks.

## Validation and browser evidence

- `npm --prefix web run build`: passed, including TypeScript compilation.
- `npm --prefix web test`: 137 tests passed across 19 files.
- Focused `flythrough.test.ts`: 9 passed.
- `git diff --check`: passed.
- Development browser journey: passed, screenshots/results in `.tmp/flythrough/validated/`.
- Production-build browser journey on the authorized port 5173: passed, including all interaction/fallback checks and no page errors; evidence in `.tmp/flythrough/production-authorized/`.
- Continuous real mouse-wheel run: 90 scroll steps, final progress 1.000, no page errors. Camera positions, final frame, and recording in `.tmp/flythrough/continuous/`.
- Browser checks cover all five beats and intermediate transitions, source-page navigation, wrong-answer teaching, Ask response replacement, guided success, visual expansion, keyboard focus containment, no scroll reset, return-to-preview state, deep link, mobile/reduced-motion layouts, and WebGL context-loss recovery.
- The preview is the existing local marketing example. These checks do not claim a new authenticated Learn/RAG acceptance run and do not upload student material or call providers.

Repeat with an installed Playwright package and Chrome (this machine has Playwright at `/private/tmp/rag-pw/node_modules`):

```sh
NODE_PATH=/private/tmp/rag-pw/node_modules BROWSER_CHANNEL=chrome EVIDENCE_DIR=.tmp/flythrough/acceptance node web/e2e/landing-flythrough.cjs
```

To test the built frontend, temporarily serve `npm --prefix web run preview -- --host 127.0.0.1 --port 5173 --strictPort` instead of Vite dev, then run the same browser command. Use the existing authorized origin. A first trial on port 4173 completed the scene interactions but failed the no-page-error assertion because the existing backend does not authorize that origin for `/auth/me`. No auth/CORS settings were weakened to accommodate the preview.

## Limits and visual judgment

- This is a textured real-time 3D interpretation of the references, not a photogrammetric or pixel-identical recreation. Near terrain/trees and paper architecture remain visibly stylized compared with the photographic reference images.
- WebGL water reflects world geometry, but not the DOM content projected onto the product board.
- A local Chrome/M4 Pro motion sample measured about 17.1 ms average frame time. This is a single-machine observation, not a cross-device performance guarantee. Demand rendering avoids continuous idle rendering; desktop pixel ratio is capped at 1.5.
- Mobile/reduced-motion intentionally do not run the camera flight.
- Build retains non-blocking chunk-size warnings. Reusing the visual specification via the demo module also prevents its nominal lazy import from becoming a separate chunk. No unrelated bundling refactor was made.
- Existing unrelated dirty files were preserved and excluded from this checkpoint.

## Generated assets and full prompts

The imagegen skill supplied two bitmap surface/environment assets using the built-in image-generation tool, not the fallback CLI. Final workspace assets:

- `web/public/lucent-alpine-panorama.jpg`
- `web/public/lucent-alpine-ground.jpg`

Panorama prompt:

> Use case: photorealistic-natural. Asset type: seamless 360-degree equirectangular environment texture for a Three.js alpine lake scene, landscape 2:1 aspect ratio. Create a cinematic photorealistic full spherical panorama from eye level just above the middle of a vast calm alpine lake. Dramatic natural rocky mountain ridges surround the viewer in every direction, dense dark evergreen forests at the shore, pale silver atmospheric fog in layers among the mountains and just above the water, overcast warm early morning light with a little pale gold at horizon. Restrained premium editorial feeling. Upper half: believable soft pale grey sky and mountain peaks; horizon line precisely at vertical center; lower half: natural dark sage lake water with mountain reflections, subtle ripples, no land directly under camera. True equirectangular spherical projection, seamless left/right edges, zenith sky at top, nadir lake at bottom. Colors cool slate, forest green, misty silver, warm ivory highlights. No text, no logo, no buildings, no paper, no people, no fantasy shapes. Must feel like a real Swiss alpine valley, not procedural geometry. This texture will surround real paper architecture in a 3D website.

Ground prompt:

> Use case: photorealistic-natural. Asset type: seamless square albedo texture for 3D alpine terrain. Orthographic straight-down surface scan of weathered grey alpine limestone and slate with dark moss, sparse low alpine grass and fine scree. Approximately a 20-metre patch of continuous rugged ground. Natural dense geological detail, fine fractured stone, subtle crevices and muted sage lichen, subdued grey olive palette. Perfectly flat diffuse overcast lighting, no directional shadows, no horizon, no sky, no trees, no objects, no text. Seamless tiling all four edges, photographic detail, not painted and not low-poly. This is a surface material map, not a landscape composition.
