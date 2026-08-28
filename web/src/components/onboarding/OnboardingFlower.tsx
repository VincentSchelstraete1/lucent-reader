import { useEffect, useRef } from "react"
import { motion, useAnimation } from "framer-motion"
import { useReducedMotion } from "../../lib/useReducedMotion"
import styles from "./onboarding.module.css"

export function OnboardingFlower({ progress, pulseKey }: { progress: number; pulseKey: number }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const targetTime = useRef(0)
  const frame = useRef<number>()
  const reduced = useReducedMotion()
  const controls = useAnimation()
  useEffect(() => {
    const video = videoRef.current
    if (!video || !Number.isFinite(video.duration)) return
    targetTime.current = Math.max(0, Math.min(video.duration, progress * video.duration))
    if (reduced) { video.currentTime = targetTime.current; return }
    const start = video.currentTime
    const startAt = performance.now()
    cancelAnimationFrame(frame.current ?? 0)
    const tick = (now: number) => {
      const amount = Math.min((now - startAt) / 440, 1)
      video.currentTime = start + (targetTime.current - start) * (1 - Math.pow(1 - amount, 3))
      if (amount < 1) frame.current = requestAnimationFrame(tick)
    }
    frame.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame.current ?? 0)
  }, [progress, reduced])
  useEffect(() => {
    if (!pulseKey || reduced) return
    controls.start({ rotate: [0, -1, 0], scale: [1, 1.018, 1], transition: { duration: 0.18 } })
  }, [pulseKey, reduced, controls])
  return <motion.div className={styles.flowerStage} animate={controls} aria-hidden="true"><video ref={videoRef} className={styles.flowerVideo} src="/videos/flower-bloom.mp4" muted playsInline preload="auto" onLoadedMetadata={(event) => { event.currentTarget.currentTime = progress * event.currentTarget.duration }} /></motion.div>
}
