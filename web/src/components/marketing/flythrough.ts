import * as THREE from "three"

// The knots are authored in world metres. Scroll changes the camera's position
// and gaze, never its FOV. Natural water/terrain exists for the entire journey.
export const CAMERA_KEYS = [
  { p: 0, pos: [-8, 28, 240], look: [0, 14, 150] },
  { p: .06, pos: [-5, 25, 200], look: [5, 17, 130] },
  { p: .12, pos: [-10, 23, 167], look: [1, 18, 112] },
  { p: .18, pos: [-8, 22, 155], look: [6, 17, 120] },
  { p: .22, pos: [-8, 22, 145], look: [9, 10, 120] },
  { p: .26, pos: [-4, 20, 130], look: [10, 4, 80] },
  { p: .30, pos: [8, 18, 70], look: [0, 10, 0] },
  { p: .40, pos: [-4, 12, 0], look: [20, 10, -60] },
  { p: .46, pos: [8, 12, -35], look: [24, 12, -90] },
  { p: .52, pos: [25, 12, -68], look: [30, 12, -120] },
  { p: .57, pos: [24, 11, -98], look: [25, 10, -136] },
  { p: .62, pos: [25, 10, -119], look: [25, 10, -136] },
  { p: .67, pos: [25, 10, -119.2], look: [25, 10, -136] },
  { p: .695, pos: [13.3, 10, -129], look: [23, 11, -160] },
  { p: .71, pos: [14, 10, -144], look: [28, 12, -174] },
  { p: .72, pos: [18, 11, -145], look: [32, 12, -175] },
  { p: .755, pos: [22, 12, -154], look: [32, 12, -178] },
  { p: .775, pos: [21, 14, -171], look: [15, 16, -217] },
  { p: .79, pos: [23, 16, -185], look: [4, 16, -225] },
  { p: .86, pos: [4, 22, -225], look: [0, 15, -275] },
  { p: .94, pos: [0, 14, -260], look: [0, 9, -340] },
  { p: 1, pos: [0, 8, -279], look: [0, 14, -370] },
]
const vector = (v: number[]) => new THREE.Vector3(v[0], v[1], v[2])
const route = new THREE.CatmullRomCurve3(CAMERA_KEYS.map(k => vector(k.pos)), false, "catmullrom", .28)
const gaze = new THREE.CatmullRomCurve3(CAMERA_KEYS.map(k => vector(k.look)), false, "catmullrom", .28)
export const smooth = (p: number, start: number, end: number) => THREE.MathUtils.smoothstep(p, start, end)

export function cameraPose(progress: number) {
  const p = THREE.MathUtils.clamp(progress, 0, 1)
  let i = 0
  while (i < CAMERA_KEYS.length - 2 && p > CAMERA_KEYS[i + 1].p) i++
  const t = (i + (p - CAMERA_KEYS[i].p) / (CAMERA_KEYS[i + 1].p - CAMERA_KEYS[i].p)) / (CAMERA_KEYS.length - 1)
  return { position: route.getPoint(t), target: gaze.getPoint(t), roll: Math.sin(p * Math.PI * 4) * .018 }
}

export function pageFormation(p: number, index: number) {
  const enter = smooth(p, .065 + index * .008, .14 + index * .008)
  const fall = smooth(p, .205 + index * .004, .30 + index * .004)
  return { enter, fall, y: (1 - enter) * (150 + index * 12) - fall * (95 + index * 8) }
}

export function architectureFormation(p: number, index: number) {
  const phase = index * .0012
  return { enter: smooth(p, .435 + phase, .53 + phase), exit: smooth(p, .805 + phase, .92 + phase) }
}

