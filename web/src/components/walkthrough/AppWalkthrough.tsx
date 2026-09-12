import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { CHROME_EXTENSION_URL } from "../../lib/extension"
import styles from "./walkthrough.module.css"
const KEY="lucent-app-tour-complete"
export const APP_WALKTHROUGH_STEPS=[
 {target:"app-brand",title:"Your Lucent library",body:"Everything you save with Lucent returns here, organized around its original source."},
 {target:"app-brand",title:"Bring Lucent into Chrome",body:"Add the Lucent extension to explain, simplify, and save difficult text while you read.",cta:{label:"Add to Chrome",href:CHROME_EXTENSION_URL}},
 {target:"library-heading",title:"Start from a source",body:"Open a saved article or page to revisit what caught your attention."},
 {target:"library-content",title:"Highlight and clarify",body:"In the browser extension, select difficult text and choose Explain or Simplify without leaving the page."},
 {target:"library-content",title:"Save your understanding",body:"Saved explanations and notes retain their source, so they still make sense later."},
 {target:"app-brand",title:"Revisit it later",body:"Return here whenever you want to review ideas and continue learning."}
]
const steps=APP_WALKTHROUGH_STEPS
type Box={top:number;left:number;width:number;height:number}
export function shouldOpenAppWalkthrough(search: string, completed: string | null) {
 return new URLSearchParams(search).get("welcome") === "1" || completed !== "1"
}
export function AppWalkthrough(){
 const [open,setOpen]=useState(()=>shouldOpenAppWalkthrough(window.location.search,localStorage.getItem(KEY))),[index,setIndex]=useState(0),[box,setBox]=useState<Box|null>(null);const dialog=useRef<HTMLDivElement>(null)
 const step=steps[index]
 useLayoutEffect(()=>{if(!open)return;const update=()=>{const node=document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);if(node){const r=node.getBoundingClientRect();setBox({top:r.top-8,left:r.left-8,width:r.width+16,height:r.height+16})}};update();window.addEventListener("resize",update);window.addEventListener("scroll",update,{passive:true});return()=>{window.removeEventListener("resize",update);window.removeEventListener("scroll",update)}},[open,step])
 useEffect(()=>{if(open)dialog.current?.focus()},[open,index])
 function close(){localStorage.setItem(KEY,"1");const url=new URL(window.location.href);if(url.searchParams.has("welcome")){url.searchParams.delete("welcome");window.history.replaceState(window.history.state,"",`${url.pathname}${url.search}${url.hash}`)}setOpen(false)}
 if(!open||!box)return null
 const dialogTop=Math.min(window.innerHeight-240,box.top+box.height+18)
 return <div className={styles.layer}><div className={styles.spotlight} style={box}/><div ref={dialog} className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="tour-title" tabIndex={-1} style={{top:Math.max(18,dialogTop),left:Math.min(window.innerWidth-330,Math.max(18,box.left))}} onKeyDown={e=>{if(e.key==="Escape")close()}}><div className={styles.progress}>{steps.map((_,i)=><span key={i} data-active={i<=index}/>)}</div><span className={styles.count}>{index+1} / {steps.length}</span><h2 id="tour-title">{step.title}</h2><p>{step.body}</p>{step.cta&&<a className={styles.extensionCta} href={step.cta.href} target="_blank" rel="noreferrer">{step.cta.label} <span aria-hidden="true">↗</span></a>}<div className={styles.actions}><button onClick={close}>Skip tour</button><span/>{index>0&&<button onClick={()=>setIndex(i=>i-1)}>Back</button>}<button className={styles.next} onClick={()=>index===steps.length-1?close():setIndex(i=>i+1)}>{index===steps.length-1?"Finish":"Next"}</button></div></div></div>
}
