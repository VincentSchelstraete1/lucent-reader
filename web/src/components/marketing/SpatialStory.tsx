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
  import("./LucentProductDemo").then(m => ({ default: m.LucentProductDemo }))
)

const layers = ["Source material", "Simplify", "Explain", "Visualize", "Practice"]

/**
 * Build an extended keyframe track that clamps before the first point and
 * after the last point so Framer Motion never interpolates back to the
 * underlying style after the final keyframe.
 */
function useTimeline(
  progress: MotionValue<number>,
  points: number[],
  values: number[]
) {
  return useTransform(
    progress,
    [
      ...(points[0] > 0 ? [0] : []),
      ...points,
      ...(points[points.length - 1] < 1 ? [1] : []),
    ],
    [
      ...(points[0] > 0 ? [values[0]] : []),
      ...values,
      ...(points[points.length - 1] < 1 ? [values[values.length - 1]] : []),
    ]
  )
}

// ── DocumentPage (original, unchanged) ────────────────────────────────────
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
        {index === 0 ? (<>When a cell<br />finds damage.</>) :
         index === 1 ? (<>The essential<br />idea.</>) :
         index === 2 ? (<>Detection is<br />only the start.</>) :
         index === 3 ? (<>See the<br />connection.</>) :
         (<>Put the idea<br />to work.</>)}
      </h2>
      <p>
        {index === 0 ? "Cells continually monitor their proteins. When a protein loses its working shape, a control signal coordinates the response." :
         index === 1 ? "Finding damage is not the same as fixing it. A signal connects what the cell detects to what it does next." :
         index === 2 ? "Think of a smoke alarm: it detects a problem and calls for action. It does not put out the fire itself." :
         index === 3 ? "Follow the signal from detection to a protective response." :
         "A cell detects damage, but its signal is blocked. Would detection alone protect the cell?"}
      </p>
      <div className={styles.paperRule} />
      {index === 3 ? (
        <div className={styles.paperFlow}>
          <span>Damage detected</span><i>↓</i>
          <span>Signal sent</span><i>↓</i>
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
          <div className={styles.paperLines}><i /><i /><i /><i /></div>
          <div className={styles.paperNote}>
            {index === 0 ? "01 — Detect. Signal. Respond." : index === 4 ? "Reason from what you know." : "Same source. A clearer explanation."}
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

// ── FanPage ────────────────────────────────────────────────────────────────
// One page in the Stage 3 interior document-space spread.
// Each FanPage is its own component so all useTransform calls are at the
// top level of a component (Rules of Hooks compliant).
function FanPage({
  index,
  total,
  fanProgress,
}: {
  index: number
  total: number
  fanProgress: MotionValue<number>
}) {
  const t = index / (total - 1)      // 0..1
  const c = t - 0.5                  // −0.5..0.5  (negative = left, positive = right)
  const absC = Math.abs(c)

  // Pages sweep out to ±74 degrees at full open
  const rotateY = useTransform(fanProgress, (p) => c * p * 148)
  // Outer pages recede in Z, centre pages stay close to camera
  const z = useTransform(fanProgress, (p) => -(28 + absC * p * 360))
  // Slight horizontal nudge so pages don't all share the exact same XY origin
  const x = useTransform(fanProgress, (p) => c * p * 32)
  const opacity = useTransform(fanProgress, (p) => {
    const entering = Math.min(1, p * 5)
    // Very outermost pages (near 74 deg) fade — they go nearly edge-on
    const edgeFade = absC > 0.44 ? Math.max(0, 1 - (absC - 0.44) / 0.06) : 1
    const brightness = 0.55 + (1 - absC) * 0.45
    return entering * brightness * edgeFade
  })

  return (
    <motion.div
      className={styles.fanPage}
      style={{ rotateY, z, x, opacity }}
    />
  )
}

const FAN_COUNT = 22

// Renders the complete fanning page spread
function PageFan({ fanProgress }: { fanProgress: MotionValue<number> }) {
  return (
    <div className={styles.pageFan} aria-hidden="true">
      {Array.from({ length: FAN_COUNT }, (_, i) => (
        <FanPage key={i} index={i} total={FAN_COUNT} fanProgress={fanProgress} />
      ))}
    </div>
  )
}

// ── MonolithTower ─────────────────────────────────────────────────────────
// The distant paper-stack tower visible in Stages 1–2 and 4.
// Uses a CSS 3D box: front face (paper surface) + right face (visible paper
// edges via repeating-linear-gradient) to match the existing card aesthetic.
function MonolithTower() {
  return (
    <div className={styles.monolithBox}>
      {/* Front face — readable top page */}
      <div className={styles.monolithFront}>
        <div className={styles.monolithContent}>
          <div className={styles.monolithTopLine}>
            <span>Reading notes</span>
            <span>01</span>
          </div>
          <strong className={styles.monolithHeading}>
            When a cell<br />finds damage.
          </strong>
          <div className={styles.monolithPLines}>
            <i style={{ width: "88%" }} /><i style={{ width: "95%" }} />
            <i style={{ width: "76%" }} /><i style={{ width: "91%" }} />
            <i style={{ width: "83%" }} /><i style={{ width: "61%" }} />
          </div>
          <div className={styles.monolithRule} />
          <div className={styles.monolithPLines}>
            <i style={{ width: "78%" }} /><i style={{ width: "85%" }} />
            <i style={{ width: "70%" }} /><i style={{ width: "55%" }} />
          </div>
        </div>
      </div>
      {/* Right side face — stacked paper edges revealed by rotateY scroll */}
      <div className={styles.monolithRight} />
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────

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
    const q = window.matchMedia("(max-width: 950px), (max-height: 620px)")
    const upd = () => setCompact(q.matches)
    q.addEventListener("change", upd)
    return () => q.removeEventListener("change", upd)
  }, [])

  const staticStory = reduced || compact

  useEffect(() => {
    if (window.location.hash !== "#learn-in-action") return
    const id = requestAnimationFrame(() =>
      document.getElementById("learn-in-action")?.scrollIntoView({ behavior: "instant", block: "start" })
    )
    return () => cancelAnimationFrame(id)
  }, [])

  useMotionValueEvent(p, "change", value => {
    setBeat(value < 0.42 ? 0 : value < 0.62 ? 1 : value < 0.89 ? 2 : 3)
    if (value > 0.40) setLoadDemo(true)
  })

  // ── PERSPECTIVE ORIGIN ───────────────────────────────────────────────────
  // CRITICAL: must be declared at the top level of the component — NEVER
  // inside a conditional or inline style prop (that would violate Rules of Hooks
  // and silently break the animation).
  //
  // Y goes 28% → 50%: camera starts elevated (looking down), then levels out.
  // This is what creates the "descent" illusion in Stage 1.
  const perspOriginYNum = useTimeline(p, [0, 0.18, 0.42], [28, 50, 50])
  // Build the CSS string outside the JSX (valid hook call site).
  const perspectiveOriginVal = useTransform(perspOriginYNum, y => `50% ${y}%`)

  // ── STAGE 1: THE DESCENT (p: 0 → 0.18) ─────────────────────────────────
  // Headline sits forward on Z — a physical signpost the camera flies past.
  const heroZ       = useTimeline(p, [0, 0.14, 0.32, 0.41], [60, 20, 0, 0])
  const heroY       = useTimeline(p, [0, 0.14, 0.32, 0.41], [-20, -7, 0, 0])
  const heroOpacity = useTimeline(p, [0, 0.32, 0.41], [1, 1, 0])

  // ── STAGE 2: THE FOREST FLY-BY (p: 0.18 → 0.42) ────────────────────────
  // Landscape rushes forward; document monolith approaches from Z = −1400.
  const landscapeScale = useTimeline(p, [0, 0.18, 0.42, 0.62, 1], [1.04, 1.12, 1.58, 1.65, 1.68])
  const landscapeY     = useTimeline(p, [0, 0.18, 0.42, 0.62, 1], [0, -6, -95, -108, -122])
  const landscapeX     = useTimeline(p, [0, 0.18, 0.42, 0.62, 1], [0, -6, -98, -112, -138])
  const foregroundY    = useTimeline(p, [0, 0.18, 0.42, 1], [0, 18, 205, 248])
  const foregroundScale= useTimeline(p, [0, 0.18, 0.42, 1], [1.04, 1.12, 1.72, 1.82])

  // Monolith tower — approaches through Stages 1–2, passes camera in Stage 2→3
  // Z values stay within valid range for perspective:1800px (must be > −1800).
  const monolithZ       = useTimeline(p,
    [0,    0.10,  0.42,  0.56,  0.62,  0.88,  1.0],
    [-1380,-1180, -220,   260,   380,     0, -1100])
  const monolithScale   = useTimeline(p,
    [0,    0.10,  0.42,  0.56,  0.60,  0.86,  0.92,  1.0],
    [0.44, 0.54,  1.00,  1.55,  0.18,  0.18,  0.80,  0.52])
  const monolithOpacity = useTimeline(p,
    [0,    0.06,  0.44,  0.57,  0.62,  0.84,  0.92,  1.0],
    [0,    1,     1,     0.22,  0,     0,     1,     1])
  const monolithRotateY = useTimeline(p, [0, 0.42, 0.56], [2, 6, 11])

  // Clarity copy (Stage 2)
  const clarityOpacity = useTimeline(p, [0.42, 0.46, 0.56, 0.62], [0, 1, 1, 0])

  // ── STAGE 3: ENTERING THE DOCUMENT SPACE (p: 0.62 → 0.88) ──────────────
  // fanProgress drives the PageFan opening: 0 = closed stack, 1 = fully open.
  const fanProgress        = useTimeline(p, [0.62, 0.74, 0.84, 0.88], [0, 1, 1, 0])
  const fanWrapperOpacity  = useTimeline(p, [0.61, 0.66, 0.84, 0.89], [0, 1, 1, 0])

  // Interactive demo panel (unchanged from original)
  const productOpacity  = useTimeline(p, [0.62, 0.70], [0, 1])
  const productScale    = useTimeline(p, [0.60, 0.70, 0.85, 1], [0.92, 1, 1, 0.55])
  const productZ        = useTimeline(p, [0.60, 0.70, 0.85, 1], [-120, 0, 0, -500])
  const productRotateY  = useTimeline(p, [0.60, 0.70, 0.85, 1], [-8, 0, 0, -26])
  const productX        = useTimeline(p, [0.60, 0.70, 0.85, 1], [40, 0, 0, 450])
  const productY        = useTimeline(p, [0.60, 0.70, 0.85, 1], [40, 0, 0, 30])

  // Capability labels staggered in Z
  const capLabelsOpacity = useTimeline(p, [0, 0.32, 0.41, 0.62, 0.70], [1, 1, 0, 0, 1])

  // Floating interaction depth nodes
  const node1Opacity = useTimeline(p, [0.63, 0.70, 0.85, 0.94], [0, 1, 1, 0])
  const node2Opacity = useTimeline(p, [0.65, 0.72, 0.85, 0.94], [0, 1, 1, 0])
  const node3Opacity = useTimeline(p, [0.67, 0.74, 0.85, 0.94], [0, 1, 1, 0])
  const node1Z = useTimeline(p, [0.62, 0.72], [-200, -60])
  const node2Z = useTimeline(p, [0.62, 0.74], [-300, -140])
  const node3Z = useTimeline(p, [0.62, 0.76], [-400, -220])

  // ── STAGE 4: CONVERGENCE & EXIT (p: 0.88 → 1.0) ────────────────────────
  const endingOpacity = useTimeline(p, [0.94, 1], [0, 1])

  // ── Interactive card reader ──────────────────────────────────────────────
  const documentX      = useTimeline(p, [0, 0.33, 0.43], [0, 0, 100])
  const documentY      = useTimeline(p, [0, 0.33, 0.43], [0, 0, 180])
  const documentScale2 = useTimeline(p, [0, 0.33, 0.43], [1, 1, 0.65])
  const documentOpacity= useTimeline(p, [0.34, 0.42], [1, 0])

  // ── Fog layers ───────────────────────────────────────────────────────────
  const fogFarX       = useTimeline(p, [0, 1], [-100, 160])
  const fogNearX      = useTimeline(p, [0, 0.5, 1], [100, -90, -280])
  const fogNearY      = useTimeline(p, [0, 0.32, 0.40, 0.48, 1], [0, -10, -160, -50, -90])
  const fogNearOpacity= useTimeline(p, [0, 0.32, 0.40, 0.48, 0.70, 0.85, 1], [0.8, 0.8, 1, 0.4, 0.14, 0.14, 0.48])
  const fogBetweenX   = useTimeline(p, [0, 0.5, 1], [-80, 80, 140])
  // Stage-2 fly-by mist — sweeps low across frame as camera accelerates
  const fogSweepX       = useTimeline(p, [0.14, 0.42, 0.55], [130, -170, -340])
  const fogSweepOpacity = useTimeline(p, [0.14, 0.22, 0.38, 0.46, 0.55], [0, 1, 1, 0.5, 0])
  // Deep atmospheric mist during descent
  const fogDeepX       = useTimeline(p, [0, 0.42, 1], [-60, 80, 180])
  const fogDeepOpacity = useTimeline(p, [0, 0.14, 0.42, 0.62], [0.6, 0.6, 1.0, 0])

  // Misc
  const scrollCueOpacity = useTimeline(p, [0, 0.1, 0.2], [1, 1, 0])

  const accessible = (active: boolean) => ({
    "aria-hidden": !staticStory && !active ? (true as const) : undefined,
    ...(!staticStory && !active ? { inert: "" } : {}),
  })

  function turnPage(direction: number) {
    setActiveCard(c => Math.max(0, Math.min(layers.length - 1, c + direction)))
  }

  return (
    <main
      ref={ref}
      className={styles.spatialStory}
      data-static-story={staticStory}
      aria-label="From source material to understanding"
    >
      <a className={styles.skipLink} href="#learn-in-action">Skip to interactive preview</a>
      {!staticStory && <div id="learn-in-action" className={styles.demoAnchor} tabIndex={-1} />}

      <div className={styles.storySticky}>
        {/*
          Camera viewport — hosts perspective(1800px).
          perspectiveOriginVal is a MotionValue<string> pre-computed at component
          top level; applying it here is safe and hooks-compliant.
        */}
        <motion.div
          className={styles.cameraViewport}
          style={staticStory ? undefined : { perspectiveOrigin: perspectiveOriginVal }}
        >

          {/* ── Environment (landscape + fog + monolith) ── */}
          <div className={styles.environment} aria-hidden="true">
            <motion.img
              className={styles.landscape}
              src="/lucent-landscape.jpg"
              width="1672" height="941"
              fetchPriority="high" alt=""
              style={staticStory ? undefined : { scale: landscapeScale, x: landscapeX, y: landscapeY }}
            />
            <div className={styles.landscapeShade} />
            <motion.div
              className={styles.foreground}
              style={staticStory ? undefined : { scale: foregroundScale, y: foregroundY }}
            />

            {/* Deep atmospheric mist — rises during descent */}
            <motion.div
              className={`${styles.fog} ${styles.fogDeep}`}
              style={staticStory ? undefined : { x: fogDeepX, opacity: fogDeepOpacity }}
            />
            {/* Far mountain mist — drifts right */}
            <motion.div
              className={`${styles.fog} ${styles.fogFar}`}
              style={staticStory ? undefined : { x: fogFarX }}
            />
            {/* Stage-2 fly-by mist sweep */}
            <motion.div
              className={`${styles.fog} ${styles.fogSweep}`}
              style={staticStory ? undefined : { x: fogSweepX, opacity: fogSweepOpacity }}
            />

            {/* ── Monolith tower (Stages 1–2 and 4) ── */}
            {!staticStory && (
              <motion.div
                className={styles.monolithWrapper}
                style={{
                  z: monolithZ,
                  scale: monolithScale,
                  opacity: monolithOpacity,
                  rotateY: monolithRotateY,
                }}
              >
                <MonolithTower />
              </motion.div>
            )}
          </div>

          {/* ── Stage 1: Hero copy — rides the Z-axis as a signpost ── */}
          <motion.div
            className={`${styles.storyCopy} ${styles.heroStoryCopy}`}
            {...accessible(beat === 0)}
            style={staticStory ? undefined : { opacity: heroOpacity, z: heroZ, y: heroY }}
          >
            <p className={styles.eyebrowLight}>Read. Understand. Go further.</p>
            <h1 className={styles.storyHeadline}>
              Turn any<br />material into<br /><em>understanding.</em>
            </h1>
            <p className={styles.storyBody}>
              Your documents, opened up.<br />
              Clear explanations, interactive visuals, and a tutor that helps the idea click.
            </p>
            <div className={styles.heroActions}>
              <Link to="/signup" className={styles.btnLight}>Get started <span aria-hidden="true">↗</span></Link>
              <a href="#learn-in-action" className={styles.watchLink}>
                <span aria-hidden="true">▷</span> Explore Lucent
              </a>
            </div>
          </motion.div>

          {/* ── Interactive document card stack (Stages 1–2) ── */}
          <motion.div
            className={styles.documentScene}
            {...accessible(beat === 0)}
            style={staticStory ? undefined : {
              x: documentX, y: documentY,
              scale: documentScale2, opacity: documentOpacity,
            }}
          >
            <motion.div
              className={styles.documentStack}
              style={reduced || compact ? undefined : { rotateX: tiltX, rotateY: tiltY }}
              onPointerMove={e => {
                if (reduced || compact || e.pointerType !== "mouse") return
                const b = e.currentTarget.getBoundingClientRect()
                tiltX.set((0.5 - (e.clientY - b.top) / b.height) * 5)
                tiltY.set(((e.clientX - b.left) / b.width - 0.5) * 5)
              }}
              onPointerLeave={() => { tiltX.set(0); tiltY.set(0) }}
              onPointerDown={e => {
                suppressClick.current = false
                gesture.current = e.pointerType === "touch" ? { x: e.clientX, y: e.clientY } : null
              }}
              onPointerCancel={() => { gesture.current = null }}
              onPointerUp={e => {
                const start = gesture.current; gesture.current = null
                if (!start) return
                const dx = e.clientX - start.x; const dy = e.clientY - start.y
                if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
                  suppressClick.current = true; turnPage(dx < 0 ? 1 : -1)
                }
              }}
              onClickCapture={e => {
                if (suppressClick.current) { e.preventDefault(); e.stopPropagation(); suppressClick.current = false }
              }}
            >
              {[4, 3, 2, 1, 0].map(i => (
                <DocumentPage key={i} index={i} activeCard={activeCard}
                  staticStory={staticStory} reduced={reduced} onNext={() => turnPage(1)} />
              ))}
              <motion.div className={`${styles.fog} ${styles.fogBetween}`} style={{ x: fogBetweenX, z: -400 }} />
            </motion.div>

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
            <p className={styles.paperCaption} aria-hidden="true">From pages<br />to progress.</p>
          </motion.div>

          {/* Page controls */}
          <motion.div
            className={styles.pageControls}
            {...accessible(beat === 0)}
            style={staticStory ? undefined : { opacity: heroOpacity }}
            aria-label="Explore the source pages"
          >
            <button type="button" aria-label="Previous source page"
              disabled={activeCard === 0} onClick={() => turnPage(-1)}>←</button>
            <span aria-live="polite">{activeCard + 1} / {layers.length} · {layers[activeCard]}</span>
            <button type="button" aria-label="Next source page"
              disabled={activeCard === layers.length - 1} onClick={() => turnPage(1)}>→</button>
          </motion.div>

          {/* ── Stage 2: Clarity copy ── */}
          <motion.div
            className={`${styles.storyCopy} ${styles.clarityCopy}`}
            {...accessible(beat === 1)}
            style={staticStory ? undefined : { opacity: clarityOpacity }}
          >
            <p className={styles.eyebrowLight}>A calmer way to learn</p>
            <h2 className={styles.storyHeading}>Same material.<br /><em>A clearer path.</em></h2>
            <p className={styles.storyBody}>
              Read it. See it. Try it.<br />
              Keep the explanation beside the question, so understanding has room to grow.
            </p>
          </motion.div>

          {/* ── Stage 3: Page fan — the interior document space ── */}
          {/*
            22 pages fan open radially from ±0° to ±74°, creating the
            "inside the open book" visual from the reference images.
            Outer pages recede in Z for natural perspective depth.
          */}
          {!staticStory && (
            <motion.div
              className={styles.fanWrapper}
              aria-hidden="true"
              style={{ opacity: fanWrapperOpacity }}
            >
              <PageFan fanProgress={fanProgress} />
            </motion.div>
          )}

          {/* ── Stage 3: Interactive product demo ── */}
          <motion.section
            id={staticStory ? "learn-in-action" : undefined}
            tabIndex={-1}
            className={styles.productStage}
            {...accessible(beat === 2)}
            aria-label="Interactive Lucent preview"
            style={staticStory ? undefined : {
              opacity: productOpacity, scale: productScale,
              rotateY: productRotateY, x: productX, y: productY, z: productZ,
            }}
          >
            <div className={styles.productStageIntro}>
              <div>
                <p className={styles.eyebrowLight}>See Lucent in action</p>
                <h2>From reading <em>to reasoning.</em></h2>
              </div>
              <p>Try an answer. Ask for another explanation.<br />See what happens when the idea clicks.</p>
            </div>
            {(loadDemo || staticStory) && (
              <Suspense fallback={<div className={styles.demoLoading} role="status">Opening the learning preview…</div>}>
                <ProductDemo />
              </Suspense>
            )}
          </motion.section>

          {/* Stage 3 floating depth nodes */}
          {!staticStory && (
            <div className={styles.floatingNodes} aria-hidden="true">
              <motion.div className={`${styles.floatingNode} ${styles.floatingNodeA}`} style={{ opacity: node1Opacity, z: node1Z }} />
              <motion.div className={`${styles.floatingNode} ${styles.floatingNodeB}`} style={{ opacity: node2Opacity, z: node2Z }} />
              <motion.div className={`${styles.floatingNode} ${styles.floatingNodeC}`} style={{ opacity: node3Opacity, z: node3Z }} />
            </div>
          )}

          {/* Near fog — physically occludes document edges (proper parallax occlusion) */}
          <motion.div
            className={`${styles.fog} ${styles.fogNear}`}
            aria-hidden="true"
            style={staticStory ? undefined : { x: fogNearX, y: fogNearY, opacity: fogNearOpacity }}
          />

          {/* ── Stage 4: Resolution copy ── */}
          <motion.section
            className={styles.resolutionCopy}
            {...accessible(beat === 3)}
            aria-label="Go further with Lucent"
            style={staticStory ? undefined : { opacity: endingOpacity }}
          >
            <p className={styles.eyebrowLight}>Go further</p>
            <h2>A little further<br />from the familiar.</h2>
            <p>Bring your material.<br />Leave with a new way of seeing it.</p>
            <Link to="/signup" className={styles.btnLight}>Begin with your material <span aria-hidden="true">↗</span></Link>
          </motion.section>

          <motion.div className={styles.scrollCue} aria-hidden="true"
            style={staticStory ? undefined : { opacity: scrollCueOpacity }}>
            <span /> Scroll to explore
          </motion.div>

          <div className={styles.storyIndex} aria-hidden="true">
            <span>0{beat + 1}</span><i />
            <span>{["Your material", "A clearer path", "Learn with Lucent", "Go further"][beat]}</span>
          </div>

        </motion.div>{/* /cameraViewport */}
      </div>
    </main>
  )
}
