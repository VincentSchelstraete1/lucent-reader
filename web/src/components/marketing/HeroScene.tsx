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
// SEEDED RNG — deterministic so instance jitter doesn't change on re-render
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
// CAMERA SPLINE — 8 keyframes, scroll progress → camera position + lookAt + FOV
// ─────────────────────────────────────────────────────────────────────────────
interface CamKf {
  p:  number
  px: number; py: number; pz: number   // position
  lx: number; ly: number; lz: number   // look-at target
  fov: number
}

const CAM: CamKf[] = [
  //   p     pos                        lookAt                    fov
  { p:0.00, px:  0, py:85, pz: 200, lx:  0, ly:28, lz: -80, fov:65 },
  { p:0.15, px:  0, py:55, pz: 155, lx:  0, ly:28, lz: -80, fov:67 },
  { p:0.30, px:  0, py:22, pz:  90, lx:  0, ly:28, lz: -80, fov:70 },
  { p:0.45, px:  0, py: 5, pz:   8, lx:  0, ly:28, lz: -80, fov:75 },
  { p:0.52, px:  0, py:14, pz: -60, lx:  0, ly:14, lz:-130, fov:68 },
  { p:0.65, px:  0, py:14, pz:-110, lx:  0, ly:14, lz:-175, fov:62 },
  { p:0.82, px:  0, py:14, pz:-165, lx:  0, ly:10, lz:-210, fov:58 },
  { p:1.00, px: -6, py:38, pz:-115, lx:  0, ly: 4, lz:-160, fov:55 },
]

// Module-level temp vectors — safe here because useFrame callbacks are sequential
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
  const s    = lt * lt * (3 - 2 * lt)           // smoothstep

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

// ─────────────────────────────────────────────────────────────────────────────
// ScrollCamera — moves the R3F camera according to scroll progress
// ─────────────────────────────────────────────────────────────────────────────
function ScrollCamera({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const { camera } = useThree()
  useEffect(() => { applyCamKf(0, camera) }, [camera])
  useFrame(() => { applyCamKf(Math.max(0, Math.min(1, scrollRef.current)), camera) })
  return null
}

// ─────────────────────────────────────────────────────────────────────────────
// FogController — animates THREE.FogExp2 density through the 4 stages
// ─────────────────────────────────────────────────────────────────────────────
function FogController({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const { scene } = useThree()

  useEffect(() => {
    scene.fog        = new THREE.FogExp2(0xb8cdd6, 0.006)
    scene.background = new THREE.Color(0x8ba0ae)
    return () => { scene.fog = null; scene.background = null }
  }, [scene])

  useFrame(() => {
    if (!(scene.fog instanceof THREE.FogExp2)) return
    const t = scrollRef.current
    let d: number
    if      (t < 0.15) d = 0.006
    else if (t < 0.45) d = THREE.MathUtils.lerp(0.006, 0.024, (t - 0.15) / 0.30)
    else if (t < 0.55) d = THREE.MathUtils.lerp(0.024, 0.003, (t - 0.45) / 0.10)
    else               d = 0.003
    scene.fog.density = d
  })

  return null
}

// ─────────────────────────────────────────────────────────────────────────────
// SkyDome — landscape JPEG wrapped on the inside of a large sphere
// ─────────────────────────────────────────────────────────────────────────────
function SkyDome() {
  const tex = useTexture("/lucent-landscape.jpg")
  useMemo(() => { tex.colorSpace = THREE.SRGBColorSpace }, [tex])
  return (
    <mesh>
      <sphereGeometry args={[480, 32, 16]} />
      <meshBasicMaterial map={tex} side={THREE.BackSide} />
    </mesh>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// LakePlane — highly reflective water surface at y = 0
// ─────────────────────────────────────────────────────────────────────────────
function LakePlane() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[600, 600]} />
      <meshStandardMaterial color="#253545" metalness={0.90} roughness={0.05} />
    </mesh>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// PaperMonolith — skyscraper-scale tower of 250 instanced paper sheets
//
// Each sheet is a thin BoxGeometry (width × depth, very small height).
// They are stacked vertically with tiny random jitter in X/Z/rotY so the
// stack reads as a real physical ream viewed from the side (paper edges)
// or from above (top page visible).
// ─────────────────────────────────────────────────────────────────────────────
const MONO_N     = 250
const MONO_W     = 3.2     // sheet width  (X)
const MONO_D     = 2.4     // sheet depth  (Z)
const MONO_T     = 0.022   // sheet thickness (Y)
const MONO_STEP  = 0.22    // Y spacing between sheet centres → total height ≈ 55 units

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
        (rng() - 0.5) * 0.14,           // tiny X jitter
        i * MONO_STEP + 0.5,             // stack from y≈0.5 upward
        -80 + (rng() - 0.5) * 0.12,     // tiny Z jitter around world z=-80
      )
      euler.set(
        (rng() - 0.5) * 0.006,
        (rng() - 0.5) * 0.042,          // slight twist per sheet
        (rng() - 0.5) * 0.006,
      )
      quat.setFromEuler(euler)
      mat4.compose(pos, quat, scl)
      mesh.setMatrixAt(i, mat4)
    }
    mesh.instanceMatrix.needsUpdate = true
  }, [rng])

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, MONO_N]} castShadow>
      <boxGeometry args={[MONO_W, MONO_T, MONO_D]} />
      <meshStandardMaterial color="#ece9de" roughness={0.88} metalness={0.02} />
    </instancedMesh>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// PaperCanyon — 36 tall sheets arranged radially → interior atrium (Stage 3)
