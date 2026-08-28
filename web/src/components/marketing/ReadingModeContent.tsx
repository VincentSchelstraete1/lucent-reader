import { useMemo, useState } from "react"
import styles from "./marketing.module.css"
type Level="simple"|"standard"|"advanced"; type Spacing="off"|"low"|"medium"|"high"; type Theme="light"|"dark"; type Width="narrow"|"medium"|"wide"; type Font="serif"|"sans"
export function ReadingModeContent(){
 const [level,setLevel]=useState<Level>("standard"),[length,setLength]=useState(70),[font,setFont]=useState<Font>("serif"),[spacing,setSpacing]=useState<Spacing>("medium"),[size,setSize]=useState(100),[theme,setTheme]=useState<Theme>("light"),[width,setWidth]=useState<Width>("medium"),[focus,setFocus]=useState(false),[enabled,setEnabled]=useState(true)
 const paragraphs=useMemo(()=>{const copy={simple:["Plants use sunlight to make food. Leaves collect light and turn it into energy the plant can use.","This process also releases oxygen into the air."],standard:["Photosynthesis is the process plants use to convert light energy into chemical energy. Chlorophyll captures sunlight, beginning reactions that eventually produce sugars.","Those sugars support growth while oxygen is released as a by-product. The process connects sunlight, water, and carbon dioxide in one remarkable system."],advanced:["Photosynthesis converts electromagnetic energy into stable chemical bonds through coupled light-dependent and carbon-fixation reactions. Excited chlorophyll electrons establish the proton gradient used to synthesize ATP.","The Calvin cycle then uses ATP and NADPH to fix atmospheric carbon into organic molecules, sustaining most terrestrial food webs."]};return copy[level].slice(0,length<45?1:2)},[level,length])
 const spacingValue={off:"1.45",low:"1.6",medium:"1.85",high:"2.15"}[spacing]
 return <section id="reading-mode" className={`${styles.section} ${styles.wideSection}`}><div className={styles.sectionIntro}><p className={styles.eyebrow}>Reading Mode</p><h2 className={styles.sectionHeading}>Make the page fit the reader.</h2><p className={styles.sectionBody}>A functional preview based on Lucent’s compact extension controls.</p></div>
 <div className={styles.readingShell} data-theme={theme}>
  <aside className={styles.readingPanel} aria-label="Reading Mode preferences"><h3>Reading Mode</h3><button className={styles.simplifyButton} onClick={()=>setLevel("simple")}>Simplify Entire Page</button>
   <Control label="Target Reading Level"><Segment values={["simple","standard","advanced"]} value={level} set={v=>setLevel(v as Level)}/></Control>
   <Control label="Text Length"><input aria-label="Text length" type="range" min="25" max="100" value={length} onChange={e=>setLength(+e.target.value)}/></Control>
   <Control label="Reading Font"><Segment values={["serif","sans"]} value={font} set={v=>setFont(v as Font)}/></Control>
   <Control label="Text Spacing"><Segment values={["off","low","medium","high"]} value={spacing} set={v=>setSpacing(v as Spacing)}/></Control>
   <Control label="Text Size"><div className={styles.stepper}><button aria-label="Decrease text size" onClick={()=>setSize(v=>Math.max(80,v-10))}>A−</button><span>{size}%</span><button aria-label="Increase text size" onClick={()=>setSize(v=>Math.min(140,v+10))}>A+</button></div></Control>
   <Control label="Theme"><Segment values={["light","dark"]} value={theme} set={v=>setTheme(v as Theme)}/></Control>
   <Control label="Page Width"><Segment values={["narrow","medium","wide"]} value={width} set={v=>setWidth(v as Width)}/></Control>
   <Control label="Focus Line"><button className={styles.toggle} aria-pressed={focus} onClick={()=>setFocus(!focus)}>{focus?"On":"Off"}</button></Control>
  </aside>
  <div className={styles.readerSurface}><article className={styles.readerArticle} data-width={width} style={{fontFamily:font==="serif"?"var(--lucent-font-editorial)":"var(--lucent-font-ui)",fontSize:`${size}%`,lineHeight:spacingValue,opacity:enabled?1:.48}}><span className={styles.readerLabel}>A field guide</span><h3>Energy, held in a leaf</h3>{paragraphs.map((p,i)=><p key={p} className={focus&&i!==0?styles.unfocused:""}>{p}</p>)}</article>
   <div className={styles.bottomBar}><button aria-pressed={enabled} onClick={()=>setEnabled(!enabled)}>◉ {enabled?"On":"Off"}</button><button onClick={()=>setFont(font==="serif"?"sans":"serif")}>Font: {font}</button><button onClick={()=>setSize(v=>v>=140?80:v+10)}>{size}%</button><button onClick={()=>setSpacing(spacing==="high"?"off":spacing==="medium"?"high":spacing==="low"?"medium":"low")}>Spacing: {spacing}</button><button onClick={()=>setTheme(theme==="light"?"dark":"light")}>{theme}</button></div>
  </div>
 </div></section>}
function Control({label,children}:{label:string;children:React.ReactNode}){return <div className={styles.control}><label>{label}</label>{children}</div>}
function Segment({values,value,set}:{values:string[];value:string;set:(v:string)=>void}){return <div className={styles.segment}>{values.map(v=><button key={v} aria-pressed={v===value} onClick={()=>set(v)}>{v}</button>)}</div>}
