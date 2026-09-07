import { useEffect, useRef, useState } from "react"
import { useMotionValueEvent, useScroll } from "framer-motion"
import { useReducedMotion } from "../../lib/useReducedMotion"
import styles from "./marketing.module.css"

export function ScrollFlower() {
  const sectionRef = useRef<HTMLElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [duration, setDuration] = useState(0)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: sectionRef, offset: ["start end", "end start"] })
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const ready = () => setDuration(Number.isFinite(video.duration) ? video.duration : 0)
    video.addEventListener("loadedmetadata", ready)
    if (video.readyState >= 1) ready()
    return () => video.removeEventListener("loadedmetadata", ready)
  }, [])
  useMotionValueEvent(scrollYProgress, "change", value => {
    const video = videoRef.current
    if (!video || !duration) return
    const progress = reduced ? (value < .5 ? .08 : .92) : Math.max(.04, Math.min(.96, value))
    const next = progress * duration
    if (Math.abs(video.currentTime - next) > .025) video.currentTime = next
  })
  return <section ref={sectionRef} className={styles.flowerTransition} aria-label="Understanding in bloom"><div className={styles.flowerSticky}>
    <video ref={videoRef} className={styles.flowerVideo} src="/videos/flower-bloom.mp4" muted playsInline preload="auto" disablePictureInPicture />
    <p>As ideas become clear, understanding opens.</p>
  </div></section>
}
