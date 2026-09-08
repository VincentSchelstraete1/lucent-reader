import { lazy, Suspense, useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { motion, useMotionValueEvent, useScroll, useTransform, type MotionValue } from "framer-motion"
import { useReducedMotion } from "../../lib/useReducedMotion"
import styles from "./marketing.module.css"

const ProductDemo = lazy(() => import("./LucentProductDemo").then(module => ({ default: module.LucentProductDemo })))
const layers = ["Source material", "Simplify", "Explain", "Visualize", "Practice"]

// Include both scroll endpoints. Native scroll timelines otherwise interpolate
// back to the underlying style after the final authored keyframe.
function useTimeline(progress: MotionValue<number>, points: number[], values: number[]) {
  return useTransform(progress,
    [...(points[0] > 0 ? [0] : []), ...points, ...(points[points.length - 1] < 1 ? [1] : [])],
    [...(points[0] > 0 ? [values[0]] : []), ...values, ...(points[points.length - 1] < 1 ? [values[values.length - 1]] : [])])
}

function DocumentPage({ index, progress, staticStory, active }: { index: number; progress: MotionValue<number>; staticStory: boolean; active: boolean }) {
  const start = index * .07
  const last = index === layers.length - 1
  const points = index === 0 ? [0, .05, .07] : [0, start - .022, start, start + .05, start + .07]
  const values = (back: number, front: number, turned: number) => index === 0 ? [front, front, turned] : [back, back, front, front, last ? front : turned]
  const x = useTimeline(progress, points, values(index * 38, 0, -60))
  const y = useTimeline(progress, points, values(-index * 9, 0, 12))
  const z = useTimeline(progress, points, values(100 - index * 85, 100, 160))
  const rotateY = useTimeline(progress, points, values(-10, -5, -108))
  const rotateX = useTimeline(progress, points, values(3, 0, 4))
  const rotateZ = useTimeline(progress, points, values(-5 + index, -1, -6))
  const opacity = useTimeline(progress, points, values(1, 1, 0))
  return <motion.div data-paper-layer={index} data-active={active} className={styles.documentPage} style={staticStory ? undefined : { x, y, z, rotateX, rotateY, rotateZ, opacity }}>
    <div className={styles.pageTopline}><span>{index ? "Lucent / " + layers[index] : "Biology / Reading notes"}</span><span>0{index + 1}</span></div>
    <p className={styles.paperKicker}>{index ? layers[index] : "Cellular quality control"}</p>
    <h2>{index === 0 ? <>When a cell<br/>finds damage.</> : index === 1 ? <>The essential<br/>idea.</> : index === 2 ? <>Detection is<br/>only the start.</> : index === 3 ? <>See the<br/>connection.</> : <>Put the idea<br/>to work.</>}</h2>
    <p>{index === 0 ? "Cells continually monitor their proteins. When a protein loses its working shape, a control signal coordinates the response." : index === 1 ? "Finding damage is not the same as fixing it. A signal connects what the cell detects to what it does next." : index === 2 ? "Think of a smoke alarm: it detects a problem and calls for action. It does not put out the fire itself." : index === 3 ? "Follow the signal from detection to a protective response." : "A cell detects damage, but its signal is blocked. Would detection alone protect the cell?"}</p>
    <div className={styles.paperRule}/>
    {index === 3 ? <div className={styles.paperFlow}><span>Damage detected</span><i>↓</i><span>Signal sent</span><i>↓</i><span>Response begins</span></div> : <>
      <p className={styles.paperDetail}>{index === 0 ? "The response may repair or remove a faulty protein, preventing it from disrupting other processes. Detection, signalling, and response each play a different part in protecting the cell." : index === 4 ? "Look for the missing connection between noticing the damage and responding to it." : "Understanding the relationship matters more than remembering each label on its own."}</p>
      <div className={styles.paperLines}><i/><i/><i/><i/></div>
      <div className={styles.paperNote}>{index === 0 ? "01 — Detect. Signal. Respond." : index === 4 ? "Reason from what you know." : "Same source. A clearer explanation."}</div>
    </>}
  </motion.div>
}

export function SpatialStory() {
  const ref = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const [compact, setCompact] = useState(() => window.matchMedia("(max-width: 950px), (max-height: 620px)").matches)
  const [beat, setBeat] = useState(0)
  const [loadDemo, setLoadDemo] = useState(false)
  const [scrollCard, setScrollCard] = useState(0)
  const [manualCard, setManualCard] = useState(0)
  const { scrollYProgress: p } = useScroll({ target: ref, offset: ["start start", "end end"] })
  useEffect(() => {
    const query = window.matchMedia("(max-width: 950px), (max-height: 620px)")
    const update = () => setCompact(query.matches)
    query.addEventListener("change", update)
    return () => query.removeEventListener("change", update)
  }, [])
  const staticStory = reduced || compact
  useEffect(() => {
    // The landing route mounts after the browser's initial fragment lookup.
    // Resolve the public preview deep link once its target is in the DOM.
    if (window.location.hash !== "#learn-in-action") return
    const frame = requestAnimationFrame(() => {
      document.getElementById("learn-in-action")?.scrollIntoView({ behavior: "instant", block: "start" })
    })
    return () => cancelAnimationFrame(frame)
  }, [])
  useMotionValueEvent(p, "change", value => {
    setBeat(value < .42 ? 0 : value < .62 ? 1 : value < .89 ? 2 : 3)
    setScrollCard(Math.min(4, Math.floor((value + .004) / .07)))
    if (value > .40) setLoadDemo(true)
  })
  const heroOpacity = useTimeline(p, [0, .32, .41], [1, 1, 0])
  const clarityOpacity = useTimeline(p, [.42, .46, .56, .62], [0, 1, 1, 0])
  const documentX = useTimeline(p, [0, .33, .43], [0, 0, 100])
  const documentY = useTimeline(p, [0, .33, .43], [0, 0, 180])
  const documentScale = useTimeline(p, [0, .33, .43], [1, 1, .65])
  const documentOpacity = useTimeline(p, [.34, .42], [1, 0])
  // Leave a full landscape-only interval before the separate demo entrance.
  const productOpacity = useTimeline(p, [.62, .70], [0, 1])
  const productScale = useTimeline(p, [.60, .70, .85, 1], [.92, 1, 1, .55])
  const productZ = useTimeline(p, [.60, .70, .85, 1], [-100, 0, 0, -500])
  const productRotateY = useTimeline(p, [.60, .70, .85, 1], [-8, 0, 0, -26])
  const productX = useTimeline(p, [.60, .70, .85, 1], [40, 0, 0, 450])
  const productY = useTimeline(p, [.60, .70, .85, 1], [40, 0, 0, 30])
  const endingOpacity = useTimeline(p, [.94, 1], [0, 1])
  // A continuous forward/right camera drift, never a backdrop reset at the demo.
  const landscapeScale = useTimeline(p, [0, .32, .46, 1], [1.04, 1.08, 1.34, 1.40])
  const landscapeY = useTimeline(p, [0, .32, .46, 1], [0, -8, -100, -120])
  const landscapeX = useTimeline(p, [0, .32, .46, 1], [0, -10, -110, -140])
  const foregroundY = useTimeline(p, [0, .32, .46, 1], [0, 20, 210, 240])
  const foregroundScale = useTimeline(p, [0, .32, .46, 1], [1.04, 1.12, 1.65, 1.75])
  const fogFarX = useTimeline(p, [0, 1], [-100, 160])
  const fogNearX = useTimeline(p, [0, .5, 1], [100, -90, -280])
  const fogNearY = useTimeline(p, [0, .32, .40, .48, 1], [0, -10, -160, -50, -90])
  const fogNearOpacity = useTimeline(p, [0, .32, .40, .48, .70, .85, 1], [.8, .8, 1, .4, .14, .14, .48])
  const fogBetweenX = useTimeline(p, [0, .5, 1], [-80, 80, 140])
  const scrollCueOpacity = useTimeline(p, [0, .1, .2], [1, 1, 0])
  const accessible = (active: boolean) => ({ "aria-hidden": !staticStory && !active ? true : undefined, ...(!staticStory && !active ? { inert: "" } : {}) })
  const activeCard = staticStory ? manualCard : scrollCard
  function turnPage(direction: number) {
    const next = Math.max(0, Math.min(layers.length - 1, activeCard + direction))
    if (staticStory) setManualCard(next)
    else if (ref.current) window.scrollTo({ top: ref.current.offsetTop + (ref.current.offsetHeight - window.innerHeight) * (next * .07 + .015), behavior: "smooth" })
  }

  return <main ref={ref} className={styles.spatialStory} data-static-story={staticStory} aria-label="From source material to understanding">
    <a className={styles.skipLink} href="#learn-in-action">Skip to interactive preview</a>
    {!staticStory && <div id="learn-in-action" className={styles.demoAnchor} tabIndex={-1} />}
    <div className={styles.storySticky}>
      <div className={styles.environment} aria-hidden="true">
        <motion.img className={styles.landscape} src="/lucent-landscape.jpg" width="1672" height="941" fetchPriority="high" alt="" style={staticStory ? undefined : { scale: landscapeScale, x: landscapeX, y: landscapeY }} />
        <div className={styles.landscapeShade}/>
        <motion.div className={styles.foreground} style={staticStory ? undefined : { scale: foregroundScale, y: foregroundY }} />
        <motion.div className={`${styles.fog} ${styles.fogFar}`} style={staticStory ? undefined : { x: fogFarX }} />
      </div>

      <motion.div className={`${styles.storyCopy} ${styles.heroStoryCopy}`} {...accessible(beat === 0)} style={staticStory ? undefined : { opacity: heroOpacity }}>
        <p className={styles.eyebrowLight}>Read. Understand. Go further.</p>
        <h1 className={styles.storyHeadline}>Turn any<br/>material into<br/><em>understanding.</em></h1>
        <p className={styles.storyBody}>Your documents, opened up.<br/>Clear explanations, interactive visuals, and a tutor that helps the idea click.</p>
        <div className={styles.heroActions}><Link to="/signup" className={styles.btnLight}>Get started <span aria-hidden="true">↗</span></Link><a href="#learn-in-action" className={styles.watchLink}><span aria-hidden="true">▷</span> Explore Lucent</a></div>
      </motion.div>

      <motion.div className={styles.documentScene} style={staticStory ? undefined : { x: documentX, y: documentY, scale: documentScale, opacity: documentOpacity }} aria-hidden="true">
        <div className={styles.documentStack}>
          {[4,3,2,1,0].map(index => <DocumentPage key={index} index={index} progress={p} staticStory={staticStory} active={index === activeCard}/>)}
          <motion.div className={`${styles.fog} ${styles.fogBetween}`} style={{ x: fogBetweenX, z: -400 }} />
        </div>
        <div className={styles.capabilityLabels}><span>Simplify</span><span>Explain</span><span>Visualize</span><span>Practice</span><span>Learn</span></div>
        <p className={styles.paperCaption}>From pages<br/>to progress.</p>
      </motion.div>

      <motion.div className={styles.pageControls} {...accessible(beat === 0)} style={staticStory ? undefined : { opacity: heroOpacity }} aria-label="Explore the source pages">
        <button type="button" aria-label="Previous source page" disabled={activeCard === 0} onClick={() => turnPage(-1)}>←</button>
        <span aria-live="polite">{activeCard + 1} / {layers.length} · {layers[activeCard]}</span>
        <button type="button" aria-label="Next source page" disabled={activeCard === layers.length - 1} onClick={() => turnPage(1)}>→</button>
      </motion.div>

      <motion.div className={`${styles.storyCopy} ${styles.clarityCopy}`} {...accessible(beat === 1)} style={staticStory ? undefined : { opacity: clarityOpacity }}>
        <p className={styles.eyebrowLight}>A calmer way to learn</p>
        <h2 className={styles.storyHeading}>Same material.<br/><em>A clearer path.</em></h2>
        <p className={styles.storyBody}>Read it. See it. Try it.<br/>Keep the explanation beside the question, so understanding has room to grow.</p>
      </motion.div>

      <motion.section id={staticStory ? "learn-in-action" : undefined} tabIndex={-1} className={styles.productStage} {...accessible(beat === 2)} aria-label="Interactive Lucent preview" style={staticStory ? undefined : { opacity: productOpacity, scale: productScale, rotateY: productRotateY, x: productX, y: productY, z: productZ }}>
        <div className={styles.productStageIntro}><div><p className={styles.eyebrowLight}>See Lucent in action</p><h2>From reading <em>to reasoning.</em></h2></div><p>Try an answer. Ask for another explanation.<br/>See what happens when the idea clicks.</p></div>
        {(loadDemo || staticStory) && <Suspense fallback={<div className={styles.demoLoading} role="status">Opening the learning preview…</div>}><ProductDemo /></Suspense>}
      </motion.section>

      <motion.div className={`${styles.fog} ${styles.fogNear}`} aria-hidden="true" style={staticStory ? undefined : { x: fogNearX, y: fogNearY, opacity: fogNearOpacity }} />

      <motion.section className={styles.resolutionCopy} {...accessible(beat === 3)} aria-label="Go further with Lucent" style={staticStory ? undefined : { opacity: endingOpacity }}>
        <p className={styles.eyebrowLight}>Go further</p>
        <h2>A little further<br/>from the familiar.</h2>
        <p>Bring your material.<br/>Leave with a new way of seeing it.</p>
        <Link to="/signup" className={styles.btnLight}>Begin with your material <span aria-hidden="true">↗</span></Link>
      </motion.section>
      <motion.div className={styles.scrollCue} aria-hidden="true" style={staticStory ? undefined : { opacity: scrollCueOpacity }}><span/> Scroll to explore</motion.div>
      <div className={styles.storyIndex} aria-hidden="true"><span>0{beat + 1}</span><i/><span>{["Your material", "A clearer path", "Learn with Lucent", "Go further"][beat]}</span></div>
    </div>
  </main>
}
