import { lazy, Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState, type MutableRefObject } from "react"
import { useFrame, useThree } from "@react-three/fiber"
import { Bvh, Html, MeshReflectorMaterial, useTexture } from "@react-three/drei"
import * as THREE from "three"
import { architectureFormation, cameraPose, pageFormation, paperRibbon, ridgeGeometry, smooth } from "./flythrough"
import { StructuredVisual } from "../../learning/visuals/StructuredVisual"
import { qualityControlVisual } from "./LucentProductDemo"
import styles from "./marketing.module.css"

const ProductDemo = lazy(() => import("./LucentProductDemo").then(m => ({ default: m.LucentProductDemo })))
type Progress = { scrollRef: MutableRefObject<number> }

function CameraJourney({ scrollRef, journeyRef }: Progress & { journeyRef: MutableRefObject<number> }) {
  const { camera, gl, scene, invalidate } = useThree()
  const progress = useRef(scrollRef.current)
  useFrame((_, delta) => {
    progress.current = THREE.MathUtils.damp(progress.current, scrollRef.current, 6, Math.min(delta, .1))
    if (Math.abs(progress.current - scrollRef.current) > .00001) invalidate()
    journeyRef.current = progress.current
    const pose = cameraPose(progress.current)
    camera.position.copy(pose.position); camera.lookAt(pose.target); camera.rotateZ(pose.roll)
    if (scene.fog instanceof THREE.FogExp2) scene.fog.density = .0018 + Math.sin(progress.current * Math.PI) * .0005
    // Read-only browser diagnostics: actual camera travel, not CSS zoom.
    gl.domElement.dataset.camera = camera.position.toArray().map(v => v.toFixed(2)).join(",")
    gl.domElement.dataset.progress = progress.current.toFixed(3)
  })
  return null
}

function AlpineWorld() {
  const texture = useTexture("/lucent-alpine-panorama.jpg")
  const ground = useTexture("/lucent-alpine-ground.jpg")
  const waterNormal = useMemo(() => {
    const data = new Uint8Array(128 * 128 * 4)
    for (let y = 0; y < 128; y++) for (let x = 0; x < 128; x++) {
      const i = (y * 128 + x) * 4, wave = Math.sin(y * Math.PI / 8 + Math.sin(x * Math.PI / 32))
      data[i] = 128 + Math.sin(x * Math.PI / 16) * 12; data[i + 1] = 128 + wave * 28; data[i + 2] = 252; data[i + 3] = 255
    }
    const normal = new THREE.DataTexture(data, 128, 128); normal.wrapS = normal.wrapT = THREE.RepeatWrapping; normal.repeat.set(180, 180); normal.needsUpdate = true; return normal
  }, [])
  useEffect(() => () => waterNormal.dispose(), [waterNormal])
  const ridges = useMemo(() => [-1, 1].map(side => ridgeGeometry(side)), [])
  useEffect(() => () => ridges.forEach(g => g.dispose()), [ridges])
  useEffect(() => {
    texture.colorSpace = THREE.SRGBColorSpace
    // This wide photographic matte covers the horizon band, not the zenith.
    texture.wrapS = THREE.RepeatWrapping; texture.repeat.set(2, 2); texture.offset.y = -.5; texture.needsUpdate = true
  }, [texture])
  useEffect(() => { ground.colorSpace = THREE.SRGBColorSpace; ground.wrapS = ground.wrapT = THREE.RepeatWrapping; ground.anisotropy = 8; ground.needsUpdate = true }, [ground])
  return <>
    <mesh position={[0, 0, -70]} rotation={[0, .5, 0]}>
      <sphereGeometry args={[1800, 64, 32]} />
      <meshBasicMaterial map={texture} side={THREE.BackSide} fog={false} toneMapped={false} />
    </mesh>
    {ridges.map((geometry, i) => <mesh key={i} geometry={geometry} receiveShadow><meshStandardMaterial map={ground} bumpMap={ground} bumpScale={.8} vertexColors roughness={1} metalness={0} side={THREE.DoubleSide} /></mesh>)}
    <Forest ridges={ridges} />
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -3.8, -45]}>
      <planeGeometry args={[4200, 4200]} />
      <MeshReflectorMaterial resolution={1024} blur={[6, 2]} mixBlur={.25} mixStrength={1.3} mirror={.75} color="#6f8984" roughness={.45} metalness={.15} normalMap={waterNormal} normalScale={new THREE.Vector2(.18, .18)} depthScale={.2} minDepthThreshold={.4} maxDepthThreshold={1.4} />
    </mesh>
  </>
}

