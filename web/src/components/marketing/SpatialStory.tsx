/**
 * SpatialStory.tsx
 *
 * Desktop (full motion):
 *   Mounts a @react-three/fiber <Canvas> that fills the 100svh sticky frame.
 *   HTML overlays (headline, CTAs, stage copy) are absolutely positioned above
 *   the canvas.  The interactive document card stack is also an HTML overlay
 *   on the right side, fading out when the camera enters the paper canyon.
 *
 * Mobile / prefers-reduced-motion:
 *   Renders the existing CSS card-stack layout (no WebGL canvas).
 *   All motion is handled by Framer Motion on DOM elements.
 */
import { lazy, Suspense, useEffect, useRef, useState } from "react"
import { Canvas } from "@react-three/fiber"
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
import { HeroScene } from "./HeroScene"
import styles from "./marketing.module.css"

const ProductDemo = lazy(() =>
  import("./LucentProductDemo").then(m => ({ default: m.LucentProductDemo }))
)

const LAYERS = ["Source material", "Simplify", "Explain", "Visualize", "Practice"]

// ─────────────────────────────────────────────────────────────────────────────
// useTimeline — clamped keyframe interpolation for Framer Motion MotionValues
// ─────────────────────────────────────────────────────────────────────────────
function useTimeline(
  progress: MotionValue<number>,
  points: number[],
  values: number[],
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
    ],
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// DocumentPage — one card in the interactive stack (static + canvas case)
// ─────────────────────────────────────────────────────────────────────────────
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
  const offset   = index - activeCard
  const active   = offset === 0
  const clickable =
    activeCard < LAYERS.length - 1 && (active || (!staticStory && offset === 1))

  return (
    <motion.div
      data-paper-layer={index}
      data-active={active}
      className={styles.documentPage}
      aria-hidden={!active && !clickable ? true : undefined}
      initial={false}
      animate={{
        x:       active ? 0 : offset < 0 ? -60 : offset * 38,
        y:       active ? 0 : offset < 0 ? 12  : -offset * 9,
        z:       active ? 100 : offset < 0 ? 160 : 100 - offset * 85,
        rotateY: active ? (staticStory ? 0 : -5) : offset < 0 ? -108 : -10,
        rotateX: active ? 0 : 3,
        rotateZ: active ? (staticStory ? 0 : -1) : -5 + offset,
        opacity: active || (!staticStory && offset > 0) ? 1 : 0,
      }}
      transition={{ duration: reduced ? 0 : 0.55, ease: [0.22, 0.68, 0.2, 1] }}
    >
      <div className={styles.pageTopline}>
        <span>{index ? "Lucent / " + LAYERS[index] : "Biology / Reading notes"}</span>
        <span>0{index + 1}</span>
      </div>
      <p className={styles.paperKicker}>
        {index ? LAYERS[index] : "Cellular quality control"}
      </p>
      <h2>
        {index === 0 ? (<>When a cell<br />finds damage.</>) :
         index === 1 ? (<>The essential<br />idea.</>) :
         index === 2 ? (<>Detection is<br />only the start.</>) :
         index === 3 ? (<>See the<br />connection.</>) :
                       (<>Put the idea<br />to work.</>)}
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
          <span>Damage detected</span><i>↓</i>
          <span>Signal sent</span><i>↓</i>
          <span>Response begins</span>
        </div>
      ) : (
        <>
          <p className={styles.paperDetail}>
            {index === 0
              ? "The response may repair or remove a faulty protein, preventing it from disrupting other processes."
              : index === 4
              ? "Look for the missing connection between noticing the damage and responding to it."
              : "Understanding the relationship matters more than remembering each label on its own."}
          </p>
          <div className={styles.paperLines}><i /><i /><i /><i /></div>
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
          aria-label={`Show ${LAYERS[activeCard + 1]} page`}
          onClick={onNext}
        />
      )}
    </motion.div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// DocumentCardStack — the right-side card stack overlay (Stages 1-2, canvas)
