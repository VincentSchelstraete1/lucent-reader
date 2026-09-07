import { useState, type MouseEvent } from "react"
import { AnimatePresence, motion } from "framer-motion"
import styles from "./marketing.module.css"
type Action = "explain" | "simplify" | "note" | "save"
const actions: { key: Action; label: string }[] = [{ key: "simplify", label: "Simplify" }, { key: "explain", label: "Explain" }, { key: "note", label: "Note" }, { key: "save", label: "Save" }]
export function DemoContent() {
  const [selected, setSelected] = useState(false), [action, setAction] = useState<Action | null>(null), [note, setNote] = useState("")
  function detectSelection(event: MouseEvent<HTMLDivElement>) { if (window.getSelection()?.toString().trim()) setSelected(true); event.currentTarget.focus() }
  return <section id="demo" className={`${styles.section} ${styles.wideSection}`}>
    <div className={styles.sectionIntro}><p className={styles.eyebrow}>Try it here</p><h2 className={styles.sectionHeading}>Understanding, right where you’re reading.</h2><p className={styles.sectionBody}>Select the highlighted thought—or any text in the passage—to bring Lucent into context.</p></div>
    <div className={styles.browserDemo}><div className={styles.browserChrome}><span/><span/><span/><strong>fieldnotes.science / photosynthesis</strong></div><div className={styles.articleDemo} onMouseUp={detectSelection} tabIndex={0}>
      <p className={styles.articleKicker}>BOTANY · 6 MIN READ</p><h3>How plants turn light into stored energy</h3><p>Leaves capture light through pigments called chlorophyll. That light begins a chain of reactions inside each cell.</p>
      <button className={`${styles.selectableSentence} ${selected ? styles.selectedSentence : ""}`} onClick={() => setSelected(true)}>The light-dependent reactions create an electrochemical gradient that powers the synthesis of ATP.</button>
      <p>Plants then use that stored energy to assemble sugars from carbon dioxide.</p>
      <AnimatePresence>{selected && <motion.div className={styles.floatingToolbar} initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} exit={{opacity:0}}>{actions.map(item => <button key={item.key} aria-pressed={action===item.key} onClick={() => setAction(item.key)}>{item.label}</button>)}</motion.div>}</AnimatePresence>
      {action && <motion.div className={styles.demoResult} key={action} initial={{opacity:0}} animate={{opacity:1}}>{action === "explain" && <><strong>In context</strong><p>The cell builds up charged particles like water behind a dam. Their release drives a tiny molecular motor that makes ATP—the cell’s portable energy.</p></>}{action === "simplify" && <><strong>Simplified</strong><p>Light builds pressure inside the cell. Releasing that pressure creates usable energy.</p></>}{action === "note" && <label><strong>Your note</strong><textarea value={note} onChange={e=>setNote(e.target.value)} placeholder="Connect this to what you know…" autoFocus /></label>}{action === "save" && <p className={styles.savedState}>✓ Saved to Photosynthesis in your library</p>}</motion.div>}
    </div></div>
  </section>
}
