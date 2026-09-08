import * as THREE from "three"
import { cameraPose, smooth } from "./flythrough"

export const OPENING_END = .075

// Bounded depth for the photographic projection. The image, not this smooth
// depth envelope, supplies all mountain/forest detail and silhouettes.
export function openingDepth(u: number, v: number) {
  const foreground = (1 - smooth(v, .03, .26)) * (.4 + .6 * smooth(Math.abs(u - .5), .1, .4))
  const shore = (1 - smooth(v, .38, .65)) * smooth(Math.abs(u - .5), .13, .48)
  const water = 1 - smooth(v, .05, .46)
  return Math.max(140, 950 - foreground * 560 - shore * 180 - water * 240)
}

export function openingCamera(progress: number, time: number) {
  if (progress >= OPENING_END) return cameraPose(progress)
  const original = cameraPose(progress), start = cameraPose(0)
  const blend = smooth(progress, .045, OPENING_END)
  const forward = new THREE.Vector3().subVectors(start.target, start.position).normalize()
  const glide = forward.multiplyScalar(Math.min(progress / .045, 1) * 9)
  glide.x += Math.min(progress / .045, 1) * 1.1 + Math.sin(time * .14) * .16
  glide.y += Math.sin(time * .19) * .08
  return {
    position: start.position.clone().add(glide).lerp(original.position, blend),
    target: start.target.clone().add(glide).lerp(original.target, blend),
    roll: original.roll * blend,
  }
}
