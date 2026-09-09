import * as THREE from 'three'

export const smooth = (p: number, start: number, end: number) => THREE.MathUtils.smoothstep(p, start, end)
// All encounters have permanent locations in this one alpine world.
export const WORLD = { hero: [4, 22, 190], visual: [-8, 18, 150], product: [2, 16, 121], overlook: [0, 8, 51] } as const
export const CAMERA_KEYS = [
  { p: 0, pos: [-8,28,240], look: [0,14,150] },
  { p: .05, pos: [-7,27.5,234], look: [1,14,144] },
  { p: .12, pos: [-5,27,225], look: [1,20,145] },
  { p: .20, pos: [-4,26,215], look: [1,23,140] },
  { p: .28, pos: [-3.5,26,213], look: [1,23,138] },
  { p: .34, pos: [-7,26,202], look: [0,22,130] },
  { p: .40, pos: [-8,25,187], look: [0,20,118] },
  { p: .48, pos: [-2,23,172], look: [3,18,106] },
  { p: .56, pos: [1,20,154], look: [2,18,93] },
  { p: .62, pos: [1,19,145], look: [2,19,82] },
  { p: .67, pos: [1.2,19,144.5], look: [2,19,82] },
  { p: .705, pos: [-11,20,130], look: [0,19,75] },
  { p: .74, pos: [-10,21,115], look: [0,18,62] },
  { p: .82, pos: [-3,23,94], look: [2,17,32] },
  { p: .92, pos: [0,20,79], look: [0,14,10] },
  { p: 1, pos: [0,17,73], look: [0,14,-8] },
]
const vector = (v: readonly number[]) => new THREE.Vector3(v[0], v[1], v[2])
const route = new THREE.CatmullRomCurve3(CAMERA_KEYS.map(k => vector(k.pos)), false, 'catmullrom', .25)
// Gentle authored look changes preserve the photographic projection's horizon
// while lateral camera movement produces the larger passing parallax.
const gaze = new THREE.CatmullRomCurve3(CAMERA_KEYS.map(k => vector(k.pos).add(new THREE.Vector3(8 + Math.sin(k.p * Math.PI * 2) * .8, -14 + Math.sin(k.p * Math.PI * 2) * .6, -90))), false, 'catmullrom', .25)
export function cameraPose(progress: number) {
  const p = THREE.MathUtils.clamp(progress, 0, 1)
  let i = 0
  while (i < CAMERA_KEYS.length - 2 && p > CAMERA_KEYS[i + 1].p) i++
  const t = (i + (p - CAMERA_KEYS[i].p) / (CAMERA_KEYS[i + 1].p - CAMERA_KEYS[i].p)) / (CAMERA_KEYS.length - 1)
  return { position: route.getPoint(t), target: gaze.getPoint(t), roll: Math.sin(p * Math.PI * 3) * .009 }
}

// Each sheet begins at its own distant cloud location and follows a curved
// trajectory into the same stack. Geometry moves; opacity never spawns a stack.
const starts = [[-16,90,94], [25,110,104], [-27,76,130], [20,90,150], [5,118,80]]
export function pagePose(progress: number, index: number, active = 0) {
  const enter = smooth(progress, .065 + index * .008, .19 + index * .009)
  const depart = smooth(progress, .30 + index * .005, .425 + index * .007)
  const offset = index - active
  const start = vector(starts[index]), end = vector(WORLD.hero).add(new THREE.Vector3(offset * 1.03, offset * .13, -offset * .85))
  const position = start.lerp(end, enter)
  position.x += Math.sin(enter * Math.PI) * (index % 2 ? 12 : -8)
  position.z += Math.sin(enter * Math.PI) * (index === 2 ? 42 : 12)
  position.y += Math.sin(enter * Math.PI) * (index % 2 ? 6 : -7)
  position.x += depart * (index % 2 ? 24 : -26)
  position.y -= depart * (28 + index * 4)
  position.z -= depart * (14 + index * 6)
  return {
    position, enter, depart,
    rotation: new THREE.Euler(-.035+(1-enter)*(.4+index*.16)+depart*.8, -.25+Math.max(0,offset)*.035+(1-enter)*(index%2?-.9:.8)+depart*(index%2?1.2:-1.5)+(offset<0?-1.9:0), -.035+Math.max(0,offset)*.018+(1-enter)*Math.sin(index*2)*.5+depart*.6),
    visible: progress > .045 && depart < 1 && offset >= 0,
  }
}

export function passingPagePose(p: number, index: number) {
  const t = smooth(p, .055 + index * .025, .22 + index * .024)
  return {
    position: new THREE.Vector3((index%2?1:-1)*(10+Math.sin(t*Math.PI)*4), 48-t*32+index%3*4, 132+index*8+t*97),
    rotation: new THREE.Euler(-.4+t*.8, .35+index*.4+t*.7, Math.sin(index)*.3),
    visible: t > 0 && t < 1,
  }
}