function Forest({ ridges }: { ridges: THREE.BufferGeometry[] }) {
  const mesh = useRef<THREE.InstancedMesh>(null!)
  const geometry = useMemo(() => {
    const points: number[] = [], indices: number[] = []
    for (let level = 0; level < 15; level++) {
      const y = level / 15 - .5, r = (1 - level / 15) * (level % 2 ? .35 : 1)
      for (let j = 0; j < 10; j++) { const a = j / 10 * Math.PI * 2; points.push(Math.cos(a) * r * (.8 + .2 * Math.sin(j * 13 + level)), y + Math.sin(j * 8 + level) * .025, Math.sin(a) * r) }
    }
    points.push(0, .5, 0)
    for (let i = 0; i < 14; i++) for (let j = 0; j < 10; j++) { const a = i * 10 + j, b = i * 10 + (j + 1) % 10; indices.push(a, a + 10, b, b, a + 10, b + 10) }
    for (let j = 0; j < 10; j++) indices.push(140 + j, 150, 140 + (j + 1) % 10)
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(points, 3)); g.setIndex(indices); g.computeVertexNormals(); return g
  }, [])
  useEffect(() => () => geometry.dispose(), [geometry])
  const trees = useMemo(() => ridges.flatMap(geometry => {
    const p = geometry.attributes.position, result: THREE.Vector3[] = []
    for (let i = 0; i < p.count; i += 4) {
      if (p.getY(i) > -2 && p.getY(i) < 70) result.push(new THREE.Vector3(p.getX(i), p.getY(i), p.getZ(i)))
    }
    return result
  }), [ridges])
  useLayoutEffect(() => {
    const dummy = new THREE.Object3D()
    trees.forEach((position, i) => {
      const height = 3 + (Math.sin(i * 37) + 1) * 2.8
      dummy.position.copy(position); dummy.position.y += height / 2
      dummy.scale.set(.75 + height * .1, height, .75 + height * .1)
      dummy.rotation.y = i * 2.4; dummy.updateMatrix(); mesh.current.setMatrixAt(i, dummy.matrix)
      mesh.current.setColorAt(i, new THREE.Color(i % 3 ? "#2b4037" : "#405044"))
    })
    mesh.current.instanceMatrix.needsUpdate = true
  }, [trees])
  return <instancedMesh ref={mesh} args={[geometry, undefined, trees.length]} raycast={() => {}}>
    <meshStandardMaterial roughness={1} />
  </instancedMesh>
}

function Mist() {
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas"); canvas.width = canvas.height = 128
    const ctx = canvas.getContext("2d")!
    const gradient = ctx.createRadialGradient(64, 64, 3, 64, 64, 64)
    gradient.addColorStop(0, "rgba(222,230,225,.65)"); gradient.addColorStop(.4, "rgba(222,230,225,.22)"); gradient.addColorStop(1, "rgba(222,230,225,0)")
    ctx.fillStyle = gradient; ctx.fillRect(0, 0, 128, 128)
    return new THREE.CanvasTexture(canvas)
  }, [])
  useEffect(() => () => texture.dispose(), [texture])
  return <group>{Array.from({ length: 28 }, (_, i) => <mesh key={i} raycast={() => {}} position={[Math.sin(i * 3) * 40, i % 3 + 3, 220 - i * 21]} rotation={[-.08, Math.sin(i) * .2, 0]}>
    <planeGeometry args={[115, 24]} /><meshBasicMaterial map={texture} transparent opacity={.34} depthWrite={false} side={THREE.DoubleSide} fog={false} />
  </mesh>)}<mesh position={[9, 8, 136]} raycast={() => {}}><planeGeometry args={[65, 13]} /><meshBasicMaterial map={texture} transparent opacity={.72} depthWrite={false} side={THREE.DoubleSide} fog={false} /></mesh></group>
}

