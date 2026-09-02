import { useEffect, useId, useRef, useState } from "react"
import type { ProcessLearningObject } from "../schema/learningObject"

type MermaidModule = typeof import("mermaid")["default"]
let mermaidPromise: Promise<MermaidModule> | null = null
let renderSequence = 0

async function loadMermaid(): Promise<MermaidModule> {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then(({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        flowchart: { htmlLabels: false, curve: "basis" },
        theme: "base",
        themeVariables: {
          primaryColor: "#f5f1e8",
          primaryTextColor: "#2c2c2a",
          primaryBorderColor: "#1d9e75",
          lineColor: "#167a5a",
          fontFamily: "Inter, system-ui, sans-serif"
        }
      })
      return mermaid
    })
  }
  return mermaidPromise
}

function safeLabel(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/#/g, "&#35;")
    .replace(/[\r\n]+/g, " ")
}

export function processToMermaid(object: ProcessLearningObject): string {
  const nodeByStep = new Map(object.steps.map((step, index) => [step.id, `node${index}`]))
  const nodes = object.steps.map((step, index) => `  node${index}["${safeLabel(step.label)}"]`)
  const connections = object.connections.flatMap(({ from, to }) => {
    const fromNode = nodeByStep.get(from)
    const toNode = nodeByStep.get(to)
    return fromNode && toNode ? [`  ${fromNode} --> ${toNode}`] : []
  })
  return ["flowchart LR", ...nodes, ...connections].join("\n")
}

function parseSafeSvg(markup: string): SVGElement {
  const documentNode = new DOMParser().parseFromString(markup, "image/svg+xml")
  if (documentNode.querySelector("parsererror") || documentNode.documentElement.tagName.toLowerCase() !== "svg") {
    throw new Error("Mermaid returned an invalid diagram")
  }
  documentNode.querySelectorAll("script, foreignObject").forEach((node) => node.remove())
  documentNode.querySelectorAll("*").forEach((node) => {
    for (const attribute of [...node.attributes]) {
      const value = attribute.value.trim().toLowerCase()
      if (attribute.name.toLowerCase().startsWith("on") || ((attribute.name === "href" || attribute.name.endsWith(":href")) && !value.startsWith("#"))) {
        node.removeAttribute(attribute.name)
      }
    }
  })
  return documentNode.documentElement as unknown as SVGElement
}

export function ProcessRenderer({ object }: { object: ProcessLearningObject }) {
  const host = useRef<HTMLDivElement>(null)
  const reactId = useId().replace(/[^a-zA-Z0-9_-]/g, "")
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading")
  const [error, setError] = useState("")

  useEffect(() => {
    let active = true
    setStatus("loading")
    setError("")
    const renderId = `lucent-process-${reactId}-${renderSequence += 1}`
    loadMermaid()
      .then((mermaid) => mermaid.render(renderId, processToMermaid(object)))
      .then(({ svg }) => {
        if (!active || !host.current) return
        host.current.replaceChildren(document.importNode(parseSafeSvg(svg), true))
        setStatus("ready")
      })
      .catch((reason: unknown) => {
        if (!active) return
        host.current?.replaceChildren()
        setError(reason instanceof Error ? reason.message : "Unable to render this process")
        setStatus("error")
      })
    return () => { active = false }
  }, [object, reactId])

  return (
    <div aria-busy={status === "loading"}>
      {status === "loading" && <p role="status">Building process diagram…</p>}
      {status === "error" && <p role="alert">{error}</p>}
      <div ref={host} aria-label={`${object.title} diagram`} />
    </div>
  )
}
