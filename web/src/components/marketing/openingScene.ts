import { cameraPose, smooth } from './flythrough'
export const OPENING_END = .075
// Permanent photographic depth envelope; the same plate persists along the route.
export function openingDepth(u: number, v: number) {
  const foreground = (1-smooth(v,.03,.26))*(.4+.6*smooth(Math.abs(u-.5),.1,.4))
  const shore = (1-smooth(v,.38,.65))*smooth(Math.abs(u-.5),.13,.48)
  const water = 1-smooth(v,.05,.46)
  return Math.max(220, 950-foreground*470-shore*140-water*180)
}
export function openingCamera(progress: number, time: number) {
  const pose = cameraPose(progress), amount = 1-smooth(progress,.035,.075)
  const x=Math.sin(time*.14)*.16*amount, y=Math.sin(time*.19)*.08*amount
  pose.position.x+=x; pose.target.x+=x; pose.position.y+=y; pose.target.y+=y
  return pose
}
