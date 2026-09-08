import { describe, expect, it } from "vitest"
import { architectureFormation, CAMERA_KEYS, cameraPose, pageFormation, paperRibbon, ridgeGeometry } from "./flythrough"

describe("one continuous landing camera journey", () => {
  it("travels through world space with lateral and elevation changes", () => {
    expect(cameraPose(0).position.toArray()).toEqual(CAMERA_KEYS[0].pos)
    expect(cameraPose(1).position.z).toBeCloseTo(-279)
    expect(cameraPose(.52).position.x).toBeCloseTo(25)
    expect(cameraPose(.4).position.y).toBeCloseTo(12)
    expect(cameraPose(0).position.distanceTo(cameraPose(1).position)).toBeGreaterThan(500)
  })
  it("has finite continuous positions and a non-degenerate gaze throughout", () => {
    let previous = cameraPose(0).position
    for (let i = 1; i <= 2000; i++) {
      const pose = cameraPose(i / 2000)
      expect(pose.position.toArray().every(Number.isFinite)).toBe(true)
      expect(pose.position.distanceTo(previous)).toBeLessThan(1.8)
      expect(pose.target.distanceTo(pose.position)).toBeGreaterThan(8)
      expect(Math.abs(pose.roll)).toBeLessThan(.02)
      previous = pose.position
    }
  })
  it("passes beside the product surface instead of through it", () => {
    for (let i = 670; i <= 720; i++) {
      const p = cameraPose(i / 1000).position
      if (Math.abs(p.z + 136) < .8) expect(p.x).toBeLessThan(15.5)
    }
  })
  it("keeps the pure opening and calm lake free of the page architecture", () => {
    for (let i = 0; i < 5; i++) {
      expect(pageFormation(0, i).enter).toBe(0)
      expect(pageFormation(.18, i).enter).toBe(1)
      expect(pageFormation(.38, i).fall).toBe(1)
    }
    for (let i = 0; i < 16; i++) {
      expect(architectureFormation(.4, i).enter).toBe(0)
      expect(architectureFormation(.58, i).enter).toBe(1)
      expect(architectureFormation(1, i).exit).toBe(1)
    }
  })
  it("physically lowers the documents into fog while the camera can still see them", () => {
    expect(pageFormation(.22, 0).y).toBeLessThan(pageFormation(.18, 0).y)
    expect(cameraPose(.22).position.z).toBeGreaterThan(128)
    expect(pageFormation(.29, 0).y).toBeLessThan(-80)
  })
})

describe("smooth paper and terrain geometry", () => {
  it.each([-1, 1])("makes closed finite ribbons on side %i", side => {
    for (const layer of [0, 20, 39]) {
      const g = paperRibbon(side, layer), edges = new Map<string, number>()
      expect(Array.from(g.attributes.position.array).every(Number.isFinite)).toBe(true)
      expect(Array.from(g.attributes.normal.array).every(Number.isFinite)).toBe(true)
      const index = g.index!
      for (let i = 0; i < index.count; i += 3) for (let j = 0; j < 3; j++) {
        const a = index.getX(i + j), b = index.getX(i + (j + 1) % 3), key = [Math.min(a, b), Math.max(a, b)].join(":")
        edges.set(key, (edges.get(key) || 0) + 1)
      }
      expect([...edges.values()].every(n => n === 2)).toBe(true)
      g.dispose()
    }
  })
  it.each([-1, 1])("keeps terrain normals pointing out of the ground on side %i", side => {
    const g = ridgeGeometry(side)
    expect(g.attributes.uv.count).toBe(g.attributes.position.count)
    for (let i = 0; i < g.attributes.normal.count; i += 197) expect(g.attributes.normal.getY(i)).toBeGreaterThan(0)
    g.dispose()
  })
})
