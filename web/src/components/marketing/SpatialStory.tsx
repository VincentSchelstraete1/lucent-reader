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

function DocumentPage({ index, progress }: { index: number; progress: MotionValue<number> }) {
  const x = useTimeline(progress, [0, .12, .32, .49, .61], [index * 28, index * 28, (index - 2) * 87, index === 3 ? -30 : (index - 2) * 52, 0])
  const y = useTimeline(progress, [0, .12, .32, .49, .61], [-index * 10, -index * 10, (index - 2) * -22, (index - 2) * -10, 0])
  const z = useTimeline(progress, [0, .12, .32, .49, .61], [100 - index * 48, 100 - index * 48, 180 - index * 90, index === 3 ? 130 : -60 - index * 35, 0])
  const rotateY = useTimeline(progress, [0, .32, .49, .61], [-23, -34 + index * 3, -14, 0])
  const rotateZ = useTimeline(progress, [0, .32, .61], [-7 + index * 1.1, -8 + index * 2, 0])
  const opacity = useTimeline(progress, [.50, .55, .58], [1, index === 3 ? 1 : 0, 0])
  return <motion.div data-paper-layer={index} className={styles.documentPage} style={{ x, y, z, rotateY, rotateZ, opacity }}>
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
    setBeat(value < .19 ? 0 : value < .39 ? 1 : value < .59 ? 2 : value < .89 ? 3 : 4)
    if (value > .40) setLoadDemo(true)
  })
  const heroOpacity = useTimeline(p, [0, .12, .19], [1, 1, 0])
  const transformOpacity = useTimeline(p, [.19, .24, .34, .39], [0, 1, 1, 0])
  const clarityOpacity = useTimeline(p, [.39, .44, .53, .59], [0, 1, 1, 0])
  const documentX = useTimeline(p, [0, .34, .49, .65], [0, 0, 40, -220])
  const documentScale = useTimeline(p, [0, .36, .50, .65], [1, .78, .85, 1.25])
  const documentOpacity = useTimeline(p, [.54, .58], [1, 0])
  const productOpacity = useTimeline(p, [.54, .575, .85, .92], [0, 1, 1, 0])
  const productScale = useTimeline(p, [.54, .68, .85, .95], [.38, 1, 1, .78])
  const productRotateY = useTimeline(p, [.54, .68, .85, .95], [-18, 0, 0, 8])
  const productX = useTimeline(p, [.54, .68, .85, .95], [180, 0, 0, -70])
  const productY = useTimeline(p, [.54, .68, .85, .95], [0, 0, 0, -90])
  const endingOpacity = useTimeline(p, [.89, .96], [0, 1])
  const landscapeScale = useTimeline(p, [0, .55, 1], [1.02, 1.10, 1.02])
  const landscapeY = useTimeline(p, [0, 1], [0, -24])
  const foregroundY = useTimeline(p, [0, .65, 1], [0, 100, 10])
  const foregroundScale = useTimeline(p, [0, .65, 1], [1.02, 1.20, 1.04])
  const veilOpacity = useTimeline(p, [0, .5, .65, .85, 1], [0, 0, .88, .88, 0])
  const scrollCueOpacity = useTimeline(p, [0, .1, .2], [1, 1, 0])
  const accessible = (active: boolean) => ({ "aria-hidden": !staticStory && !active ? true : undefined, ...(!staticStory && !active ? { inert: "" } : {}) })

  return <main ref={ref} className={styles.spatialStory} data-static-story={staticStory} aria-label="From source material to understanding">
    <a className={styles.skipLink} href="#learn-in-action">Skip to interactive preview</a>
    {!staticStory && <div id="learn-in-action" className={styles.demoAnchor} tabIndex={-1} />}
    <div className={styles.storySticky}>
      <div className={styles.environment} aria-hidden="true">
        <motion.img className={styles.landscape} src="/lucent-landscape.jpg" width="1672" height="941" fetchPriority="high" alt="" style={staticStory ? undefined : { scale: landscapeScale, y: landscapeY }} />
        <div className={styles.landscapeShade}/>
        <motion.div className={styles.foreground} style={staticStory ? undefined : { scale: foregroundScale, y: foregroundY }} />
        <motion.div className={styles.productVeil} style={staticStory ? undefined : { opacity: veilOpacity }} />
      </div>

      <motion.div className={`${styles.storyCopy} ${styles.heroStoryCopy}`} {...accessible(beat === 0)} style={staticStory ? undefined : { opacity: heroOpacity }}>
        <p className={styles.eyebrowLight}>Read. Understand. Go further.</p>
        <h1 className={styles.storyHeadline}>Turn any<br/>material into<br/><em>understanding.</em></h1>
        <p className={styles.storyBody}>Your documents, opened up.<br/>Clear explanations, interactive visuals, and a tutor that helps the idea click.</p>
        <div className={styles.heroActions}><Link to="/signup" className={styles.btnLight}>Get started <span aria-hidden="true">↗</span></Link><a href="#learn-in-action" className={styles.watchLink}><span aria-hidden="true">▷</span> Explore Lucent</a></div>
      </motion.div>

      <motion.div className={styles.documentScene} style={staticStory ? undefined : { x: documentX, scale: documentScale, opacity: documentOpacity }} aria-hidden="true">
        <div className={styles.documentStack}>{[4,3,2,1,0].map(index => <DocumentPage key={index} index={index} progress={p}/>)}</div>
        <div className={styles.capabilityLabels}><span>Simplify</span><span>Explain</span><span>Visualize</span><span>Practice</span><span>Learn</span></div>
        <p className={styles.paperCaption}>From pages<br/>to progress.</p>
      </motion.div>

      <motion.div className={`${styles.storyCopy} ${styles.transformCopy}`} {...accessible(beat === 1)} style={staticStory ? undefined : { opacity: transformOpacity }}>
        <p className={styles.eyebrowLight}>One source. More ways in.</p>
        <h2 className={styles.storyHeading}>Let the idea<br/><em>open up.</em></h2>
        <p className={styles.storyBody}>Unpack a difficult passage. Find a simpler explanation. See how the pieces connect.</p>
      </motion.div>

      <motion.div className={`${styles.storyCopy} ${styles.clarityCopy}`} {...accessible(beat === 2)} style={staticStory ? undefined : { opacity: clarityOpacity }}>
        <p className={styles.eyebrowLight}>A calmer way to learn</p>
        <h2 className={styles.storyHeading}>Same material.<br/><em>A clearer path.</em></h2>
        <p className={styles.storyBody}>Read it. See it. Try it.<br/>Keep the explanation beside the question, so understanding has room to grow.</p>
      </motion.div>

      <motion.section id={staticStory ? "learn-in-action" : undefined} tabIndex={-1} className={styles.productStage} {...accessible(beat === 3)} aria-label="Interactive Lucent preview" style={staticStory ? undefined : { opacity: productOpacity, scale: productScale, rotateY: productRotateY, x: productX, y: productY }}>
        <div className={styles.productStageIntro}><div><p className={styles.eyebrowLight}>See Lucent in action</p><h2>From reading <em>to reasoning.</em></h2></div><p>Try an answer. Ask for another explanation.<br/>See what happens when the idea clicks.</p></div>
        {(loadDemo || staticStory) && <Suspense fallback={<div className={styles.demoLoading} role="status">Opening the learning preview…</div>}><ProductDemo /></Suspense>}
      </motion.section>

      <motion.section className={styles.resolutionCopy} {...accessible(beat === 4)} aria-label="Go further with Lucent" style={staticStory ? undefined : { opacity: endingOpacity }}>
        <p className={styles.eyebrowLight}>Go further</p>
        <h2>A little further<br/>from the familiar.</h2>
        <p>Bring your material.<br/>Leave with a new way of seeing it.</p>
        <Link to="/signup" className={styles.btnLight}>Begin with your material <span aria-hidden="true">↗</span></Link>
      </motion.section>
      <motion.div className={styles.scrollCue} aria-hidden="true" style={staticStory ? undefined : { opacity: scrollCueOpacity }}><span/> Scroll to explore</motion.div>
      <div className={styles.storyIndex} aria-hidden="true"><span>0{beat + 1}</span><i/><span>{["Your material", "More ways in", "A clearer path", "Learn with Lucent", "Go further"][beat]}</span></div>
    </div>
  </main>
}
