import { lazy, Suspense, useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import {
  motion,
  useMotionValueEvent,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from "framer-motion"
import { useReducedMotion } from "../../lib/useReducedMotion"
import styles from "./marketing.module.css"

const ProductDemo = lazy(() =>
  import("./LucentProductDemo").then(module => ({ default: module.LucentProductDemo }))
)
const layers = ["Source material", "Simplify", "Explain", "Visualize", "Practice"]

// Include both scroll endpoints. Native scroll timelines otherwise interpolate
// back to the underlying style after the final authored keyframe.
function useTimeline(progress: MotionValue<number>, points: number[], values: number[]) {
  return useTransform(
    progress,
    [...(points[0] > 0 ? [0] : []), ...points, ...(points[points.length - 1] < 1 ? [1] : [])],
    [
      ...(points[0] > 0 ? [values[0]] : []),
      ...values,
      ...(points[points.length - 1] < 1 ? [values[values.length - 1]] : []),
    ]
  )
}

function useTimelineStr(progress: MotionValue<number>, points: number[], values: string[]) {
  return useTransform(
    progress,
    [...(points[0] > 0 ? [0] : []), ...points, ...(points[points.length - 1] < 1 ? [1] : [])],
    [
      ...(points[0] > 0 ? [values[0]] : []),
      ...values,
      ...(points[points.length - 1] < 1 ? [values[values.length - 1]] : []),
    ]
  )
}

function DocumentPage({
  index,
  activeCard,
  staticStory,
  reduced,
  onNext,
}: {
  index: number
  activeCard: number
  staticStory: boolean
  reduced: boolean
  onNext: () => void
}) {
  const offset = index - activeCard
  const active = offset === 0
  const clickable = activeCard < layers.length - 1 && (active || (!staticStory && offset === 1))
  return (
    <motion.div
      data-paper-layer={index}
      data-active={active}
      className={styles.documentPage}
      aria-hidden={!active && !clickable ? true : undefined}
      initial={false}
      animate={{
        x: active ? 0 : offset < 0 ? -60 : offset * 38,
        y: active ? 0 : offset < 0 ? 12 : -offset * 9,
        z: active ? 100 : offset < 0 ? 160 : 100 - offset * 85,
        rotateY: active ? (staticStory ? 0 : -5) : offset < 0 ? -108 : -10,
        rotateX: active ? 0 : 3,
        rotateZ: active ? (staticStory ? 0 : -1) : -5 + offset,
        opacity: active || (!staticStory && offset > 0) ? 1 : 0,
      }}
      transition={{ duration: reduced ? 0 : 0.55, ease: [0.22, 0.68, 0.2, 1] }}
    >
      <div className={styles.pageTopline}>
        <span>{index ? "Lucent / " + layers[index] : "Biology / Reading notes"}</span>
        <span>0{index + 1}</span>
      </div>
      <p className={styles.paperKicker}>{index ? layers[index] : "Cellular quality control"}</p>
      <h2>
        {index === 0 ? (
          <>
            When a cell
            <br />
            finds damage.
          </>
        ) : index === 1 ? (
          <>
            The essential
            <br />
            idea.
          </>
        ) : index === 2 ? (
          <>
            Detection is
            <br />
            only the start.
          </>
        ) : index === 3 ? (
          <>
            See the
            <br />
            connection.
          </>
        ) : (
          <>
            Put the idea
            <br />
            to work.
          </>
        )}
      </h2>
      <p>
        {index === 0
          ? "Cells continually monitor their proteins. When a protein loses its working shape, a control signal coordinates the response."
          : index === 1
            ? "Finding damage is not the same as fixing it. A signal connects what the cell detects to what it does next."
            : index === 2
              ? "Think of a smoke alarm: it detects a problem and calls for action. It does not put out the fire itself."
              : index === 3
                ? "Follow the signal from detection to a protective response."
                : "A cell detects damage, but its signal is blocked. Would detection alone protect the cell?"}
      </p>
      <div className={styles.paperRule} />
      {index === 3 ? (
        <div className={styles.paperFlow}>
          <span>Damage detected</span>
          <i>↓</i>
          <span>Signal sent</span>
          <i>↓</i>
          <span>Response begins</span>
        </div>
      ) : (
        <>
          <p className={styles.paperDetail}>
            {index === 0
              ? "The response may repair or remove a faulty protein, preventing it from disrupting other processes. Detection, signalling, and response each play a different part in protecting the cell."
              : index === 4
                ? "Look for the missing connection between noticing the damage and responding to it."
                : "Understanding the relationship matters more than remembering each label on its own."}
          </p>
          <div className={styles.paperLines}>
            <i />
            <i />
            <i />
            <i />
          </div>
          <div className={styles.paperNote}>
            {index === 0
              ? "01 — Detect. Signal. Respond."
              : index === 4
                ? "Reason from what you know."
                : "Same source. A clearer explanation."}
          </div>
        </>
      )}
      {clickable && (
        <button
          type="button"
          className={styles.pageTurnTarget}
          aria-label={`Show ${layers[activeCard + 1]} page`}
          onClick={onNext}
        />
      )}
    </motion.div>
  )
}

// Monolith sheet — one thin paper layer of the distant document tower
function MonolithSheet({ index, total }: { index: number; total: number }) {
  const t = index / (total - 1) // 0..1
  return (
    <div
      className={styles.monolithSheet}
      style={{
        transform: `translateZ(${-index * 3}px) translateX(${(t - 0.5) * 8}px) rotateY(${(t - 0.5) * 4}deg)`,
        opacity: 1 - t * 0.35,
      }}
    />
  )
}

const MONOLITH_SHEETS = 28

export function SpatialStory() {
  const ref = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const [compact, setCompact] = useState(
    () => window.matchMedia("(max-width: 950px), (max-height: 620px)").matches
  )
  const [beat, setBeat] = useState(0)
  const [loadDemo, setLoadDemo] = useState(false)
  const [activeCard, setActiveCard] = useState(0)
  const gesture = useRef<{ x: number; y: number } | null>(null)
  const suppressClick = useRef(false)
  const tiltX = useSpring(0, { stiffness: 160, damping: 25 })
  const tiltY = useSpring(0, { stiffness: 160, damping: 25 })

  const { scrollYProgress: p } = useScroll({ target: ref, offset: ["start start", "end end"] })

  useEffect(() => {
    const query = window.matchMedia("(max-width: 950px), (max-height: 620px)")
    const update = () => setCompact(query.matches)
    query.addEventListener("change", update)
    return () => query.removeEventListener("change", update)
  }, [])

  const staticStory = reduced || compact

  useEffect(() => {
    if (window.location.hash !== "#learn-in-action") return
    const frame = requestAnimationFrame(() => {
      document.getElementById("learn-in-action")?.scrollIntoView({ behavior: "instant", block: "start" })
    })
    return () => cancelAnimationFrame(frame)
  }, [])

  useMotionValueEvent(p, "change", value => {
    setBeat(value < 0.42 ? 0 : value < 0.62 ? 1 : value < 0.89 ? 2 : 3)
    if (value > 0.40) setLoadDemo(true)
  })

  // ─────────────────────────────────────────────────────────────────────────
  // STAGE 1: THE DESCENT  (p: 0 → 0.18)
  // Camera begins high, looking down. As user scrolls the viewpoint descends.
  // Headline sits forward on Z like a physical signpost the camera flies past.
  // ─────────────────────────────────────────────────────────────────────────

  // Perspective origin Y: starts elevated (30%) → neutral (50%)
  const perspOriginY = useTimelineStr(p, [0, 0.18, 0.42], ["30%", "50%", "50%"])

  // Hero headline: starts slightly forward on Z (camera flies past it)
  const heroZ = useTimeline(p, [0, 0.14, 0.32, 0.41], [60, 20, 0, 0])
  const heroY = useTimeline(p, [0, 0.14, 0.32, 0.41], [-18, -6, 0, 0])
  const heroOpacity = useTimeline(p, [0, 0.32, 0.41], [1, 1, 0])

  // ─────────────────────────────────────────────────────────────────────────
  // STAGE 2: THE FOREST FLY-BY  (p: 0.18 → 0.42)
  // Camera levels, accelerates forward. Landscape rushes by. Document monolith
  // grows from small/distant (Z = -2400) to near (Z = -500).
  // ─────────────────────────────────────────────────────────────────────────

  // Landscape — dramatic forward push
  const landscapeScale = useTimeline(p, [0, 0.18, 0.42, 0.62, 1], [1.04, 1.10, 1.55, 1.62, 1.65])
  const landscapeY = useTimeline(p, [0, 0.18, 0.42, 0.62, 1], [0, -4, -90, -105, -118])
  const landscapeX = useTimeline(p, [0, 0.18, 0.42, 0.62, 1], [0, -5, -95, -108, -132])

  // Foreground treeline — faster parallax than background
  const foregroundY = useTimeline(p, [0, 0.18, 0.42, 1], [0, 15, 195, 235])
  const foregroundScale = useTimeline(p, [0, 0.18, 0.42, 1], [1.04, 1.10, 1.70, 1.78])

  // Document monolith — distant tower approaching through Stage 2, passing
  // through camera plane at ~p=0.60, re-emerging behind for Stage 4.
  const monolithZ = useTimeline(
    p,
    [0, 0.14, 0.42, 0.58, 0.62, 0.88, 1],
    [-2400, -2200, -500, 200, 400, 0, -800]
  )
  const monolithScale = useTimeline(
    p,
    [0, 0.14, 0.42, 0.58, 0.62, 0.88, 1],
    [0.18, 0.22, 0.9, 1.4, 1.0, 0.85, 0.7]
  )
  const monolithOpacity = useTimeline(
    p,
    [0, 0.08, 0.42, 0.55, 0.62, 0.86, 0.92, 1],
    [0, 1, 1, 0.2, 0, 0, 1, 1]
  )
  const monolithRotateY = useTimeline(p, [0, 0.42, 0.58], [0, 0, 4])

  // ─────────────────────────────────────────────────────────────────────────
  // STAGE 3: ENTERING THE DOCUMENT SPACE  (p: 0.62 → 0.88)
  // Camera passes through the front plane. Interactive demo is the focal plane.
  // Floating nodes at staggered Z depths surround the reading arena.
  // ─────────────────────────────────────────────────────────────────────────

  const clarityOpacity = useTimeline(p, [0.42, 0.46, 0.56, 0.62], [0, 1, 1, 0])

  // Interactive demo entrance (preserved from original)
  const productOpacity = useTimeline(p, [0.62, 0.70], [0, 1])
  const productScale = useTimeline(p, [0.60, 0.70, 0.85, 1], [0.92, 1, 1, 0.55])
  const productZ = useTimeline(p, [0.60, 0.70, 0.85, 1], [-120, 0, 0, -500])
  const productRotateY = useTimeline(p, [0.60, 0.70, 0.85, 1], [-8, 0, 0, -26])
  const productX = useTimeline(p, [0.60, 0.70, 0.85, 1], [40, 0, 0, 450])
  const productY = useTimeline(p, [0.60, 0.70, 0.85, 1], [40, 0, 0, 30])

  // Floating interaction nodes — staged Z depth cloud
  const node1Opacity = useTimeline(p, [0.63, 0.70, 0.85, 0.94], [0, 1, 1, 0])
  const node2Opacity = useTimeline(p, [0.65, 0.72, 0.85, 0.94], [0, 1, 1, 0])
  const node3Opacity = useTimeline(p, [0.67, 0.74, 0.85, 0.94], [0, 1, 1, 0])
  const node1Z = useTimeline(p, [0.62, 0.72], [-200, -60])
  const node2Z = useTimeline(p, [0.62, 0.74], [-300, -140])
  const node3Z = useTimeline(p, [0.62, 0.76], [-400, -220])

  // Capability labels — staggered Z so they sit at different depth planes
  const capLabelsOpacity = useTimeline(p, [0, 0.32, 0.41, 0.62, 0.70], [1, 1, 0, 0, 1])

  // ─────────────────────────────────────────────────────────────────────────
  // STAGE 4: CONVERGENCE & EXIT  (p: 0.88 → 1.0)
  // Camera pulls wide. Document monolith re-converges. Resolution copy aligns.
  // ─────────────────────────────────────────────────────────────────────────

  const endingOpacity = useTimeline(p, [0.94, 1], [0, 1])

  // ─────────────────────────────────────────────────────────────────────────
  // FOG LAYERS  (shared across stages)
  // ─────────────────────────────────────────────────────────────────────────
  const fogFarX = useTimeline(p, [0, 1], [-100, 160])
  const fogNearX = useTimeline(p, [0, 0.5, 1], [100, -90, -280])
  const fogNearY = useTimeline(p, [0, 0.32, 0.40, 0.48, 1], [0, -10, -160, -50, -90])
  const fogNearOpacity = useTimeline(
    p,
    [0, 0.32, 0.40, 0.48, 0.70, 0.85, 1],
    [0.8, 0.8, 1, 0.4, 0.14, 0.14, 0.48]
  )
  const fogBetweenX = useTimeline(p, [0, 0.5, 1], [-80, 80, 140])
  // New stage-2 mist sweep — rushes across the lower frame during the fly-by
  const fogSweepX = useTimeline(p, [0.14, 0.42, 0.55], [120, -160, -320])
  const fogSweepOpacity = useTimeline(
    p,
    [0.14, 0.20, 0.38, 0.46, 0.55],
    [0, 0.9, 0.9, 0.5, 0]
  )
  const fogDeepX = useTimeline(p, [0, 0.42, 1], [-60, 80, 180])
  const fogDeepOpacity = useTimeline(p, [0, 0.14, 0.42, 0.62], [0.6, 0.6, 0.9, 0])

  // ─────────────────────────────────────────────────────────────────────────
  // DOCUMENT SCENE (interactive card reader)
  // ─────────────────────────────────────────────────────────────────────────
  const documentX = useTimeline(p, [0, 0.33, 0.43], [0, 0, 100])
  const documentY = useTimeline(p, [0, 0.33, 0.43], [0, 0, 180])
  const documentScale = useTimeline(p, [0, 0.33, 0.43], [1, 1, 0.65])
  const documentOpacity = useTimeline(p, [0.34, 0.42], [1, 0])

  // Misc
  const scrollCueOpacity = useTimeline(p, [0, 0.1, 0.2], [1, 1, 0])
  const accessible = (active: boolean) => ({
    "aria-hidden": !staticStory && !active ? (true as const) : undefined,
    ...(!staticStory && !active ? { inert: "" } : {}),
  })

  function turnPage(direction: number) {
    setActiveCard(current => Math.max(0, Math.min(layers.length - 1, current + direction)))
  }

  return (
    <main
      ref={ref}
      className={styles.spatialStory}
      data-static-story={staticStory}
      aria-label="From source material to understanding"
    >
      <a className={styles.skipLink} href="#learn-in-action">
        Skip to interactive preview
      </a>
      {!staticStory && (
        <div id="learn-in-action" className={styles.demoAnchor} tabIndex={-1} />
      )}

      {/* ── Sticky camera viewport ── */}
      <div className={styles.storySticky}>
        {/* Camera viewport: perspective-origin animates the "descent" */}
        <motion.div
          className={styles.cameraViewport}
          style={staticStory ? undefined : { perspectiveOrigin: useTransform(perspOriginY, y => `50% ${y}`) }}
        >
          {/* ── Environment layer (background + atmospheric elements) ── */}
          <div className={styles.environment} aria-hidden="true">
            <motion.img
              className={styles.landscape}
              src="/lucent-landscape.jpg"
              width="1672"
              height="941"
              fetchPriority="high"
              alt=""
              style={
                staticStory
                  ? undefined
                  : { scale: landscapeScale, x: landscapeX, y: landscapeY }
              }
            />
            <div className={styles.landscapeShade} />
            <motion.div
              className={styles.foreground}
              style={staticStory ? undefined : { scale: foregroundScale, y: foregroundY }}
            />

            {/* Deep atmospheric fog — rolls in during descent */}
            <motion.div
              className={`${styles.fog} ${styles.fogDeep}`}
              style={staticStory ? undefined : { x: fogDeepX, opacity: fogDeepOpacity }}
            />

            {/* Far-field fog drifting right across mountains */}
            <motion.div
              className={`${styles.fog} ${styles.fogFar}`}
              style={staticStory ? undefined : { x: fogFarX }}
            />

            {/* ── Document monolith — the distant paper tower ── */}
            {!staticStory && (
              <motion.div
                className={styles.documentMonolith}
                style={{
                  z: monolithZ,
                  scale: monolithScale,
                  opacity: monolithOpacity,
                  rotateY: monolithRotateY,
                }}
              >
                {Array.from({ length: MONOLITH_SHEETS }, (_, i) => (
                  <MonolithSheet key={i} index={i} total={MONOLITH_SHEETS} />
                ))}
                {/* Monolith top-page text (visible when approaching in Stage 2) */}
                <div className={styles.monolithTopPage}>
                  <span className={styles.monolithTitle}>When we'll</span>
                  <span className={styles.monolithSubtitle}>find courage</span>
                </div>
              </motion.div>
            )}

            {/* Stage-2 mist sweep — rushes across lower frame during fly-by */}
            <motion.div
              className={`${styles.fog} ${styles.fogSweep}`}
              style={
                staticStory ? undefined : { x: fogSweepX, opacity: fogSweepOpacity }
              }
            />
          </div>

          {/* ── STAGE 1: Hero copy — Z-signpost ── */}
          <motion.div
            className={`${styles.storyCopy} ${styles.heroStoryCopy}`}
            {...accessible(beat === 0)}
            style={
              staticStory
                ? undefined
                : { opacity: heroOpacity, z: heroZ, y: heroY }
            }
          >
            <p className={styles.eyebrowLight}>Read. Understand. Go further.</p>
            <h1 className={styles.storyHeadline}>
              Turn any
              <br />
              material into
              <br />
              <em>understanding.</em>
            </h1>
            <p className={styles.storyBody}>
              Your documents, opened up.
              <br />
              Clear explanations, interactive visuals, and a tutor that helps the idea click.
            </p>
            <div className={styles.heroActions}>
              <Link to="/signup" className={styles.btnLight}>
                Get started <span aria-hidden="true">↗</span>
              </Link>
              <a href="#learn-in-action" className={styles.watchLink}>
                <span aria-hidden="true">▷</span> Explore Lucent
              </a>
            </div>
          </motion.div>

          {/* ── STAGE 1 / 2: Interactive document stack ── */}
          <motion.div
            className={styles.documentScene}
            {...accessible(beat === 0)}
            style={
              staticStory
                ? undefined
                : { x: documentX, y: documentY, scale: documentScale, opacity: documentOpacity }
            }
          >
            <motion.div
              className={styles.documentStack}
              style={reduced || compact ? undefined : { rotateX: tiltX, rotateY: tiltY }}
              onPointerMove={event => {
                if (reduced || compact || event.pointerType !== "mouse") return
                const bounds = event.currentTarget.getBoundingClientRect()
                tiltX.set((0.5 - (event.clientY - bounds.top) / bounds.height) * 5)
                tiltY.set(((event.clientX - bounds.left) / bounds.width - 0.5) * 5)
              }}
              onPointerLeave={() => {
                tiltX.set(0)
                tiltY.set(0)
              }}
              onPointerDown={event => {
                suppressClick.current = false
                gesture.current =
                  event.pointerType === "touch" ? { x: event.clientX, y: event.clientY } : null
              }}
              onPointerCancel={() => {
                gesture.current = null
              }}
              onPointerUp={event => {
                const start = gesture.current
                gesture.current = null
                if (!start) return
                const dx = event.clientX - start.x
                const dy = event.clientY - start.y
                if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
                  suppressClick.current = true
                  turnPage(dx < 0 ? 1 : -1)
                }
              }}
              onClickCapture={event => {
                if (suppressClick.current) {
                  event.preventDefault()
                  event.stopPropagation()
                  suppressClick.current = false
                }
              }}
            >
              {[4, 3, 2, 1, 0].map(index => (
                <DocumentPage
                  key={index}
                  index={index}
                  activeCard={activeCard}
                  staticStory={staticStory}
                  reduced={reduced}
                  onNext={() => turnPage(1)}
                />
              ))}
              <motion.div
                className={`${styles.fog} ${styles.fogBetween}`}
                style={{ x: fogBetweenX, z: -400 }}
              />
            </motion.div>

            {/* Capability labels — staggered Z in Stage 3 */}
            <motion.div
              className={styles.capabilityLabels}
              style={staticStory ? undefined : { opacity: capLabelsOpacity }}
              aria-hidden="true"
            >
              <span style={{ transform: "translateZ(40px)" }}>Simplify</span>
              <span style={{ transform: "translateZ(20px)" }}>Explain</span>
              <span style={{ transform: "translateZ(60px)" }}>Visualize</span>
              <span style={{ transform: "translateZ(10px)" }}>Practice</span>
              <span style={{ transform: "translateZ(50px)" }}>Learn</span>
            </motion.div>
            <p className={styles.paperCaption} aria-hidden="true">
              From pages
              <br />
              to progress.
            </p>
          </motion.div>

          {/* Page controls */}
          <motion.div
            className={styles.pageControls}
            {...accessible(beat === 0)}
            style={staticStory ? undefined : { opacity: heroOpacity }}
            aria-label="Explore the source pages"
          >
            <button
              type="button"
              aria-label="Previous source page"
              disabled={activeCard === 0}
              onClick={() => turnPage(-1)}
            >
              ←
            </button>
            <span aria-live="polite">
              {activeCard + 1} / {layers.length} · {layers[activeCard]}
            </span>
            <button
              type="button"
              aria-label="Next source page"
              disabled={activeCard === layers.length - 1}
              onClick={() => turnPage(1)}
            >
              →
            </button>
          </motion.div>

          {/* ── STAGE 2: Clarity copy ── */}
          <motion.div
            className={`${styles.storyCopy} ${styles.clarityCopy}`}
            {...accessible(beat === 1)}
            style={staticStory ? undefined : { opacity: clarityOpacity }}
          >
            <p className={styles.eyebrowLight}>A calmer way to learn</p>
            <h2 className={styles.storyHeading}>
              Same material.
              <br />
              <em>A clearer path.</em>
            </h2>
            <p className={styles.storyBody}>
              Read it. See it. Try it.
              <br />
              Keep the explanation beside the question, so understanding has room to grow.
            </p>
          </motion.div>

          {/* ── STAGE 3: Interactive product demo ── */}
          <motion.section
            id={staticStory ? "learn-in-action" : undefined}
            tabIndex={-1}
            className={styles.productStage}
            {...accessible(beat === 2)}
            aria-label="Interactive Lucent preview"
            style={
              staticStory
                ? undefined
                : {
                    opacity: productOpacity,
                    scale: productScale,
                    rotateY: productRotateY,
                    x: productX,
                    y: productY,
                    z: productZ,
                  }
            }
          >
            <div className={styles.productStageIntro}>
              <div>
                <p className={styles.eyebrowLight}>See Lucent in action</p>
                <h2>
                  From reading <em>to reasoning.</em>
                </h2>
              </div>
              <p>
                Try an answer. Ask for another explanation.
                <br />
                See what happens when the idea clicks.
              </p>
            </div>
            {(loadDemo || staticStory) && (
              <Suspense
                fallback={
                  <div className={styles.demoLoading} role="status">
                    Opening the learning preview…
                  </div>
                }
              >
                <ProductDemo />
              </Suspense>
            )}
          </motion.section>

          {/* ── STAGE 3: Floating interaction depth nodes ── */}
          {!staticStory && (
            <div className={styles.floatingNodes} aria-hidden="true">
              <motion.div
                className={`${styles.floatingNode} ${styles.floatingNodeA}`}
                style={{ opacity: node1Opacity, z: node1Z }}
              />
              <motion.div
                className={`${styles.floatingNode} ${styles.floatingNodeB}`}
                style={{ opacity: node2Opacity, z: node2Z }}
              />
              <motion.div
                className={`${styles.floatingNode} ${styles.floatingNodeC}`}
                style={{ opacity: node3Opacity, z: node3Z }}
              />
            </div>
          )}

          {/* Near fog — crosses in front of documents for physical occlusion */}
          <motion.div
            className={`${styles.fog} ${styles.fogNear}`}
            aria-hidden="true"
            style={
              staticStory ? undefined : { x: fogNearX, y: fogNearY, opacity: fogNearOpacity }
            }
          />

          {/* ── STAGE 4: Resolution copy ── */}
          <motion.section
            className={styles.resolutionCopy}
            {...accessible(beat === 3)}
            aria-label="Go further with Lucent"
            style={staticStory ? undefined : { opacity: endingOpacity }}
          >
            <p className={styles.eyebrowLight}>Go further</p>
            <h2>
              A little further
              <br />
              from the familiar.
            </h2>
            <p>
              Bring your material.
              <br />
              Leave with a new way of seeing it.
            </p>
            <Link to="/signup" className={styles.btnLight}>
              Begin with your material <span aria-hidden="true">↗</span>
            </Link>
          </motion.section>

          {/* Scroll cue */}
          <motion.div
            className={styles.scrollCue}
            aria-hidden="true"
            style={staticStory ? undefined : { opacity: scrollCueOpacity }}
          >
            <span /> Scroll to explore
          </motion.div>

          {/* Stage index */}
          <div className={styles.storyIndex} aria-hidden="true">
            <span>0{beat + 1}</span>
            <i />
            <span>{["Your material", "A clearer path", "Learn with Lucent", "Go further"][beat]}</span>
          </div>
        </motion.div>
      </div>
    </main>
  )
}