//
// The sheets form a cylinder of radius 16 centred on the camera path.
// A warm point light above creates the glowing-cathedral look from the refs.
// All sheets share one material so opacity can be updated in one call.
// ─────────────────────────────────────────────────────────────────────────────
const CANYON_N  = 36
const CANYON_R  = 16
const CANYON_CZ = -125    // world Z of canyon centre

function PaperCanyon({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const groupRef = useRef<THREE.Group>(null!)
  const mat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#ece9de", roughness: 0.88, metalness: 0.02,
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
    mat.opacity = o * 0.94
    if (groupRef.current) groupRef.current.visible = o > 0.004
  })

  const sheets = useMemo(
    () =>
      Array.from({ length: CANYON_N }, (_, i) => {
        const θ = (i / CANYON_N) * Math.PI * 2
        return {
          key: i,
          pos: [
            Math.sin(θ) * CANYON_R,
            14,
            Math.cos(θ) * CANYON_R + CANYON_CZ,
          ] as [number, number, number],
          rot: [0, -θ, 0] as [number, number, number],
        }
      }),
    [],
  )

  return (
    <group ref={groupRef}>
      {sheets.map(s => (
        <mesh key={s.key} position={s.pos} rotation={s.rot} material={mat}>
          <planeGeometry args={[22, 44]} />
        </mesh>
      ))}
      {/* Warm top light — creates the "glowing opening" from the reference */}
      <pointLight
        position={[0, 42, CANYON_CZ]}
        intensity={20}
        color="#fff8e2"
        distance={100}
        decay={2}
      />
      {/* Cooler fill light from below */}
      <pointLight
        position={[0, -4, CANYON_CZ]}
        intensity={5}
        color="#c8dff0"
        distance={45}
        decay={2}
      />
    </group>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// PaperFlower — fanned-open sculpture over the alpine lake (Stage 4)
//
// 44 sheets arranged radially like PaperCanyon but with an upward tilt (rotX)
// that increases toward the outer sheets, creating an open-book / flower effect
// matching the Stage 4 reference image (the sculptural tree over the fjord).
// ─────────────────────────────────────────────────────────────────────────────
const FLOWER_N  = 44
const FLOWER_R  = 22
const FLOWER_CZ = -162    // world Z of flower centre

function PaperFlower({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const groupRef = useRef<THREE.Group>(null!)
  const mat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#ece9de", roughness: 0.85, metalness: 0.02,
        side: THREE.DoubleSide, transparent: true, opacity: 0,
      }),
    [],
  )

  useFrame(() => {
    const t = scrollRef.current
    const o = t < 0.78 ? 0 : t < 0.88 ? (t - 0.78) / 0.10 : 1
    mat.opacity = o * 0.90
    if (groupRef.current) groupRef.current.visible = o > 0.004
  })

  const sheets = useMemo(
    () =>
      Array.from({ length: FLOWER_N }, (_, i) => {
        const θ = (i / FLOWER_N) * Math.PI * 2
        // Progressive upward tilt: side sheets tilt more than front/back sheets
        const tiltX = -(Math.abs(Math.sin(θ * 0.5)) * 0.55 + 0.12)
        return {
          key: i,
          pos: [
            Math.sin(θ) * FLOWER_R,
            2,
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
        <mesh key={s.key} position={s.pos} rotation={s.rot} material={mat}>
          <planeGeometry args={[28, 42]} />
        </mesh>
      ))}
      <pointLight position={[0, 22, FLOWER_CZ]} intensity={10} color="#fff8e8" distance={80} decay={2} />
    </group>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// ProductDemoPortal — LucentProductDemo embedded as a drei Html transform plane
// inside the paper canyon.  Visible only when camera is inside (Stage 3).
//
// Using group.visible = false when outside Stage 3 so drei's Html also hides
// the DOM element.  Lazy-loaded on first activation via shouldRender flag.
// ─────────────────────────────────────────────────────────────────────────────
function ProductDemoPortal({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  const groupRef     = useRef<THREE.Group>(null!)
  const hasLoadedRef = useRef(false)
  const [shouldRender, setShouldRender] = useState(false)

  useFrame(() => {
    const t      = scrollRef.current
    const active = t > 0.50 && t < 0.92
    if (groupRef.current) groupRef.current.visible = active
    // Trigger React render once (avoids setShouldRender every frame)
    if (active && !hasLoadedRef.current) {
      hasLoadedRef.current = true
      setShouldRender(true)
    }
  })

  return (
    // scale={0.028}: 680 CSS px × 0.028 ≈ 19 Three.js units wide,
    // roughly 40% of viewport width when camera is ~40 units away in the canyon.
    <group ref={groupRef} position={[0, 14, -140]} scale={0.028}>
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
// HeroScene — assembles all R3F scene objects
// ─────────────────────────────────────────────────────────────────────────────
export function HeroScene({ scrollRef }: { scrollRef: React.MutableRefObject<number> }) {
  return (
    <>
      {/* Camera + atmosphere */}
      <ScrollCamera    scrollRef={scrollRef} />
      <FogController   scrollRef={scrollRef} />

      {/* Environment */}
      <Suspense fallback={null}>
        <SkyDome />
      </Suspense>
      <LakePlane />

      {/* Lighting */}
      <ambientLight intensity={0.55} color="#c8d8e2" />
      <directionalLight
        position={[40, 80, 60]}
        intensity={1.4}
        color="#fff6ee"
        castShadow
      />
      {/* Hemisphere: sky blue above, deep moss below */}
      <hemisphereLight args={["#9fc0ce", "#2e4038", 0.65]} />

      {/* Story elements */}
      <PaperMonolith />
      <PaperCanyon    scrollRef={scrollRef} />
      <PaperFlower    scrollRef={scrollRef} />
      <ProductDemoPortal scrollRef={scrollRef} />
    </>
  )
}
