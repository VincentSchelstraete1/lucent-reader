/* eslint-disable react/no-unknown-property */
"use client"

// Adapted from React Bits' Lanyard component:
//   https://reactbits.dev/components/lanyard
//   https://github.com/DavidHDev/react-bits/blob/main/src/content/Components/Lanyard/Lanyard.jsx
// Copyright (c) 2026 David Haz - MIT + Commons Clause License Condition v1.0
// (used here as one component inside the Lucent product, per that license;
// not sold, sublicensed, or redistributed as a standalone package).
//
// The physics/rope/drag logic below is React Bits' own approach, ported to
// TypeScript. What's Lucent-specific: the card/cord textures (passed in as
// props, see LucentLanyard below) and matte (non-chrome, no clearcoat)
// material tuning on the card face.
import { useEffect, useMemo, useRef, useState } from "react"
import { Canvas, extend, useFrame, type ThreeElements } from "@react-three/fiber"
import { useGLTF, useTexture, Environment, Lightformer } from "@react-three/drei"
import {
  BallCollider,
  CuboidCollider,
  Physics,
  RigidBody,
  useRopeJoint,
  useSphericalJoint,
  type RapierRigidBody
} from "@react-three/rapier"
import { MeshLineGeometry, MeshLineMaterial } from "meshline"
import * as THREE from "three"
import styles from "./lucentLanyard.module.css"

extend({ MeshLineGeometry, MeshLineMaterial })

declare module "@react-three/fiber" {
  interface ThreeElements {
    meshLineGeometry: ThreeElements["mesh"]
    meshLineMaterial: any
  }
}

const CARD_GLB_PATH = "/models/lanyard-card.glb"
const DEFAULT_FRONT_IMAGE = "/flowers/lanyard-card-front.png"
const DEFAULT_LANYARD_IMAGE = "/flowers/lanyard-cord.png"

// useTexture must be called unconditionally (hooks rule) even when a face
// image isn't supplied - a 1x1 transparent pixel stands in so nothing is
// drawn for that face, same trick React Bits' own source uses.
const BLANK_PIXEL =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

const FRONT_UV_RECT = { x: 0, y: 0, w: 0.5, h: 0.755 }
const BACK_UV_RECT = { x: 0.5, y: 0, w: 0.5, h: 0.757 }

export interface LucentLanyardProps {
  frontImage?: string | null
  backImage?: string | null
  imageFit?: "cover" | "contain"
  lanyardImage?: string | null
  lanyardWidth?: number
  gravity?: [number, number, number]
  /** Minimizes the initial drop/swing-in for prefers-reduced-motion. Drag stays fully available regardless - it's user-initiated, not automatic motion. */
  reduced?: boolean
}

export function LucentLanyard({
  frontImage = DEFAULT_FRONT_IMAGE,
  backImage = DEFAULT_FRONT_IMAGE,
  imageFit = "cover",
  lanyardImage = DEFAULT_LANYARD_IMAGE,
  lanyardWidth = 1,
  gravity = [0, -40, 0],
  reduced = false
}: LucentLanyardProps) {
  const [isMobile, setIsMobile] = useState(() => typeof window !== "undefined" && window.innerWidth < 768)

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  return (
    <div className={styles.wrapper}>
      <Canvas
        camera={{ position: [0, 0, 13], fov: 20 }}
        dpr={[1, isMobile ? 1.5 : 2]}
        gl={{ alpha: true }}
        onCreated={({ gl, size }) => {
          gl.setClearColor(new THREE.Color(0x000000), 0)
          if (import.meta.env.DEV) {
            console.log("[LucentLanyard] canvas initialized", size)
            if (size.width === 0 || size.height === 0) {
              console.error("[LucentLanyard] canvas has zero size - its parent container needs an explicit width/height")
            }
          }
        }}
      >
        <ambientLight intensity={Math.PI} />
        <Physics gravity={gravity} timeStep={isMobile ? 1 / 30 : 1 / 60}>
          <Band
            isMobile={isMobile}
            reduced={reduced}
            frontImage={frontImage}
            backImage={backImage}
            imageFit={imageFit}
            lanyardImage={lanyardImage}
            lanyardWidth={lanyardWidth}
          />
        </Physics>
        <Environment blur={0.75}>
          <Lightformer intensity={2} color="white" position={[0, -1, 5]} rotation={[0, 0, Math.PI / 3]} scale={[100, 0.1, 1]} />
          <Lightformer intensity={3} color="white" position={[-1, -1, 1]} rotation={[0, 0, Math.PI / 3]} scale={[100, 0.1, 1]} />
          <Lightformer intensity={3} color="white" position={[1, 1, 1]} rotation={[0, 0, Math.PI / 3]} scale={[100, 0.1, 1]} />
          <Lightformer intensity={10} color="white" position={[-10, 0, 14]} rotation={[0, Math.PI / 2, Math.PI / 3]} scale={[100, 10, 1]} />
        </Environment>
      </Canvas>
    </div>
  )
}

