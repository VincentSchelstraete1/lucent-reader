import { describe, expect, it } from 'vitest'
import { cameraPose } from './flythrough'
import { openingCamera, openingDepth, OPENING_END } from './openingScene'

describe('photographic opening only', () => {
  it('keeps every projected point in front of the camera, with meaningful depth separation', () => {
    for (let u = 0; u <= 1; u += .02) for (let v = 0; v <= 1; v += .02) {
      expect(openingDepth(u, v)).toBeGreaterThanOrEqual(220)
      expect(openingDepth(u, v)).toBeLessThanOrEqual(950)
    }
    expect(openingDepth(.05, .05)).toBeLessThan(openingDepth(.5, .45) / 3)
  })
  it('glides forward slowly with lateral travel, rather than changing field of view', () => {
    const a = openingCamera(0, 0), b = openingCamera(.035, 0)
    expect(b.position.z).toBeLessThan(a.position.z - 3)
    expect(b.position.x).toBeGreaterThan(a.position.x + .5)
    expect(a.position.distanceTo(b.position)).toBeLessThan(9)
    expect(a.target.clone().sub(a.position).normalize().distanceTo(b.target.clone().sub(b.position).normalize())).toBeLessThan(.03)
  })
  it('limits idle drift and rejoins the untouched later camera route exactly', () => {
    expect(openingCamera(0, 20).position.distanceTo(openingCamera(0, 0).position)).toBeLessThan(.3)
    for (const p of [OPENING_END, .12, .38, .64, 1]) {
      expect(openingCamera(p, 13).position.toArray()).toEqual(cameraPose(p).position.toArray())
      expect(openingCamera(p, 13).target.toArray()).toEqual(cameraPose(p).target.toArray())
    }
  })
})
