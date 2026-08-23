import { useRef } from "react"
import { Link } from "react-router-dom"
import { motion, useScroll, useTransform } from "framer-motion"
import { FlowerHero } from "./FlowerHero"
import styles from "./marketing.module.css"
import { useReducedMotion } from "../../lib/useReducedMotion"

export function Hero() {
  const sectionRef = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start start", "end start"]
  })

  const copyOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0])
  const copyY = useTransform(scrollYProgress, [0, 0.8], [0, -40])
  const flowerY = useTransform(scrollYProgress, [0, 1], [0, -110])
  const flowerRotate = useTransform(scrollYProgress, [0, 1], [0, 4])
  const flowerOpacity = useTransform(scrollYProgress, [0, 0.9], [1, 0.35])

  return (
    <section ref={sectionRef} className={styles.hero}>
      <motion.div
        className={styles.heroCopy}
        style={reduced ? undefined : { opacity: copyOpacity, y: copyY }}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
      >
        <h1 className={styles.headline}>
          Understand anything
          <br />
          <span className={styles.headlineDisplay}>your way.</span>
        </h1>
        <p className={styles.subhead}>Lucent adapts to how you learn and helps you truly understand.</p>
        <div className={styles.heroActions}>
          <Link to="/signup" className={styles.btnPrimary}>
            Get started →
          </Link>
          <a href="#features" className={styles.seeHow}>
            See how it works
          </a>
        </div>
      </motion.div>

      <motion.div
        className={styles.flowerStage}
        style={reduced ? undefined : { y: flowerY, rotate: flowerRotate, opacity: flowerOpacity }}
      >
        <FlowerHero />
      </motion.div>
    </section>
  )
}
