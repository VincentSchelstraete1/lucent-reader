import { useEffect, useMemo, useRef, type MutableRefObject } from "react"
import { useFrame, useThree } from "@react-three/fiber"
import { useTexture } from "@react-three/drei"
import * as THREE from "three"
import { cameraPose, smooth } from "./flythrough"
import { openingDepth, OPENING_END } from "./openingScene"

// A photographic depth projection, not a replacement set of generated mountains.
// This bounded opening ends before the existing introduction has assembled.
export function OpeningLandscape({ progress }: { progress: MutableRefObject<number> }) {
  const texture = useTexture('/lucent-opening-alpine.jpg')
  const { size, invalidate } = useThree()
  const surface = useRef<THREE.Mesh>(null!)
  const material = useRef<THREE.ShaderMaterial>(null!)
  const geometry = useMemo(() => {
    const g = new THREE.PlaneGeometry(1, 1, 160, 100)
    const pos = g.attributes.position, uv = g.attributes.uv
    const aspect = size.width / size.height
    const height = 2 * Math.tan(THREE.MathUtils.degToRad(52 / 2)) * 1.06
    for (let i = 0; i < pos.count; i++) {
      const u = uv.getX(i), v = uv.getY(i)
      const depth = openingDepth(u, v)
      pos.setXYZ(i, (u - .5) * height * aspect * depth, (v - .5) * height * depth, -depth)
    }
    g.computeBoundingSphere()
    return g
  }, [size.width, size.height])
  useEffect(() => () => geometry.dispose(), [geometry])
  const basis = useMemo(() => {
    const pose = cameraPose(0), c = new THREE.PerspectiveCamera()
    c.position.copy(pose.position); c.lookAt(pose.target)
    return { position: pose.position, quaternion: c.quaternion }
  }, [])
  const uniforms = useMemo(() => ({ photo: { value: texture }, time: { value: 0 }, opacity: { value: 1 }, aspect: { value: size.width / size.height } }), [texture, size.width, size.height])
  useEffect(() => {
    // Keep the photo's display colour; the existing world's lights/tone mapping
    // must not flatten its exposure or turn its highlights grey.
    texture.colorSpace = THREE.NoColorSpace
    texture.minFilter = THREE.LinearFilter; texture.magFilter = THREE.LinearFilter
    texture.needsUpdate = true
    let frame: ReturnType<typeof setTimeout>
    const tick = () => { if (progress.current < OPENING_END && !document.hidden) invalidate(); frame = setTimeout(tick, 1000 / 30) }
    tick()
    return () => clearTimeout(frame)
  }, [texture, invalidate, progress])
  useFrame(({ clock, gl }) => {
    surface.current.visible = progress.current < OPENING_END
    material.current.uniforms.time.value = clock.elapsedTime
    material.current.uniforms.opacity.value = 1 - smooth(progress.current, .055, OPENING_END)
    gl.domElement.dataset.opening = surface.current.visible ? 'photographic-depth' : 'inactive'
    gl.domElement.dataset.openingTime = clock.elapsedTime.toFixed(2)
  })
  return <mesh ref={surface} geometry={geometry} position={basis.position} quaternion={basis.quaternion} renderOrder={1000} frustumCulled={false} raycast={() => {}}>
    <shaderMaterial ref={material} uniforms={uniforms} transparent depthTest={false} depthWrite={false} toneMapped={false}
      vertexShader={`varying vec2 photoUv;
        void main(){ photoUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`}
      fragmentShader={`
        uniform sampler2D photo; uniform float time; uniform float opacity; uniform float aspect;
        varying vec2 photoUv;
        float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
        float noise(vec2 p){vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);}
        float cloud(vec2 p){return noise(p)*.55+noise(p*2.03)*.28+noise(p*4.01)*.12+noise(p*8.02)*.05;}
        void main(){
          vec2 uv=photoUv;
          // Cover without stretching the photographic composition.
          if(aspect>1.5) uv.y=(uv.y-.5)*(1.5/aspect)+.5;
          else uv.x=(uv.x-.5)*(aspect/1.5)+.5;
          float lake=(1.-smoothstep(.37,.46,uv.y))*smoothstep(.14,.28,uv.y)*(1.-smoothstep(.30,.49,abs(uv.x-.5)));
          uv.x+=sin(uv.y*650.+time*.65)*.00023*lake;
          uv.y+=sin(uv.y*440.+time*.4+uv.x*17.)*.00010*lake;
          vec3 color=texture2D(photo,uv).rgb;
          // Three scales travel at different speeds: distant valley vapour,
          // lake wisps and a very soft veil close to the lens.
          float valley=exp(-pow((uv.y-.455)/.046,2.))*cloud(vec2(uv.x*8.-time*.018,uv.y*34.));
          float middle=exp(-pow((uv.y-.34)/.060,2.))*cloud(vec2(uv.x*6.+time*.025,uv.y*24.+time*.008));
          float near=exp(-pow((uv.y-.14-.025*sin(time*.11))/ .12,2.))*smoothstep(.40,.76,cloud(vec2(uv.x*3.-time*.034,uv.y*12.)));
          float fog=valley*.065+middle*.075+near*.12;
          color=mix(color,vec3(.88,.89,.85),fog);
          gl_FragColor=vec4(color,opacity);
        }`} />
  </mesh>
}
