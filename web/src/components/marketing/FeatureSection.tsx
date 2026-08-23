import styles from "./marketing.module.css"

const FEATURES = [
  { name: "Explain", desc: "Get a difficult passage explained in a way that actually clicks for you." },
  { name: "Visualize", desc: "See structure and connections in ideas that are hard to picture in your head." },
  { name: "Note", desc: "Turn what you read into notes you'll actually want to look back at." },
  { name: "Recall", desc: "Short quizzes built from what you've read, so it sticks." },
  { name: "Connect", desc: "See how new material relates to what you already know." }
]

export function FeatureSection() {
  return (
    <section id="features" className={styles.features}>
      <p className={styles.eyebrow}>Built for how you learn</p>
      <h2 className={styles.featuresHeading}>Everything you need to learn smarter.</h2>

      <div className={styles.featureList}>
        {FEATURES.map((f, i) => (
          <div key={f.name} className={styles.featureRow}>
            <span className={styles.featureIndex}>{String(i + 1).padStart(2, "0")}</span>
            <span className={styles.featureName}>
              <span className={styles.featureAccent} />
              {f.name}
            </span>
            <span className={styles.featureDesc}>{f.desc}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