const pageCopy = [
  ["Source material", "When a cell", "finds damage.", "Cells monitor their proteins. A control signal connects detection to a protective response."],
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
  const textures = usePaperTextures(), group = useRef<THREE.Group>(null!), tilt = useRef(0)
  const { invalidate } = useThree()
  useFrame((_, dt) => {
    group.current.rotation.y = THREE.MathUtils.damp(group.current.rotation.y, -.25 + tilt.current, 5, dt)
    if (Math.abs(group.current.rotation.y + .25 - tilt.current) > .001) invalidate()
    group.current.children.forEach((child, index) => {
      const offset = index - activeCard, formation = pageFormation(scrollRef.current, index)
      const spread = smooth(scrollRef.current, .20, .29)
      const nextX = offset * (1.05 + spread * 1.7) + formation.fall * Math.sin(index * 2) * 25
      child.position.x = THREE.MathUtils.damp(child.position.x, nextX, 8, dt)
      if (Math.abs(child.position.x - nextX) > .001) invalidate()
      child.position.y = formation.y
      child.position.z = -offset * .75 - formation.fall * index * 5
      child.rotation.y = THREE.MathUtils.damp(child.rotation.y, offset < 0 ? -1.8 : spread * offset * .10 + (1 - formation.enter) * .6 + formation.fall * 1.8, 8, dt)
      child.rotation.x = formation.fall * (.3 + index * .2)
      child.visible = (offset >= 0 || child.rotation.y > -1.6) && formation.enter > 0 && formation.fall < 1
    })
  })
  return <group ref={group} position={[9, 19, 128]} rotation={[.06, -.25, -.035]} onPointerMove={event => { tilt.current = THREE.MathUtils.clamp(event.point.x - 9, -4, 4) * .012; invalidate() }} onPointerOut={() => { tilt.current = 0; invalidate() }} onClick={event => { if (scrollRef.current > .12 && scrollRef.current < .24) { event.stopPropagation(); onNext() } }}>
    {textures.map((texture, i) => <group key={i} position={[i * .45, 0, -i * .75]}>
      <mesh castShadow receiveShadow><boxGeometry args={[9, 12, .065]} /><meshStandardMaterial color="#f7f7f5" roughness={.9} /></mesh>
      <mesh position={[0, 0, .04]} receiveShadow><planeGeometry args={[8.98, 11.98]} /><meshStandardMaterial map={texture} roughness={.9} /></mesh>
    </group>)}
  </group>
}

function PaperAtrium({ scrollRef }: Progress) {
  const group = useRef<THREE.Group>(null!)
  const sheets = useMemo(() => [-1, 1].flatMap(side => Array.from({ length: 40 }, (_, layer) => paperRibbon(side, layer).translate(0, -9, 133.5))), [])
  useEffect(() => () => sheets.forEach(g => g.dispose()), [sheets])
  useFrame(() => {
    group.current.children.forEach((child, i) => {
      const { enter, exit } = architectureFormation(scrollRef.current, i % 16)
      const swirl = (1 - enter) * .35 + exit * .6
      const angle = i * .8 + swirl
      child.position.set(Math.sin(angle) * (1 - enter + exit) * 18, 9 + (1 - enter) * (85 + i * .8) - exit * 135, -133.5 + (1 - enter) * 30 - exit * 80)
      child.rotation.set(exit * .35, swirl * (i % 2 ? 1 : -1), (1 - enter + exit) * Math.sin(angle) * .18)
      child.scale.z = .4 + enter * (1 - exit) * .6
      child.visible = enter > 0 && exit < 1
    })
  })
  return <>
  <group ref={group}>
    {sheets.map((geometry, i) => <mesh key={i} geometry={geometry} castShadow receiveShadow><meshStandardMaterial color={i % 2 ? "#eceee7" : "#f7f7f5"} roughness={.9} metalness={0} side={THREE.DoubleSide} /></mesh>)}
  </group>
  <pointLight position={[0, 18, -115]} intensity={320} distance={85} color="#fff3dc" />
  </>
}