// Smooth closed, double-sided paper bands, not a random triangle fan.
export function paperRibbon(side: number, layer: number) {
  const shape = (u: number, v: number, back: boolean) => {
    const z = -58 - u * 151
    const bend = Math.sin(u * Math.PI * 2) * 4
    const radius = 12 + layer * .02
    const angle = -.70 + layer * .047 + v * .043
    return [bend + side * (radius * Math.cos(angle) + (back ? .065 : 0)), 9 + Math.sin(angle) * (16 + layer * .13), z + Math.sin(v * Math.PI) * 2.5]
  }
  const nu = 88, nv = 4, vertices: number[] = [], indices: number[] = []
  for (let back = 0; back < 2; back++) for (let i = 0; i <= nu; i++) for (let j = 0; j <= nv; j++) vertices.push(...shape(i / nu, j / nv, !!back))
  const size = (nu + 1) * (nv + 1)
  const quad = (a: number, b: number, c: number, d: number) => indices.push(a, b, c, a, c, d)
  for (let i = 0; i < nu; i++) for (let j = 0; j < nv; j++) {
    const a = i * (nv + 1) + j, b = a + nv + 1
    quad(a, b, b + 1, a + 1); quad(a + size, a + 1 + size, b + 1 + size, b + size)
  }
  for (let i = 0; i < nu; i++) for (const j of [0, nv]) { const a = i * (nv + 1) + j, b = a + nv + 1; quad(a, a + size, b + size, b) }
  for (let j = 0; j < nv; j++) for (const i of [0, nu]) { const a = i * (nv + 1) + j; quad(a, a + 1, a + 1 + size, a + size) }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3))
  geometry.setIndex(indices); geometry.computeVertexNormals()
  return geometry
}

function hash(x: number, z: number) { const n = Math.sin(x * 127.1 + z * 311.7) * 43758.5453; return n - Math.floor(n) }
function noise(x: number, z: number) {
  const ix = Math.floor(x), iz = Math.floor(z), fx = x - ix, fz = z - iz
  const u = fx * fx * (3 - 2 * fx), v = fz * fz * (3 - 2 * fz)
  return THREE.MathUtils.lerp(THREE.MathUtils.lerp(hash(ix, iz), hash(ix + 1, iz), u), THREE.MathUtils.lerp(hash(ix, iz + 1), hash(ix + 1, iz + 1), u), v)
}
export function ridgeGeometry(side: number) {
  const geometry = new THREE.PlaneGeometry(1, 1, 112, 192)
  const positions = geometry.attributes.position, colors: number[] = [], uv: number[] = []
  const forest = new THREE.Color("#7c8871"), rock = new THREE.Color("#b1b5ac"), snow = new THREE.Color("#f0f1ee")
  for (let i = 0; i < positions.count; i++) {
    const u = positions.getX(i) + .5, v = positions.getY(i) + .5, z = 290 - v * 750
    const bank = 28 + 87 * (1 - smooth(z, 20, 145)) - 45 * smooth(-z, 210, 380) + noise(z * .024, side * 5) * 13, river = Math.sin(z * .019) * 10
    const x = river + side * (bank + u * 245)
    let detail = 0, amplitude = 1, frequency = .013
    for (let octave = 0; octave < 6; octave++) { detail += (1 - Math.abs(noise(x * frequency, z * frequency) * 2 - 1)) * amplitude; amplitude *= .48; frequency *= 2.08 }
    const edge = Math.pow(Math.sin(u * Math.PI * .7), 1.15)
    const y = -5 + edge * (32 + detail * 69) + noise(x * .28, z * .28) * edge * 3
    positions.setXYZ(i, x, y, z)
    uv.push(x / 30, z / 30)
    const color = forest.clone().lerp(rock, smooth(y, 25, 110)).lerp(snow, smooth(y, 113, 162))
    color.multiplyScalar(.78 + .22 * noise(x * .24, z * .24)); colors.push(color.r, color.g, color.b)
  }
  if (side === -1 && geometry.index) for (let i = 0; i < geometry.index.count; i += 3) { const a = geometry.index.getX(i); geometry.index.setX(i, geometry.index.getX(i + 2)); geometry.index.setX(i + 2, a) }
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2))
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3)); geometry.computeVertexNormals()
  return geometry
}
