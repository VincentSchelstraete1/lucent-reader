import { useEffect, useRef } from "react"
import { motion, useAnimation, useMotionValue, useSpring, useTransform } from "framer-motion"
import { useReducedMotion } from "../../lib/useReducedMotion"
import styles from "./marketing.module.css"

const IDLE_KEYFRAMES = {
  y: [0, -2, 1, -3, 0],
  rotate: [0, -1.4, 0.8, -1, 0],
  scale: [1, 1.007, 0.996, 1.005, 1]
}

const CLICK_SEQUENCE = {
  scale: [1, 0.94, 1.04, 1],
  rotate: [0, 0, -2, 0]
}

// Today: a static image + framer-motion. Later: this can be swapped for a
// React Three Fiber / React Bits Model Viewer scene rendering a real GLB
// without the surrounding Hero/LandingPage needing to change - nothing
// outside this file knows or cares how the flower is actually rendered.
export function FlowerHero() {
  const reduced = useReducedMotion()
  const controls = useAnimation()
  const wrapperRef = useRef<HTMLDivElement>(null)

  const pointerX = useMotionValue(0)
  const pointerY = useMotionValue(0)
  const springX = useSpring(pointerX, { stiffness: 40, damping: 14, mass: 0.6 })
  const springY = useSpring(pointerY, { stiffness: 40, damping: 14, mass: 0.6 })
  const rotateY = useTransform(springX, [-1, 1], [-5, 5])
  const rotateX = useTransform(springY, [-1, 1], [4, -4])
  const translateX = useTransform(springX, [-1, 1], [-8, 8])

  useEffect(() => {
    if (reduced) return
    controls.start({
      ...IDLE_KEYFRAMES,
      transition: { duration: 13, repeat: Infinity, ease: "easeInOut" }
    })
  }, [reduced, controls])

  function handlePointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (reduced) return
    const rect = wrapperRef.current?.getBoundingClientRect()
    if (!rect) return
    const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1
    const ny = ((e.clientY - rect.top) / rect.height) * 2 - 1
    pointerX.set(Math.max(-1, Math.min(1, nx)))
    pointerY.set(Math.max(-1, Math.min(1, ny)))
  }

  function handlePointerLeave() {
    pointerX.set(0)
    pointerY.set(0)
  }

  async function handleClick() {
    if (reduced) return
    controls.stop()
    await controls.start({ ...CLICK_SEQUENCE, transition: { duration: 0.55, ease: "easeOut" } })
    controls.start({
      ...IDLE_KEYFRAMES,
      transition: { duration: 13, repeat: Infinity, ease: "easeInOut" }
    })
  }

  return (
    <motion.div
      ref={wrapperRef}
      className={styles.flowerHero}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      onClick={handleClick}
      style={reduced ? undefined : { rotateX, rotateY, x: translateX, perspective: 800 }}
      whileHover={reduced ? undefined : { scale: 1.02 }}
      role="img"
      aria-label="A gently animated botanical flower, the Lucent emblem"
    >
      <motion.img
        src="/flowers/hero-flower.webp"
        alt=""
        className={styles.flowerHeroImg}
        animate={reduced ? undefined : controls}
        initial={false}
      />
    </motion.div>
  )
}
