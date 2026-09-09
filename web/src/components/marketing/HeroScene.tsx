import { lazy, Suspense, useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import * as THREE from 'three'
import { pagePose, passingPagePose, smooth, WORLD } from './flythrough'
import { openingCamera } from './openingScene'
import { OpeningLandscape } from './OpeningLandscape'
import { StructuredVisual } from '../../learning/visuals/StructuredVisual'
import { qualityControlVisual } from './LucentProductDemo'
import styles from './marketing.module.css'
const ProductDemo = lazy(() => import('./LucentProductDemo').then(m => ({ default: m.LucentProductDemo })))
type Progress = { scrollRef: MutableRefObject<number> }

function CameraJourney({ scrollRef, journeyRef }: Progress & { journeyRef: MutableRefObject<number> }) {
  const { camera, gl, invalidate } = useThree()
  const p = useRef(scrollRef.current)
  useFrame(({clock}, delta) => {
    p.current = THREE.MathUtils.damp(p.current, scrollRef.current, 6, Math.min(delta,.1))
    journeyRef.current=p.current
    if (Math.abs(p.current-scrollRef.current)>.00001) invalidate()
    const pose=openingCamera(p.current,clock.elapsedTime)
    camera.position.copy(pose.position); camera.lookAt(pose.target); camera.rotateZ(pose.roll)
    gl.domElement.dataset.camera=camera.position.toArray().map(v=>v.toFixed(2)).join(',')
    gl.domElement.dataset.progress=p.current.toFixed(3)
  })
  return null
}

const pageCopy = [
  ["Source material", "When a cell", "finds damage.", "Cells continually monitor their proteins. When a protein loses its working shape, a control signal coordinates the response. The response may repair or remove a faulty protein, preventing it from disrupting other processes."],
  ["Simplify", "The essential", "idea.", "Finding damage is not the same as fixing it. The signal carries the message to act."],
  ["Explain", "Detection is", "only the start.", "A smoke alarm calls for action. It does not put out the fire itself."],
  ["Visualize", "See the", "connection.", "Damage detected → Signal sent → Response begins"],
  ["Practice", "Put the idea", "to work.", "If the signal is blocked, can detecting damage alone protect the cell?"],
]

function usePaperTextures() {
  const textures = useMemo(() => pageCopy.map(([label, first, second, text], i) => {
    const canvas = document.createElement("canvas"); canvas.width = 768; canvas.height = 1024
    const ctx = canvas.getContext("2d")!
    ctx.fillStyle = "#f7f5ed"; ctx.fillRect(0, 0, 768, 1024)
    ctx.fillStyle = "#63796a"; ctx.font = "18px sans-serif"; ctx.fillText("LUCENT / " + label.toUpperCase(), 66, 80); ctx.fillText("0" + (i + 1), 663, 80)
    ctx.strokeStyle = "#b4bfb0"; ctx.beginPath(); ctx.moveTo(66, 112); ctx.lineTo(702, 112); ctx.stroke()
    ctx.font = "24px sans-serif"; ctx.fillText("Cellular quality control", 66, 195)
    ctx.fillStyle = "#263d34"; ctx.font = '76px "Lucent Landing Serif", Georgia'; ctx.fillText(first, 66, 310); ctx.fillText(second, 66, 392)
    ctx.font = "27px sans-serif"
    let line = "", y = 483
    for (const word of text.split(" ")) { if (ctx.measureText(line + word).width > 625) { ctx.fillText(line, 66, y); y += 44; line = "" }; line += word + " " }
    ctx.fillText(line, 66, y); ctx.fillStyle = "#c2cbbb"
    for (let j = 0; j < 5; j++) ctx.fillRect(66, 735 + j * 19, j % 2 ? 560 : 625, 2)
    ctx.fillStyle = "#627764"; ctx.font = "italic 23px Georgia"; ctx.fillText("Detect. Signal. Respond.", 66, 928)
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; texture.anisotropy = 4
    return texture
  }), [])
  useEffect(() => () => textures.forEach(t => t.dispose()), [textures])
  return textures
}


function DocumentSheets({ activeCard, onNext, scrollRef }: Progress & { activeCard: number; onNext: () => void }) {
  const textures=usePaperTextures(), group=useRef<THREE.Group>(null!), tilt=useRef(0)
  const geometry=useMemo(()=>{
    const g=new THREE.PlaneGeometry(8,10.8,32,40),p=g.attributes.position
    for(let i=0;i<p.count;i++){
      const x=p.getX(i),y=p.getY(i)
      // A relaxed sheet: slight concavity and a lifted lower corner, not a rigid panel.
      p.setZ(i,.035*x*x + .2*Math.pow(Math.max(0,x/4),3)*Math.pow(Math.max(0,-y/5.4),2))
    }
    g.computeVertexNormals();return g
  },[])
  useEffect(()=>()=>geometry.dispose(),[geometry])
  const {invalidate}=useThree()
  useFrame((_,dt)=>{
    group.current.children.forEach((child,i)=>{
      const pose=pagePose(scrollRef.current,i,activeCard)
      child.position.lerp(pose.position,1-Math.exp(-10*Math.min(dt,.1)))
      child.rotation.x=pose.rotation.x
      child.rotation.y=THREE.MathUtils.damp(child.rotation.y,pose.rotation.y+tilt.current,8,dt)
      child.rotation.z=pose.rotation.z
      child.visible=scrollRef.current>.045 && pose.depart<1 && (i>=activeCard || child.rotation.y>-1.6)
    })
  })
  return <group ref={group} onPointerMove={()=>{tilt.current=.018;invalidate()}} onPointerOut={()=>{tilt.current=0;invalidate()}} onClick={e=>{if(scrollRef.current>.19 && scrollRef.current<.31){e.stopPropagation();onNext()}}}>
    {textures.map((texture,i)=><group key={i} position={pagePose(0,i).position}>
      <mesh geometry={geometry} position={[0,0,-.025]} castShadow receiveShadow><meshStandardMaterial color="#e9e6db" roughness={.95} side={THREE.BackSide}/></mesh>
      <mesh geometry={geometry} castShadow receiveShadow><meshStandardMaterial map={texture} roughness={.95} side={THREE.FrontSide}/></mesh>
    </group>)}
  </group>
}

function PassingPages({scrollRef}:Progress) {
  const textures=usePaperTextures(), group=useRef<THREE.Group>(null!)
  const geometry=useMemo(()=>{const g=new THREE.PlaneGeometry(2.8,3.9,20,16),p=g.attributes.position
    for(let i=0;i<p.count;i++)p.setZ(i,Math.sin(p.getX(i)*1.1)*.14)
    g.computeVertexNormals();return g},[])
  useEffect(()=>()=>geometry.dispose(),[geometry])
  useFrame(()=>group.current.children.forEach((child,i)=>{const pose=passingPagePose(scrollRef.current,i);child.position.copy(pose.position);child.rotation.copy(pose.rotation);child.visible=pose.visible}))
  return <group ref={group}>{Array.from({length:7},(_,i)=><mesh key={i} geometry={geometry}><meshStandardMaterial map={textures[i%5]} roughness={.9} side={THREE.DoubleSide}/></mesh>)}</group>
}

// Actual world-depth cloud planes: opaque sheets occlude clouds behind them;
// clouds nearer the lens veil those sheets. No screen-space white wipe.
function ValleyClouds(){
  const group=useRef<THREE.Group>(null!)
  const banks=useMemo(()=>[
    ...Array.from({length:18},(_,i)=>({x:Math.sin(i*2.3)*18,y:i%3===0?35:12+i%4*5,z:238-i*9,w:i%3===0?64:48,h:i%3===0?20:12,strength:.22})),
    {x:6,y:18,z:198,w:31,h:9,strength:.8},
    {x:3,y:26,z:180,w:38,h:14,strength:.5},
    {x:-2,y:37,z:213,w:46,h:15,strength:.38},
  ],[])
  const uniforms=useMemo(()=>({time:{value:0}}),[])
  useFrame(({clock})=>{uniforms.time.value=clock.elapsedTime;group.current.children.forEach((c,i)=>{c.position.x=banks[i].x+Math.sin(clock.elapsedTime*.024+i)*2})})
  return <group ref={group}>{banks.map((bank,i)=><mesh key={i} position={[bank.x,bank.y,bank.z]} renderOrder={5} raycast={()=>{}}>
    <planeGeometry args={[bank.w,bank.h]}/>
    <shaderMaterial uniforms={uniforms} transparent depthWrite={false} side={THREE.DoubleSide} toneMapped={false}
      vertexShader={`varying vec2 v;void main(){v=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`}
      fragmentShader={`uniform float time;varying vec2 v;
        float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
        float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+1.),f.x),f.y);}
        void main(){vec2 p=v*vec2(7.,4.)+vec2(time*.018,time*.006);float c=n(p)*.6+n(p*2.03)*.28+n(p*4.1)*.12;
        float edge=pow(max(0.,1.-length((v-.5)*2.)),1.4);float a=smoothstep(.25,.77,c)*edge*${bank.strength.toFixed(2)};
        gl_FragColor=vec4(mix(vec3(.77,.82,.82),vec3(1.,.91,.77),v.y),a);}`}/>
  </mesh>)}</group>
}

function ProductPortal({scrollRef}:Progress){
  const [active,setActive]=useState(false), flag=useRef(false), group=useRef<THREE.Group>(null!)
  const content=useRef<HTMLElement>(null!)
  useFrame(()=>{
    const p=scrollRef.current,next=p>.57&&p<.705
    if(next!==flag.current){flag.current=next;setActive(next)}
    // Located in the valley throughout; distant fog and perspective reveal it.
    group.current.visible=p>.43&&p<.86
    group.current.position.y=WORLD.product[1]-smooth(p,.74,.85)*24
    if(content.current)content.current.style.opacity=String(smooth(p,.43,.53)*(1-smooth(p,.74,.85)))
  })
  return <group ref={group} position={[...WORLD.product]}>
    <mesh position={[0,0,-.18]} castShadow receiveShadow><boxGeometry args={[17.4,12.8,.25]}/><meshStandardMaterial color="#f7f7f1" roughness={.9}/></mesh>
    <Html wrapperClass={styles.worldSurface} transform distanceFactor={6.5} center occlude zIndexRange={[12,1]} style={{width:1050,pointerEvents:active?'auto':'none',backfaceVisibility:'hidden'}}>
      <section ref={content} style={{opacity:0}} className={styles.worldProduct} aria-label="Interactive Lucent preview" aria-hidden={!active} {...(!active?{inert:''}:{})}>
        <div className={styles.worldProductHeading}><span>03 / LEARN WITH LUCENT</span><h2>From reading to reasoning.</h2></div>
        <Suspense fallback={<div className={styles.demoLoading}>Opening the learning preview…</div>}><ProductDemo/></Suspense>
      </section>
    </Html>
  </group>
}

function VisualEncounter({scrollRef}:Progress){
  const group=useRef<THREE.Group>(null!), content=useRef<HTMLElement>(null!)
  useFrame(()=>{group.current.visible=scrollRef.current>.40&&scrollRef.current<.59;if(content.current)content.current.style.opacity=String(smooth(scrollRef.current,.40,.46)*(1-smooth(scrollRef.current,.53,.59)))})
  return <group ref={group} position={[...WORLD.visual]} rotation={[0,.3,0]}>
    <mesh><boxGeometry args={[8,6,.1]}/><meshStandardMaterial color="#eff1e9" roughness={.9}/></mesh>
    <Html wrapperClass={styles.worldSurface} transform center distanceFactor={4.2} occlude zIndexRange={[10,1]} style={{width:660,pointerEvents:'none'}}>
      <article ref={content} style={{opacity:0}} className={styles.worldDiscovery} aria-hidden="true" {...{inert:''}}><small>SEE THE CONNECTION</small><h2>An idea, opened up.</h2><StructuredVisual spec={qualityControlVisual} initialStage={1}/></article>
    </Html>
  </group>
}
function Overlook({scrollRef}:Progress) {
  const group=useRef<THREE.Group>(null!)
  useFrame(()=>{group.current.visible=scrollRef.current>.8})
  return <group ref={group} position={[0, 8, 51]}>
    
    <mesh receiveShadow position={[0, -.2, 5]}><boxGeometry args={[16, .4, 18]} /><meshStandardMaterial color="#737f7b" roughness={1} /></mesh>
    {/* A quiet, human-scale silhouette, facing away into the lake. */}
    <group position={[0, 0, -2]}>
      <mesh position={[0, 1.61, 0]} castShadow><sphereGeometry args={[.145, 12, 12]} /><meshStandardMaterial color="#182622" /></mesh>
      <mesh position={[0, 1.13, 0]} castShadow><capsuleGeometry args={[.19, .52, 4, 8]} /><meshStandardMaterial color="#182622" /></mesh>
      {[-1, 1].map(side => <group key={side}>
        <mesh position={[side * .12, .4, 0]} rotation={[0, 0, side * -.045]} castShadow><capsuleGeometry args={[.07, .68, 4, 8]} /><meshStandardMaterial color="#182622" /></mesh>
        <mesh position={[side * .26, 1.05, 0]} rotation={[0, 0, side * .12]} castShadow><capsuleGeometry args={[.06, .52, 4, 8]} /><meshStandardMaterial color="#182622" /></mesh>
      </group>)}
    </group>
  </group>
}


export function HeroScene({scrollRef,activeCard,onNext}:Progress&{activeCard:number;onNext:()=>void}){
  const journeyRef=useRef(scrollRef.current)
  const sunlightTarget=useMemo(()=>{const o=new THREE.Object3D();o.position.set(...WORLD.hero);return o},[])
  return <>
    <color attach="background" args={['#879c9f']}/><fogExp2 attach="fog" args={['#dce0da',.008]}/>
    <CameraJourney scrollRef={scrollRef} journeyRef={journeyRef}/>
    <ambientLight intensity={.55}/><hemisphereLight args={['#fff6e4','#829691',.6]}/>
    <primitive object={sunlightTarget}/>
    <directionalLight position={[18,45,224]} target={sunlightTarget} intensity={2.2} color="#fff0d6" castShadow shadow-mapSize={[2048,2048]} shadow-camera-left={-22} shadow-camera-right={22} shadow-camera-top={24} shadow-camera-bottom={-24} shadow-camera-near={1} shadow-camera-far={100} shadow-normalBias={.06} shadow-bias={-.0001} shadow-radius={3}/>
    <Suspense fallback={null}><OpeningLandscape progress={journeyRef}/><DocumentSheets scrollRef={journeyRef} activeCard={activeCard} onNext={onNext}/><PassingPages scrollRef={journeyRef}/></Suspense>
    <ValleyClouds/><VisualEncounter scrollRef={journeyRef}/><ProductPortal scrollRef={journeyRef}/><Overlook scrollRef={journeyRef}/>
  </>
}
