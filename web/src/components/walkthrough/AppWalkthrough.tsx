import { useEffect, useLayoutEffect, useRef, useState } from "react"
import styles from "./walkthrough.module.css"
const KEY="lucent-app-tour-complete"
const steps=[
 {target:"app-brand",title:"Your Lucent library",body:"Everything you save with Lucent returns here, organized around its original source."},
 {target:"library-heading",title:"Start from a source",body:"Open a saved article or page to revisit what caught your attention."},
 {target:"library-content",title:"Highlight and clarify",body:"In the browser extension, select difficult text and choose Explain or Simplify without leaving the page."},
 {target:"library-content",title:"Save your understanding",body:"Saved explanations and notes retain their source, so they still make sense later."},
 {target:"app-brand",title:"Revisit it later",body:"Return here whenever you want to review ideas and continue learning."}
]
type Box={top:number;left:number;width:number;height:number}
export function AppWalkthrough(){
 const [open,setOpen]=useState(()=>localStorage.getItem(KEY)!=="1"),[index,setIndex]=useState(0),[box,setBox]=useState<Box|null>(null);const dialog=useRef<HTMLDivElement>(null)
 const step=steps[index]
 useLayoutEffect(()=>{if(!open)return;const update=()=>{const node=document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);if(node){const r=node.getBoundingClientRect();setBox({top:r.top-8,left:r.left-8,width:r.width+16,height:r.height+16})}};update();window.addEventListener("resize",update);window.addEventListener("scroll",update,{passive:true});return()=>{window.removeEventListener("resize",update);window.removeEventListener("scroll",update)}},[open,step])
 useEffect(()=>{if(open)dialog.current?.focus()},[open,index])
 function close(){localStorage.setItem(KEY,"1");setOpen(false)}
 if(!open||!box)return null
 const dialogTop=Math.min(window.innerHeight-240,box.top+box.height+18)
 return <div className={styles.layer}><div className={styles.spotlight} style={box}/><div ref={dialog} className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="tour-title" tabIndex={-1} style={{top:Math.max(18,dialogTop),left:Math.min(window.innerWidth-330,Math.max(18,box.left))}} onKeyDown={e=>{if(e.key==="Escape")close()}}><div className={styles.progress}>{steps.map((_,i)=><span key={i} data-active={i<=index}/>)}</div><span className={styles.count}>{index+1} / {steps.length}</span><h2 id="tour-title">{step.title}</h2><p>{step.body}</p><div className={styles.actions}><button onClick={close}>Skip tour</button><span/>{index>0&&<button onClick={()=>setIndex(i=>i-1)}>Back</button>}<button className={styles.next} onClick={()=>index===steps.length-1?close():setIndex(i=>i+1)}>{index===steps.length-1?"Finish":"Next"}</button></div></div></div>
}