function DriftingPages({ scrollRef }: Progress) {
  const group = useRef<THREE.Group>(null!), textures = usePaperTextures()
  const geometry = useMemo(() => {
    const g = new THREE.PlaneGeometry(2, 2.8, 12, 8), p = g.attributes.position
    for (let i = 0; i < p.count; i++) p.setZ(i, Math.sin(p.getX(i) * 1.8) * .24)
    g.computeVertexNormals(); return g
  }, [])
  useEffect(() => () => geometry.dispose(), [geometry])
  useFrame(() => group.current.children.forEach((child, i) => {
    const { enter, exit } = architectureFormation(scrollRef.current, i % 16)
    const angle = i * 2.4 + enter * 5 + exit * 5, radius = 8 + Math.sin(i) * 3
    child.position.set(Math.sin(angle) * radius, 12 + (1 - enter) * (32 + i) - exit * 65 + Math.cos(angle) * 6, -62 - i * 5 - exit * 30)
    child.rotation.set(.4 + Math.sin(angle) * .5, angle, Math.cos(angle) * .3)
    child.visible = enter > 0 && exit < 1
  }))
  return <group ref={group}>{Array.from({ length: 30 }, (_, i) => <mesh geometry={geometry} key={i} castShadow><meshStandardMaterial map={textures[i % 5]} roughness={.9} side={THREE.DoubleSide} /></mesh>)}</group>
}

function ProductPortal({ scrollRef }: Progress) {
  const [active, setActive] = useState(false), activeRef = useRef(false)
  const group = useRef<THREE.Group>(null!)
  useFrame(() => {
    const { enter, exit } = architectureFormation(scrollRef.current, 5)
    group.current.position.y = 10 + (1 - enter) * 230 - exit * 170
    group.current.visible = enter > 0 && exit < 1
    const next = scrollRef.current > .57 && scrollRef.current < .705
    if (next !== activeRef.current) { activeRef.current = next; setActive(next) }
  })
  return <group ref={group} position={[1, 240, -136]}>
    <mesh position={[0, 0, -.18]} castShadow receiveShadow><boxGeometry args={[17.4, 12.8, .25]} /><meshStandardMaterial color="#f7f7f5" roughness={.9} /></mesh>
    <Html wrapperClass={styles.worldSurface} transform distanceFactor={6.5} center occlude zIndexRange={[12, 1]} style={{ width: 1050, pointerEvents: active ? "auto" : "none", backfaceVisibility: "hidden" }}>
      <section className={styles.worldProduct} aria-label="Interactive Lucent preview" aria-hidden={!active} {...(!active ? { inert: "" } : {})}>
        <div className={styles.worldProductHeading}><span>03 / LEARN WITH LUCENT</span><h2>From reading to reasoning.</h2></div>
        <Suspense fallback={<div className={styles.demoLoading}>Opening the learning preview…</div>}><ProductDemo /></Suspense>
      </section>
    </Html>
  </group>
}

// Product discoveries are surfaces in the same world, not full-screen sections.
function FeatureDiscoveries({ scrollRef }: Progress) {
  const group = useRef<THREE.Group>(null!)
  useFrame(() => {
    const { enter, exit } = architectureFormation(scrollRef.current, 10)
    group.current.position.y = (1 - enter) * 230 - exit * 170
    group.current.visible = enter > 0 && exit < 1
  })
  return <group ref={group} position={[0, 230, 0]}>
    <group position={[-7, 11, -100]} rotation={[0, .45, 0]}>
      <mesh position={[0, 0, -.12]}><boxGeometry args={[9.5, 7.2, .15]} /><meshStandardMaterial color="#eff1e9" roughness={.9} /></mesh>
      <Html transform center distanceFactor={5} occlude zIndexRange={[10, 1]} style={{ width: 720, pointerEvents: "none" }}>
        <article className={styles.worldDiscovery} aria-hidden="true" {...{ inert: "" }}><small>01 / SEE THE CONNECTION</small><h2>An idea, opened up.</h2><p>Follow the connection from detecting damage to taking action.</p><StructuredVisual spec={qualityControlVisual} initialStage={1} /></article>
      </Html>
    </group>
    <group position={[8, 12, -178]} rotation={[0, -.45, 0]}>
      <mesh position={[0, 0, -.12]}><boxGeometry args={[9.5, 7.2, .15]} /><meshStandardMaterial color="#eff1e9" roughness={.9} /></mesh>
      <Html transform center distanceFactor={5} occlude zIndexRange={[10, 1]} style={{ width: 720, pointerEvents: "none" }}>
        <article className={styles.worldDiscovery} aria-hidden="true"><small>03 / MAKE IT YOURS</small><h2>Understanding that stays.</h2><p>Explain it in your own words. Practise with less help. Return to the ideas that need another look.</p><div className={styles.discoverySteps}><span>Try an idea</span><span>Understand why</span><span>Apply it elsewhere</span></div><p>Not just the next question.<br />The next step in your understanding.</p></article>
      </Html>
    </group>
  </group>
}

