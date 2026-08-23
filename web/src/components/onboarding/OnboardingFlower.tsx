import { useEffect } from "react"
import { AnimatePresence, motion, useAnimation } from "framer-motion"
import { useReducedMotion } from "../../lib/useReducedMotion"
import styles from "./onboarding.module.css"

export type FlowerStage = "bud" | "opening" | "bloom"

const STAGE_SRC: Record<FlowerStage, string> = {
  bud: "/flowers/bud.webp",
  opening: "/flowers/opening.webp",
  bloom: "/flowers/bloom.webp"
}

const NEXT_STAGE: Record<FlowerStage, FlowerStage | null> = {
  bud: "opening",
  opening: "bloom",
  bloom: null
}

const STAGE_HEIGHT: Record<FlowerStage, number> = {
  bud: 220,
  opening: 240,
  bloom: 300
}

// The flower IS the onboarding progress indicator. Today it's three static
// images cross-faded/scaled by framer-motion; later this can become a real
// animated 3D bloom (R3F / Model Viewer) without OnboardingFlow or any step
// component needing to change - they only ever pass a `stage`.
export function OnboardingFlower({
  stage,
  blend = 0,
  pulseKey
}: {
  stage: FlowerStage
  /** 0-1 hint of progress toward the next stage, blended in softly. */
  blend?: number
  /** Increment to trigger a small reactive pulse (e.g. on each selection). */
  pulseKey?: number
}) {
  const reduced = useReducedMotion()
  const nextStage = NEXT_STAGE[stage]

  // The pulse lives on a wrapper that never unmounts across stage changes,
  // so it can't race AnimatePresence's exit/enter choreography for the
  // stage image itself (that one is driven declaratively below instead of
  // through these same controls - mixing the two caused the flower to never
  // actually animate in when `mode="wait"` delayed the new image's mount).
  const pulseControls = useAnimation()

  useEffect(() => {
    if (!pulseKey || reduced) return
    pulseControls.start({
      scale: [1, 1.05, 1],
      rotate: [0, -1.5, 0],
      transition: { duration: 0.45, ease: "easeOut" }
    })
  }, [pulseKey, reduced, pulseControls])

  const height = STAGE_HEIGHT[stage]

  return (
    <motion.div className={styles.flowerStage} style={{ height }} animate={pulseControls}>
      <AnimatePresence mode="wait">
        <motion.img
          key={stage}
          src={STAGE_SRC[stage]}
          alt=""
          className={styles.flowerImg}
          style={{ height }}
          initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.92, y: 10, rotate: -2 }}
          animate={reduced ? { opacity: 1 } : { opacity: 1, scale: 1, y: 0, rotate: 0 }}
          exit={reduced ? { opacity: 0 } : { opacity: 0, scale: 1.04, y: -10, rotate: 2 }}
          transition={{ duration: reduced ? 0.2 : 0.5, ease: "easeOut" }}
        />
      </AnimatePresence>

      {!reduced && nextStage && blend > 0 && (
        <motion.img
          src={STAGE_SRC[nextStage]}
          alt=""
          className={styles.flowerImgBlend}
          style={{ height }}
          animate={{ opacity: blend * 0.5 }}
          transition={{ duration: 0.3 }}
        />
      )}
    </motion.div>
  )
}