function Band({
  isMobile,
  reduced,
  frontImage,
  backImage,
  imageFit,
  lanyardImage,
  lanyardWidth
}: {
  isMobile: boolean
  reduced: boolean
  frontImage: string | null
  backImage: string | null
  imageFit: "cover" | "contain"
  lanyardImage: string | null
  lanyardWidth: number
}) {
  const maxSpeed = 50
  const minSpeed = 0

  const band = useRef<THREE.Mesh>(null)
  const fixed = useRef<RapierRigidBody>(null)
  const j1 = useRef<RapierRigidBody & { lerped?: THREE.Vector3 }>(null)
  const j2 = useRef<RapierRigidBody & { lerped?: THREE.Vector3 }>(null)
  const j3 = useRef<RapierRigidBody>(null)
  const card = useRef<RapierRigidBody>(null)

  const vec = new THREE.Vector3()
  const ang = new THREE.Vector3()
  const rot = new THREE.Vector3()
  const dir = new THREE.Vector3()

  const segmentProps = {
    type: "dynamic" as const,
    canSleep: true,
    colliders: false as const,
    angularDamping: 4,
    linearDamping: 4
  }

  const { nodes, materials } = useGLTF(CARD_GLB_PATH) as unknown as {
    nodes: Record<string, THREE.Mesh>
    materials: Record<string, THREE.MeshStandardMaterial & { map?: THREE.Texture }>
  }

  if (!nodes.card || !nodes.clip || !nodes.clamp || !materials.base || !materials.metal) {
    // Fail loudly instead of silently rendering nothing - caught by
    // LanyardErrorBoundary in AuthPage.
    throw new Error(
      `[LucentLanyard] card.glb is missing expected nodes/materials (card/clip/clamp/base/metal). Got nodes: ${Object.keys(nodes).join(", ")}`
    )
  }

  useEffect(() => {
    if (import.meta.env.DEV) console.log("[LucentLanyard] band mounted, card rigid body available:", !!card.current)
  }, [])

  const texture = useTexture(lanyardImage || DEFAULT_LANYARD_IMAGE)
  const frontTex = useTexture(frontImage || BLANK_PIXEL)
  const backTex = useTexture(backImage || BLANK_PIXEL)

  const cardMap = useMemo(() => {
    const baseMap = materials.base.map!
    if (!frontImage && !backImage) return baseMap

    const baseImg = baseMap.image as HTMLImageElement
    const W = baseImg.width
    const H = baseImg.height
    const canvas = document.createElement("canvas")
    canvas.width = W
    canvas.height = H
    const ctx = canvas.getContext("2d")
    if (!ctx) return baseMap
    ctx.drawImage(baseImg, 0, 0, W, H)

    const drawFitted = (img: HTMLImageElement, rect: { x: number; y: number; w: number; h: number }) => {
      const rx = rect.x * W
      const ry = rect.y * H
      const rw = rect.w * W
      const rh = rect.h * H
      const pick = imageFit === "contain" ? Math.min : Math.max
      const scale = pick(rw / img.width, rh / img.height)
      const dw = img.width * scale
      const dh = img.height * scale
      const dx = rx + (rw - dw) / 2
      const dy = ry + (rh - dh) / 2
      ctx.save()
      ctx.beginPath()
      ctx.rect(rx, ry, rw, rh)
      ctx.clip()
      ctx.drawImage(img, dx, dy, dw, dh)
      ctx.restore()
    }

    if (frontImage && frontTex.image) drawFitted(frontTex.image as HTMLImageElement, FRONT_UV_RECT)
    if (backImage && backTex.image) drawFitted(backTex.image as HTMLImageElement, BACK_UV_RECT)

    const composite = new THREE.CanvasTexture(canvas)
    composite.colorSpace = THREE.SRGBColorSpace
    composite.flipY = baseMap.flipY
    composite.anisotropy = 16
    composite.needsUpdate = true
    return composite
  }, [frontImage, backImage, imageFit, frontTex, backTex, materials.base.map])

  const [curve] = useState(
    () => new THREE.CatmullRomCurve3([new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()])
  )
  const [dragged, drag] = useState<THREE.Vector3 | false>(false)
  const [hovered, hover] = useState(false)

  useRopeJoint(fixed, j1, [[0, 0, 0], [0, 0, 0], 1])
  useRopeJoint(j1, j2, [[0, 0, 0], [0, 0, 0], 1])
  useRopeJoint(j2, j3, [[0, 0, 0], [0, 0, 0], 1])
  useSphericalJoint(j3, card, [
    [0, 0, 0],
    [0, 1.5, 0]
  ])

  useEffect(() => {
    if (hovered) {
      document.body.style.cursor = dragged ? "grabbing" : "grab"
      return () => void (document.body.style.cursor = "auto")
    }
  }, [hovered, dragged])

  useFrame((state, delta) => {
    if (dragged) {
      vec.set(state.pointer.x, state.pointer.y, 0.5).unproject(state.camera)
      dir.copy(vec).sub(state.camera.position).normalize()
      vec.add(dir.multiplyScalar(state.camera.position.length()))
      ;[card, j1, j2, j3, fixed].forEach((ref) => ref.current?.wakeUp())
      card.current?.setNextKinematicTranslation({
        x: vec.x - dragged.x,
        y: vec.y - dragged.y,
        z: vec.z - dragged.z
      })
    }
    if (fixed.current) {
      ;[j1, j2].forEach((ref) => {
        if (!ref.current) return
        if (!ref.current.lerped) ref.current.lerped = new THREE.Vector3().copy(ref.current.translation())
        const clampedDistance = Math.max(0.1, Math.min(1, ref.current.lerped.distanceTo(ref.current.translation())))
        ref.current.lerped.lerp(ref.current.translation(), delta * (minSpeed + clampedDistance * (maxSpeed - minSpeed)))
      })
      curve.points[0].copy(j3.current!.translation())
      curve.points[1].copy(j2.current!.lerped!)
      curve.points[2].copy(j1.current!.lerped!)
      curve.points[3].copy(fixed.current.translation())
      ;(band.current!.geometry as any).setPoints(curve.getPoints(isMobile ? 16 : 32))
      ang.copy(card.current!.angvel() as unknown as THREE.Vector3)
      rot.copy(card.current!.rotation() as unknown as THREE.Vector3)
      card.current!.setAngvel({ x: ang.x, y: ang.y - rot.y * 0.25, z: ang.z }, true)
    }
  })

  curve.curveType = "chordal"
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping

  // Normally the rope starts laid out horizontally and swings/drops into
  // its hanging rest position under gravity - that fall is the entrance
  // "wow" moment. Under reduced motion we start it much closer to where it
  // will settle so there's barely any automatic swinging, without removing
  // the physics or the drag interaction (which is user-initiated, not
  // automatic, so it stays fully active either way).
  const spread = reduced ? 0.08 : 0.5

  return (
    <>
      <group position={[0, 4, 0]}>
        <RigidBody ref={fixed} {...segmentProps} type="fixed" />
        <RigidBody position={[spread, 0, 0]} ref={j1} {...segmentProps}>
          <BallCollider args={[0.1]} />
        </RigidBody>
        <RigidBody position={[spread * 2, 0, 0]} ref={j2} {...segmentProps}>
          <BallCollider args={[0.1]} />
        </RigidBody>
        <RigidBody position={[spread * 3, 0, 0]} ref={j3} {...segmentProps}>
          <BallCollider args={[0.1]} />
        </RigidBody>
        <RigidBody
          position={[spread * 4, 0, 0]}
          ref={card}
          {...segmentProps}
          type={dragged ? "kinematicPosition" : "dynamic"}
        >
          <CuboidCollider args={[0.8, 1.125, 0.01]} />
          <group
            scale={2.25}
            position={[0, -1.2, -0.05]}
            onPointerOver={() => hover(true)}
            onPointerOut={() => hover(false)}
            onPointerUp={(e) => {
              ;(e.target as Element).releasePointerCapture(e.pointerId)
              drag(false)
            }}
            onPointerDown={(e) => {
              ;(e.target as Element).setPointerCapture(e.pointerId)
              drag(new THREE.Vector3().copy(e.point).sub(vec.copy(card.current!.translation() as unknown as THREE.Vector3)))
            }}
          >
            <mesh geometry={nodes.card.geometry}>
              <meshPhysicalMaterial
                map={cardMap}
                map-anisotropy={16}
                clearcoat={0}
                roughness={0.92}
                metalness={0.06}
              />
            </mesh>
            <mesh geometry={nodes.clip.geometry} material={materials.metal} material-roughness={0.6} material-color="#8a8578" />
            <mesh geometry={nodes.clamp.geometry} material={materials.metal} material-roughness={0.6} material-color="#8a8578" />
          </group>
        </RigidBody>
      </group>
      <mesh ref={band}>
        <meshLineGeometry />
        <meshLineMaterial
          color="white"
          depthTest={false}
          resolution={isMobile ? [1000, 2000] : [1000, 1000]}
          useMap
          map={texture}
          repeat={[-4, 1]}
          lineWidth={lanyardWidth}
        />
      </mesh>
    </>
  )
}

useGLTF.preload(CARD_GLB_PATH)
