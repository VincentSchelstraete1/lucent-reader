import { useRef } from "react"
import { Link } from "react-router-dom"
import { motion, useScroll, useTransform } from "framer-motion"
import styles from "./marketing.module.css"
import { useReducedMotion } from "../../lib/useReducedMotion"

// The flower itself lives in the page-level <ScrollFlower> layer, not here -
// this section only owns the headline/copy/CTAs and their own scroll fade.
export function Hero() {
  const sectionRef = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start start", "end start"]
  })

  const copyOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0])
  const copyY = useTransform(scrollYProgress, [0, 0.8], [0, -40])

  return (
    <section ref={sectionRef} className={styles.hero}>
      <motion.div
        className={styles.heroCopy}
        style={reduced ? undefined : { opacity: copyOpacity, y: copyY }}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
      >
        <p className={styles.eyebrow}>Your learning companion</p>
        <h1 className={styles.headline}>
          Understand anything
          <br />
          <span className={styles.headlineDisplay}>your way.</span>
        </h1>
        <p className={styles.subhead}>
          Read, clarify, and save difficult ideas without leaving the page you’re on.
        </p>
        <div className={styles.heroActions}>
          <Link to="/signup" className={styles.btnPrimary}>
            Get started
          </Link>
          <a href="#demo" className={styles.seeHow}>
            See it in action
          </a>
        </div>
      </motion.div>
    </section>
  )
}
