import { useState } from "react"
import styles from "./marketing.module.css"
const modes = {
  concise: "A gradient stores energy by separating charged particles.",
  "step by step": "1. Light moves charges. 2. Charges build pressure. 3. Their flow powers ATP production.",
  "examples first": "Like water held behind a dam, separated charges can release stored energy when allowed to flow.",
  visual: "light → charge gradient → molecular motor → ATP"
}

export function PersonalizationContent() {
  const [mode,setMode]=useState<keyof typeof modes>("concise")
  return <section className={`${styles.section} ${styles.splitSection}`}><div><p className={styles.eyebrow}>It learns how you learn</p><h2 className={styles.sectionHeading}>One idea, presented your way.</h2><p className={styles.sectionBody}>Choose the shape that helps now. Lucent can keep that preference close without reducing you to a score.</p></div><div className={styles.personalizationDemo}><div className={styles.modeTabs}>{Object.keys(modes).map(item=><button aria-pressed={item===mode} key={item} onClick={()=>setMode(item as keyof typeof modes)}>{item}</button>)}</div><span>Electrochemical gradient</span><p>{modes[mode]}</p></div></section>
}
