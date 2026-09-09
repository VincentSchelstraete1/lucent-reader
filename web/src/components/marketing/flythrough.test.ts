import { describe, expect, it } from 'vitest'
import { cameraPose, CAMERA_KEYS, WORLD, pagePose, passingPagePose } from './flythrough'
describe('one persistent alpine world',()=>{
  it('authors the complete route through hero, product and destination',()=>{
    expect(cameraPose(0).position.toArray()).toEqual(CAMERA_KEYS[0].pos)
    expect(cameraPose(1).position.z).toBe(73)
    expect(cameraPose(0).position.distanceTo(cameraPose(1).position)).toBeGreaterThan(165)
    expect(WORLD.hero[2]).toBeGreaterThan(WORLD.product[2])
    expect(WORLD.product[2]).toBeGreaterThan(WORLD.overlook[2])
  })
  it('keeps camera position, gaze and bank continuous through every interval',()=>{
    let prev=cameraPose(0)
    for(let i=1;i<=3000;i++){
      const pose=cameraPose(i/3000)
      expect(pose.position.toArray().every(Number.isFinite)).toBe(true)
      expect(pose.position.distanceTo(prev.position)).toBeLessThan(.8)
      expect(pose.target.distanceTo(prev.target)).toBeLessThan(.8)
      expect(pose.position.distanceTo(pose.target)).toBeGreaterThan(45)
      expect(Math.abs(pose.roll)).toBeLessThan(.01)
      prev=pose
    }
  })
  it('passes beside the solid product and document surfaces',()=>{
    for(let i=0;i<=3000;i++){
      const p=cameraPose(i/3000).position
      if(Math.abs(p.z-WORLD.product[2])<.4)expect(p.x).toBeLessThan(WORLD.product[0]-9)
      if(Math.abs(p.z-WORLD.hero[2])<.4)expect(p.x).toBeLessThan(WORLD.hero[0]-5)
    }
  })
  it('brings individual distant pages down into a shared fixed hero location',()=>{
    const starts=[]
    for(let i=0;i<5;i++){
      const a=pagePose(0,i),b=pagePose(.25,i)
      expect(a.visible).toBe(false)
      expect(a.position.y).toBeGreaterThan(b.position.y+40)
      expect(a.position.z).toBeLessThan(b.position.z-25)
      expect(b.enter).toBe(1);expect(b.visible).toBe(true)
      expect(b.position.distanceTo(pagePose(.28,i).position)).toBeLessThan(.001)
      starts.push(a.position.toArray().join(','))
    }
    expect(new Set(starts).size).toBe(5)
  })
  it('separates the pages and drops them into valley fog before continuing',()=>{
    for(let i=0;i<5;i++){
      const a=pagePose(.28,i),b=pagePose(.41,i)
      expect(b.position.y).toBeLessThan(a.position.y-15)
      expect(b.position.distanceTo(a.position)).toBeGreaterThan(20)
      expect(pagePose(.48,i).visible).toBe(false)
    }
  })
  it('moves passing pages across a substantial depth range',()=>{
    const a=passingPagePose(.08,0),b=passingPagePose(.20,0)
    expect(b.position.z-a.position.z).toBeGreaterThan(70)
    expect(b.position.y).toBeLessThan(a.position.y)
    expect(passingPagePose(0,0).visible).toBe(false)
  })
  it('manual page selection does not change the camera route',()=>{
    const before=cameraPose(.25)
    for(let i=0;i<5;i++)pagePose(.25,i,3)
    expect(cameraPose(.25).position.toArray()).toEqual(before.position.toArray())
    pagePose(.25,3,3).position.toArray().forEach((value,i)=>expect(value).toBeCloseTo(WORLD.hero[i],8))
  })
})