// ─────────────────────────────────────────────────────────────────────────────
function DocumentCardStack({ reduced }: { reduced: boolean }) {
  const [activeCard, setActiveCard] = useState(0)
  const tiltX      = useSpring(0, { stiffness: 160, damping: 25 })
  const tiltY      = useSpring(0, { stiffness: 160, damping: 25 })
  const gesture    = useRef<{ x: number; y: number } | null>(null)
  const suppress   = useRef(false)

  function turn(dir: number) {
    setActiveCard(c => Math.max(0, Math.min(LAYERS.length - 1, c + dir)))
  }

  return (
    <>
      <motion.div
        className={styles.documentStack}
        style={reduced ? undefined : { rotateX: tiltX, rotateY: tiltY }}
        onPointerMove={e => {
          if (reduced || e.pointerType !== "mouse") return
          const b = e.currentTarget.getBoundingClientRect()
          tiltX.set((0.5 - (e.clientY - b.top)  / b.height) * 5)
          tiltY.set(((e.clientX - b.left) / b.width - 0.5)   * 5)
        }}
        onPointerLeave={() => { tiltX.set(0); tiltY.set(0) }}
        onPointerDown={e => {
          suppress.current = false
          gesture.current  = e.pointerType === "touch" ? { x: e.clientX, y: e.clientY } : null
        }}
        onPointerCancel={() => { gesture.current = null }}
        onPointerUp={e => {
          const start = gesture.current; gesture.current = null
          if (!start) return
          const dx = e.clientX - start.x, dy = e.clientY - start.y
          if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            suppress.current = true; turn(dx < 0 ? 1 : -1)
          }
        }}
        onClickCapture={e => {
          if (suppress.current) { e.preventDefault(); e.stopPropagation(); suppress.current = false }
        }}
      >
        {[4, 3, 2, 1, 0].map(i => (
          <DocumentPage
            key={i} index={i} activeCard={activeCard}
            staticStory={false} reduced={reduced}
            onNext={() => turn(1)}
          />
        ))}
      </motion.div>

      <div className={styles.capabilityLabels} aria-hidden="true">
        <span style={{ transform: "translateZ(40px)" }}>Simplify</span>
        <span style={{ transform: "translateZ(20px)" }}>Explain</span>
        <span style={{ transform: "translateZ(60px)" }}>Visualize</span>
        <span style={{ transform: "translateZ(10px)" }}>Practice</span>
        <span style={{ transform: "translateZ(50px)" }}>Learn</span>
      </div>

      <div className={styles.pageControls} aria-label="Explore the source pages">
        <button type="button" aria-label="Previous source page"
          disabled={activeCard === 0} onClick={() => turn(-1)}>←</button>
        <span aria-live="polite">{activeCard + 1} / {LAYERS.length} · {LAYERS[activeCard]}</span>
        <button type="button" aria-label="Next source page"
          disabled={activeCard === LAYERS.length - 1} onClick={() => turn(1)}>→</button>
      </div>
    </>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// CanvasHero — desktop WebGL experience (mounted inside the sticky frame)
// ─────────────────────────────────────────────────────────────────────────────
function CanvasHero({ storyRef }: { storyRef: React.RefObject<HTMLElement | null> }) {
  const reduced   = useReducedMotion()
  const scrollRef = useRef<number>(0)
  const [beat, setBeat] = useState(0)

  const { scrollYProgress: p } = useScroll({
    target: storyRef as any,
    offset: ["start start", "end end"],
  })

  // Feed scroll progress into R3F's shared ref (read in useFrame — no re-renders)
  useMotionValueEvent(p, "change", v => {
    scrollRef.current = v
    setBeat(v < 0.46 ? 0 : v < 0.62 ? 1 : v < 0.88 ? 2 : 3)
  })

  // ── Overlay opacity values ────────────────────────────────────────────────
  const stage1Opacity   = useTimeline(p, [0, 0.38, 0.47],        [1, 1, 0])
  const cardStackOp     = useTimeline(p, [0, 0.38, 0.50],        [1, 1, 0])
  const stage2Opacity   = useTimeline(p, [0.40, 0.46, 0.56, 0.62],[0, 1, 1, 0])
  const stage4Opacity   = useTimeline(p, [0.88, 0.96],           [0, 1])
  const scrollCueOp     = useTimeline(p, [0, 0.10, 0.20],        [1, 1, 0])

  const STAGE_LABELS = ["Your material", "A clearer path", "Learn with Lucent", "Go further"]

  return (
    <>
      {/* ── WebGL Canvas ──────────────────────────────────────────────── */}
      <Canvas
        style={{ position: "absolute", inset: 0 }}
        camera={{ position: [0, 85, 200], fov: 65, near: 0.5, far: 2000 }}
        gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
        dpr={[1, 1.5]}
        shadows
      >
        <HeroScene scrollRef={scrollRef} />
      </Canvas>

      {/* ── HTML overlay — pointer-events:none; child elements opt-in ── */}
      <div className={styles.heroOverlay}>
        <a className={styles.skipLink} href="#learn-in-action">Skip to interactive preview</a>

        {/* Stage 1: hero copy (left) */}
        <motion.div
          className={`${styles.storyCopy} ${styles.heroStoryCopy}`}
          aria-hidden={beat !== 0}
          style={{ opacity: stage1Opacity }}
        >
          <p className={styles.eyebrowLight}>Read. Understand. Go further.</p>
          <h1 className={styles.storyHeadline}>
            Turn any<br />material into<br /><em>understanding.</em>
          </h1>
          <p className={styles.storyBody}>
            Your documents, opened up.<br />
            Clear explanations, interactive visuals,<br />
            and a tutor that helps the idea click.
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

        {/* Stage 1: card stack overlay (right) */}
        <motion.div
          className={styles.documentScene}
          aria-hidden={beat !== 0}
          style={{ opacity: cardStackOp, pointerEvents: beat === 0 ? "auto" : "none" }}
        >
          <DocumentCardStack reduced={reduced} />
          <p className={styles.paperCaption} aria-hidden="true">
            From pages<br />to progress.
          </p>
        </motion.div>

        {/* Stage 2: clarity copy */}
        <motion.div
          className={`${styles.storyCopy} ${styles.clarityCopy}`}
          aria-hidden={beat !== 1}
          style={{ opacity: stage2Opacity }}
        >
          <p className={styles.eyebrowLight}>A calmer way to learn</p>
          <h2 className={styles.storyHeading}>
            Same material.<br /><em>A clearer path.</em>
          </h2>
          <p className={styles.storyBody}>
            Read it. See it. Try it.<br />
            Keep the explanation beside the question,<br />
            so understanding has room to grow.
          </p>
        </motion.div>

        {/* Stage 3: anchor for keyboard navigation (demo is inside Canvas portal) */}
        <div
          id="learn-in-action"
          className={styles.demoAnchor}
          tabIndex={-1}
          aria-label="Interactive Lucent preview — embedded in 3D scene"
        />

        {/* Stage 4: resolution copy */}
        <motion.section
          className={styles.resolutionCopy}
          aria-hidden={beat !== 3}
          aria-label="Go further with Lucent"
          style={{ opacity: stage4Opacity }}
        >
          <p className={styles.eyebrowLight}>Go further</p>
          <h2>A little further<br />from the familiar.</h2>
          <p>Bring your material.<br />Leave with a new way of seeing it.</p>
          <Link to="/signup" className={styles.btnLight}>
            Begin with your material <span aria-hidden="true">↗</span>
          </Link>
        </motion.section>

        {/* Chrome */}
        <motion.div
          className={styles.scrollCue}
          aria-hidden="true"
          style={{ opacity: scrollCueOp }}
        >
          <span /> Scroll to explore
        </motion.div>

        <div className={styles.storyIndex} aria-hidden="true">
          <span>0{beat + 1}</span><i />
          <span>{STAGE_LABELS[beat]}</span>
        </div>
      </div>
    </>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// StaticSpatialStory — CSS card-stack fallback (mobile / reduced-motion)
// Full DOM-based layout, no WebGL canvas.
// ─────────────────────────────────────────────────────────────────────────────
function StaticSpatialStory() {
  const [activeCard, setActiveCard] = useState(0)
  const [loadDemo,   setLoadDemo  ] = useState(false)
  const tiltX    = useSpring(0, { stiffness: 160, damping: 25 })
  const tiltY    = useSpring(0, { stiffness: 160, damping: 25 })
  const gesture  = useRef<{ x: number; y: number } | null>(null)
  const suppress = useRef(false)

  useEffect(() => {
    if (window.location.hash !== "#learn-in-action") return
    const id = requestAnimationFrame(() =>
      document.getElementById("learn-in-action")?.scrollIntoView({ behavior: "instant", block: "start" })
    )
    return () => cancelAnimationFrame(id)
  }, [])

  function turn(dir: number) {
    setActiveCard(c => Math.max(0, Math.min(LAYERS.length - 1, c + dir)))
  }

  return (
    <div className={styles.storySticky} data-static-story="true">
      <a className={styles.skipLink} href="#learn-in-action">Skip to interactive preview</a>
      <div id="learn-in-action" className={styles.demoAnchor} tabIndex={-1} />

      {/* Stage 1: hero copy */}
      <div className={`${styles.storyCopy} ${styles.heroStoryCopy}`}>
        <p className={styles.eyebrowLight}>Read. Understand. Go further.</p>
        <h1 className={styles.storyHeadline}>
          Turn any<br />material into<br /><em>understanding.</em>
        </h1>
        <p className={styles.storyBody}>
          Your documents, opened up.<br />
          Clear explanations, interactive visuals,<br />
          and a tutor that helps the idea click.
        </p>
        <div className={styles.heroActions}>
          <Link to="/signup" className={styles.btnLight}>
            Get started <span aria-hidden="true">↗</span>
          </Link>
          <a href="#learn-in-action" className={styles.watchLink}>
            <span aria-hidden="true">▷</span> Explore Lucent
          </a>
        </div>
      </div>

      {/* Card stack */}
      <div className={styles.documentScene}>
        <motion.div
          className={styles.documentStack}
          onPointerDown={e => {
            suppress.current = false
            gesture.current  = e.pointerType === "touch" ? { x: e.clientX, y: e.clientY } : null
          }}
          onPointerCancel={() => { gesture.current = null }}
          onPointerUp={e => {
            const s = gesture.current; gesture.current = null
            if (!s) return
            const dx = e.clientX - s.x, dy = e.clientY - s.y
            if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
              suppress.current = true; turn(dx < 0 ? 1 : -1)
            }
          }}
          onClickCapture={e => {
            if (suppress.current) { e.preventDefault(); e.stopPropagation(); suppress.current = false }
          }}
        >
          {[4, 3, 2, 1, 0].map(i => (
            <DocumentPage
              key={i} index={i} activeCard={activeCard}
              staticStory reduced={false}
              onNext={() => turn(1)}
            />
          ))}
        </motion.div>

        <div className={styles.capabilityLabels} aria-hidden="true">
          <span>Simplify</span><span>Explain</span>
          <span>Visualize</span><span>Practice</span><span>Learn</span>
        </div>
      </div>

      <div className={styles.pageControls} aria-label="Explore the source pages">
        <button type="button" aria-label="Previous source page"
          disabled={activeCard === 0} onClick={() => turn(-1)}>←</button>
        <span aria-live="polite">{activeCard + 1} / {LAYERS.length} · {LAYERS[activeCard]}</span>
        <button type="button" aria-label="Next source page"
          disabled={activeCard === LAYERS.length - 1} onClick={() => turn(1)}>→</button>
      </div>

      {/* Stage 2: clarity copy */}
      <div className={`${styles.storyCopy} ${styles.clarityCopy}`}>
        <p className={styles.eyebrowLight}>A calmer way to learn</p>
        <h2 className={styles.storyHeading}>
          Same material.<br /><em>A clearer path.</em>
        </h2>
        <p className={styles.storyBody}>
          Read it. See it. Try it.<br />
          Keep the explanation beside the question,<br />
          so understanding has room to grow.
        </p>
      </div>

      {/* Stage 3: interactive product demo */}
      <section
        className={styles.productStage}
        aria-label="Interactive Lucent preview"
        onFocus={() => setLoadDemo(true)}
        onPointerEnter={() => setLoadDemo(true)}
      >
        <div className={styles.productStageIntro}>
          <div>
            <p className={styles.eyebrowLight}>See Lucent in action</p>
            <h2>From reading <em>to reasoning.</em></h2>
          </div>
          <p>
            Try an answer. Ask for another explanation.<br />
            See what happens when the idea clicks.
          </p>
        </div>
        {loadDemo ? (
          <Suspense fallback={<div className={styles.demoLoading} role="status">Opening the learning preview…</div>}>
            <ProductDemo />
          </Suspense>
        ) : (
          <button
            type="button"
            className={styles.btnLight}
            onClick={() => setLoadDemo(true)}
          >
            Open interactive preview
          </button>
        )}
      </section>

      {/* Stage 4: resolution */}
      <section className={styles.resolutionCopy} aria-label="Go further with Lucent">
        <p className={styles.eyebrowLight}>Go further</p>
        <h2>A little further<br />from the familiar.</h2>
        <p>Bring your material.<br />Leave with a new way of seeing it.</p>
        <Link to="/signup" className={styles.btnLight}>
          Begin with your material <span aria-hidden="true">↗</span>
        </Link>
      </section>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// SpatialStory — public export
// ─────────────────────────────────────────────────────────────────────────────
export function SpatialStory() {
  const reduced = useReducedMotion()
  const [compact, setCompact] = useState(
    () => window.matchMedia("(max-width: 950px), (max-height: 620px)").matches
  )

  useEffect(() => {
    const q   = window.matchMedia("(max-width: 950px), (max-height: 620px)")
    const upd = () => setCompact(q.matches)
    q.addEventListener("change", upd)
    return () => q.removeEventListener("change", upd)
  }, [])

  const staticStory = reduced || compact

  // Ref to the <main> scroll container — passed to both the Canvas overlay
  // AND used as the useScroll target inside CanvasHero.
  const mainRef = useRef<HTMLElement | null>(null)

  if (staticStory) {
    return (
      <main
        className={styles.spatialStory}
        data-static-story="true"
        aria-label="From source material to understanding"
      >
        <StaticSpatialStory />
      </main>
    )
  }

  return (
    <main
      ref={mainRef}
      className={styles.spatialStory}
      data-static-story="false"
      aria-label="From source material to understanding"
    >
      {/* 100svh sticky frame — Canvas + overlays live here */}
      <div className={styles.storySticky}>
        <CanvasHero storyRef={mainRef} />
      </div>
    </main>
  )
}
