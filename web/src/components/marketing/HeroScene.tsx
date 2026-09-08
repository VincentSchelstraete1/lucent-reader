/**
 * HeroScene.tsx
 * All @react-three/fiber scene objects for the Lucent landing hero.
 * Rendered inside a <Canvas> in SpatialStory.tsx.
 *
 * Stage layout (by scroll progress p):
 *   0.00–0.45  Stage 1+2: Alpine valley, PaperMonolith approaches from far ahead
 *   0.48–0.90  Stage 3:   Camera enters PaperCanyon; ProductDemoPortal visible
 *   0.78–1.00  Stage 4:   PaperFlower visible; wide pull-back
 */
import {
  lazy,
  Suspense,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useFrame, useThree } from "@react-three/fiber"
import { Html, useTexture } from "@react-three/drei"
import * as THREE from "three"

const ProductDemo = lazy(() =>
  import("./LucentProductDemo").then(m => ({ default: m.LucentProductDemo }))
)

// ─────────────────────────────────────────────────────────────────────────────
// SEEDED RNG
// ─────────────────────────────────────────────────────────────────────────────
function seededRng(seed: number): () => number {
  let s = seed >>> 0
  return function rng() {
    s ^= s << 13
    s ^= s >>> 17
    s ^= s << 5
    return (s >>> 0) / 0xffff_ffff
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CAMERA SPLINE — Z-coordinates pulled back for proper framing
// ─────────────────────────────────────────────────────────────────────────────
interface CamKf {
  p:  number
  px: number; py: number; pz: number   // position
  lx: number; ly: number; lz: number   // look-at target
  fov: number
}

const CAM: CamKf[] = [
  //   p     pos                        lookAt                    fov
  { p:0.00, px:  0, py:85, pz: 220, lx:  0, ly:28, lz: -80, fov:65 },
  { p:0.15, px:  0, py:55, pz: 170, lx:  0, ly:28, lz: -80, fov:67 },
  { p:0.30, px:  0, py:22, pz: 110, lx:  0, ly:28, lz: -80, fov:70 },
  { p:0.45, px:  0, py: 5, pz:  30, lx:  0, ly:28, lz: -80, fov:75 },
  // Stage 3: Canyon entrance (Z=-40 instead of -60)
  { p:0.52, px:  0, py:16, pz: -40, lx:  0, ly:16, lz:-140, fov:68 },
  // Stage 3: Canyon deep (Z=-75 instead of -110 to keep portal framed)
  { p:0.65, px:  0, py:16, pz: -75, lx:  0, ly:16, lz:-160, fov:62 },
  { p:0.82, px:  0, py:16, pz:-135, lx:  0, ly:12, lz:-210, fov:58 },
  { p:1.00, px: -6, py:38, pz:-100, lx:  0, ly: 6, lz:-170, fov:55 },
]

const _tp = new THREE.Vector3()
const _tl = new THREE.Vector3()

function applyCamKf(t: number, camera: THREE.Camera) {
  const kfs = CAM
  let ai = 0
  for (let i = 0; i < kfs.length - 1; i++) {
    if (t >= kfs[i + 1].p) ai = i + 1
  }
  const a = kfs[ai]
  const b = kfs[Math.min(ai + 1, kfs.length - 1)]
  const span = b.p - a.p
  const lt   = span > 0 ? Math.max(0, Math.min(1, (t - a.p) / span)) : 1
  const s    = lt * lt * (3 - 2 * lt)

  _tp.set(a.px+(b.px-a.px)*s, a.py+(b.py-a.py)*s, a.pz+(b.pz-a.pz)*s)
  _tl.set(a.lx+(b.lx-a.lx)*s, a.ly+(b.ly-a.ly)*s, a.lz+(b.lz-a.lz)*s)
  camera.position.copy(_tp)
  camera.lookAt(_tl)

  if ("fov" in camera) {
    const pc  = camera as THREE.PerspectiveCamera
    const fov = a.fov + (b.fov - a.fov) * s
    if (Math.abs(pc.fov - fov) > 0.05) { pc.fov = fov; pc.updateProjectionMatrix() }
  }
}

function ScrollCamera({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const { camera } = useThree()
  useEffect(() => { applyCamKf(0, camera) }, [camera])
  useFrame(() => { applyCamKf(Math.max(0, Math.min(1, scrollRef.current)), camera) })
  return null
}

// ─────────────────────────────────────────────────────────────────────────────
// FogController — updated to matching photographic alpine misty colors
// ─────────────────────────────────────────────────────────────────────────────
function FogController({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const { scene } = useThree()

  useEffect(() => {
    scene.fog        = new THREE.FogExp2("#d5dcde", 0.008)
    scene.background = new THREE.Color("#c1cdd4") // Bright misty backdrop
    return () => { scene.fog = null; scene.background = null }
  }, [scene])

  useFrame(() => {
    if (!(scene.fog instanceof THREE.FogExp2)) return
    const t = scrollRef.current
    let d: number
    if      (t < 0.15) d = 0.008
    else if (t < 0.45) d = THREE.MathUtils.lerp(0.008, 0.020, (t - 0.15) / 0.30)
    else if (t < 0.55) d = THREE.MathUtils.lerp(0.020, 0.004, (t - 0.45) / 0.10)
    else               d = 0.004
    scene.fog.density = d
  })

  return null
}

// ─────────────────────────────────────────────────────────────────────────────
// SkyDome — ignoring fog so it acts as a true skybox
// ─────────────────────────────────────────────────────────────────────────────
function SkyDome() {
  const tex = useTexture("/lucent-landscape.jpg")
  useMemo(() => { tex.colorSpace = THREE.SRGBColorSpace }, [tex])
  return (
    <mesh>
      <sphereGeometry args={[480, 64, 32]} />
      <meshBasicMaterial map={tex} side={THREE.BackSide} fog={false} toneMapped={false} />
    </mesh>
  )
}

function LakePlane() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[800, 800]} />
      <meshStandardMaterial color="#253545" metalness={0.92} roughness={0.08} />
    </mesh>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// PaperMonolith
// ─────────────────────────────────────────────────────────────────────────────
const MONO_N     = 250
const MONO_W     = 3.2
const MONO_D     = 2.4
const MONO_T     = 0.022
const MONO_STEP  = 0.22

function PaperMonolith() {
  const ref = useRef<THREE.InstancedMesh>(null!)
  const rng = useMemo(() => seededRng(42), [])

  useLayoutEffect(() => {
    const mesh   = ref.current
    if (!mesh) return
    const mat4  = new THREE.Matrix4()
    const pos   = new THREE.Vector3()
    const quat  = new THREE.Quaternion()
    const scl   = new THREE.Vector3(1, 1, 1)
    const euler = new THREE.Euler()

    for (let i = 0; i < MONO_N; i++) {
      pos.set(
        (rng() - 0.5) * 0.14,
        i * MONO_STEP + 0.5,
        -80 + (rng() - 0.5) * 0.12,
      )
      euler.set(
        (rng() - 0.5) * 0.006,
        (rng() - 0.5) * 0.042,
        (rng() - 0.5) * 0.006,
      )
      quat.setFromEuler(euler)
      mat4.compose(pos, quat, scl)
      mesh.setMatrixAt(i, mat4)
    }
    mesh.instanceMatrix.needsUpdate = true
  }, [rng])

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, MONO_N]} castShadow receiveShadow>
      <boxGeometry args={[MONO_W, MONO_T, MONO_D]} />
      <meshStandardMaterial color="#f7f7f5" roughness={0.92} metalness={0} />
    </instancedMesh>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// PaperCanyon — elegant, smooth curved sheets framing the portal
// ─────────────────────────────────────────────────────────────────────────────
const CANYON_CZ = -140

function PaperCanyon({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const groupRef = useRef<THREE.Group>(null!)
  const mat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#f7f7f5", roughness: 0.94, metalness: 0.0,
        side: THREE.DoubleSide, transparent: true, opacity: 0,
      }),
    [],
  )

  useFrame(() => {
    const t = scrollRef.current
    let o = 0
    if      (t > 0.48 && t < 0.57) o = (t - 0.48) / 0.09
    else if (t >= 0.57 && t <= 0.80) o = 1
    else if (t > 0.80 && t < 0.90)  o = 1 - (t - 0.80) / 0.10
    mat.opacity = o * 1.0
    if (groupRef.current) groupRef.current.visible = o > 0.004
  })

  // 6 large sweeping curved sheets (3 left, 3 right) framing the center
  const sheets = useMemo(() => [
    // Left sheets (radius, height, thetaStart, thetaLength, y, rotY)
    { r: 24, h: 56, ts: Math.PI * 0.65, tl: Math.PI * 0.30, y: 14, ry: -0.1 },
    { r: 28, h: 64, ts: Math.PI * 0.60, tl: Math.PI * 0.35, y: 18, ry:  0.0 },
    { r: 34, h: 74, ts: Math.PI * 0.55, tl: Math.PI * 0.40, y: 24, ry:  0.1 },
    // Right sheets
    { r: 24, h: 56, ts: Math.PI * 0.05, tl: Math.PI * 0.30, y: 14, ry:  0.1 },
    { r: 28, h: 64, ts: Math.PI * 0.05, tl: Math.PI * 0.35, y: 18, ry:  0.0 },
    { r: 34, h: 74, ts: Math.PI * 0.05, tl: Math.PI * 0.40, y: 24, ry: -0.1 },
  ], [])

  return (
    <group ref={groupRef} position={[0, 0, CANYON_CZ]}>
      {sheets.map((s, i) => (
        <mesh key={i} position={[0, s.y, 0]} rotation={[0, s.ry, 0]} castShadow receiveShadow material={mat}>
          <cylinderGeometry args={[s.r, s.r, s.h, 32, 1, true, s.ts, s.tl]} />
        </mesh>
      ))}
      
      {/* Warm top ambient occlusion light catching the upper curves */}
      <pointLight position={[0, 45, 10]} intensity={18} color="#fffaf0" distance={120} decay={2} castShadow />
      <pointLight position={[0, -10, 20]} intensity={6} color="#dbe5eb" distance={80} decay={2} />
    </group>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// PaperFlower
// ─────────────────────────────────────────────────────────────────────────────
const FLOWER_N  = 24
const FLOWER_R  = 28
const FLOWER_CZ = -180

function PaperFlower({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const groupRef = useRef<THREE.Group>(null!)
  const mat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#f7f7f5", roughness: 0.90, metalness: 0.0,
        side: THREE.DoubleSide, transparent: true, opacity: 0,
      }),
    [],
  )

  useFrame(() => {
    const t = scrollRef.current
    const o = t < 0.78 ? 0 : t < 0.88 ? (t - 0.78) / 0.10 : 1
    mat.opacity = o * 1.0
    if (groupRef.current) groupRef.current.visible = o > 0.004
  })

  const sheets = useMemo(
    () =>
      Array.from({ length: FLOWER_N }, (_, i) => {
        const θ = (i / FLOWER_N) * Math.PI * 2
        const tiltX = -(Math.abs(Math.sin(θ * 0.5)) * 0.6 + 0.15)
        return {
          key: i,
          pos: [
            Math.sin(θ) * FLOWER_R,
            6,
            Math.cos(θ) * FLOWER_R + FLOWER_CZ,
          ] as [number, number, number],
          rot: [tiltX, -θ, 0] as [number, number, number],
        }
      }),
    [],
  )

  return (
    <group ref={groupRef}>
      {sheets.map(s => (
        <mesh key={s.key} position={s.pos} rotation={s.rot} material={mat} castShadow receiveShadow>
          {/* Smooth plane geometry for the flower petals */}
          <planeGeometry args={[22, 48, 4, 4]} />
        </mesh>
      ))}
      <pointLight position={[0, 30, FLOWER_CZ]} intensity={14} color="#fffcf5" distance={100} decay={2} />
    </group>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// ProductDemoPortal
// ─────────────────────────────────────────────────────────────────────────────
function ProductDemoPortal({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const groupRef     = useRef<THREE.Group>(null!)
  const hasLoadedRef = useRef(false)
  const [shouldRender, setShouldRender] = useState(false)

  useFrame(() => {
    const t      = scrollRef.current
    const active = t > 0.50 && t < 0.92
    if (groupRef.current) groupRef.current.visible = active
    if (active && !hasLoadedRef.current) {
      hasLoadedRef.current = true
      setShouldRender(true)
    }
  })

  return (
    <group ref={groupRef} position={[0, 16, -145]} scale={0.032}>
      <Html
        transform
        occlude="blending"
        center
        zIndexRange={[16, 0]}
        style={{ width: "680px", pointerEvents: "auto", userSelect: "auto" }}
      >
        {shouldRender && (
          <Suspense
            fallback={
              <div
                style={{
                  width: 680, height: 280,
                  display: "grid", placeItems: "center",
                  background: "#faf8f0", borderRadius: 8,
                  fontFamily: "system-ui", color: "#3b4039", fontSize: 14,
                }}
              >
                Opening the learning preview…
              </div>
            }
          >
            <ProductDemo />
          </Suspense>
        )}
      </Html>
    </group>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// HeroScene
// ─────────────────────────────────────────────────────────────────────────────
export function HeroScene({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  return (
    <>
      <ScrollCamera    scrollRef={scrollRef} />
      <FogController   scrollRef={scrollRef} />

      <Suspense fallback={null}>
        <SkyDome />
      </Suspense>
      <LakePlane />

      {/* Warmer, softer lighting reflecting the alpine mood */}
      <ambientLight intensity={0.8} color="#dbe5eb" />
      <directionalLight
        position={[40, 90, 60]}
        intensity={2.2}
        color="#fffaf0"
        castShadow
        shadow-bias={-0.0001}
      />
      <hemisphereLight args={["#c1cdd4", "#304036", 0.8]} />

      <PaperMonolith />
      <PaperCanyon    scrollRef={scrollRef} />
      <PaperFlower    scrollRef={scrollRef} />
      <ProductDemoPortal scrollRef={scrollRef} />
    </>
  )
}