function Overlook() {
  return <group position={[0, -1, -305]}>
    <mesh position={[0, -6, 7]} scale={[17, 6, 21]}><dodecahedronGeometry args={[1, 2]} /><meshStandardMaterial color="#46554e" roughness={1} flatShading /></mesh>
    <mesh receiveShadow position={[0, -.5, 5]}><boxGeometry args={[24, 1, 26]} /><meshStandardMaterial color="#737f7b" roughness={1} /></mesh>
    {/* A quiet, human-scale silhouette, facing away into the lake. */}
    <group position={[0, 0, -4]}>
      <mesh position={[0, 1.61, 0]} castShadow><sphereGeometry args={[.145, 12, 12]} /><meshStandardMaterial color="#182622" /></mesh>
      <mesh position={[0, 1.13, 0]} castShadow><capsuleGeometry args={[.19, .52, 4, 8]} /><meshStandardMaterial color="#182622" /></mesh>
      {[-1, 1].map(side => <group key={side}>
        <mesh position={[side * .12, .4, 0]} rotation={[0, 0, side * -.045]} castShadow><capsuleGeometry args={[.07, .68, 4, 8]} /><meshStandardMaterial color="#182622" /></mesh>
        <mesh position={[side * .26, 1.05, 0]} rotation={[0, 0, side * .12]} castShadow><capsuleGeometry args={[.06, .52, 4, 8]} /><meshStandardMaterial color="#182622" /></mesh>
      </group>)}
    </group>
  </group>
}

function AlpineSun() {
  const light = useRef<THREE.DirectionalLight>(null!), target = useMemo(() => new THREE.Object3D(), [])
  useFrame(({ camera }) => {
    light.current.position.set(camera.position.x - 40, 100, camera.position.z + 30)
    target.position.set(camera.position.x, 0, camera.position.z - 30); target.updateMatrixWorld()
  })
  return <><primitive object={target} /><directionalLight ref={light} target={target} intensity={1.7} color="#fffaf0" castShadow shadow-mapSize={[1024, 1024]} shadow-camera-left={-80} shadow-camera-right={80} shadow-camera-top={80} shadow-camera-bottom={-80} shadow-camera-far={250} shadow-normalBias={.08} shadow-bias={-.0001} /></>
}

export function HeroScene({ scrollRef, activeCard, onNext }: Progress & { activeCard: number; onNext: () => void }) {
  const journeyRef = useRef(scrollRef.current)
  return <>
    <color attach="background" args={["#d5dcde"]} /><fogExp2 attach="fog" args={["#d5dcde", .008]} />
    <CameraJourney scrollRef={scrollRef} journeyRef={journeyRef} />
    <ambientLight intensity={.6} color="#fffaf0" /><hemisphereLight args={["#e7efec", "#536957", .7]} />
    <AlpineSun />
    <Suspense fallback={null}><AlpineWorld /><DocumentSheets scrollRef={journeyRef} activeCard={activeCard} onNext={onNext} /></Suspense>
    <Mist /><group position={[24, 0, 0]}><Bvh firstHitOnly><PaperAtrium scrollRef={journeyRef} /></Bvh><DriftingPages scrollRef={journeyRef} /><FeatureDiscoveries scrollRef={journeyRef} /><ProductPortal scrollRef={journeyRef} /></group>
    <Overlook />
  </>
}
