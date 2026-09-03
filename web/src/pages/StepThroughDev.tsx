import { useEffect, useMemo, useState } from "react"
import { api, type StepThroughFixture, type StepThroughResponse } from "../api/client"
import { generatedMechanismToRendererData, StepThroughMechanism } from "../learning/experiences/StepThroughMechanism"
import { gramSchmidtGolden } from "../learning/experiences/goldenExamples"

export function StepThroughDev() {
  const [fixtures, setFixtures] = useState<StepThroughFixture[]>([])
  const [selected, setSelected] = useState("gram-schmidt")
  const [source, setSource] = useState("")
  const [result, setResult] = useState<StepThroughResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fixture = useMemo(() => fixtures.find((item) => item.name === selected), [fixtures, selected])

  useEffect(() => {
    api.getStepThroughFixtures().then((items) => {
      setFixtures(items)
      if (items[0]) setSource(items[0].source_text)
    }).catch((err) => setError(err instanceof Error ? err.message : "Unable to load fixtures"))
  }, [])

  function choose(name: string) {
    setSelected(name)
    const next = fixtures.find((item) => item.name === name)
    if (next) setSource(next.source_text)
    setResult(null)
    setError(null)
  }

  async function generate(mode: "replay" | "live") {
    setError(null)
    try {
      const response = await api.generateStepThrough({ fixture_name: selected, source_text: source, mode, save_fixture: mode === "live" })
      setResult(response)
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : "Step-through generation failed")
    }
  }

  const rendererData = result ? (result.metadata.fixture_kind === "golden_manual" ? gramSchmidtGolden : generatedMechanismToRendererData(result.mechanism)) : null
  return <section className="page step-through-dev">
    <header className="page-header"><p className="note-kicker">Development tool</p><h1>Step-through generator</h1><p className="page-subtitle">Generate one semantic mechanism with zero or one model call, then replay it for free.</p></header>
    <div className="step-through-toolbar">
      <label>Source fixture<select value={selected} onChange={(event) => choose(event.target.value)}>{fixtures.map((item) => <option key={item.name} value={item.name}>{item.name}{item.replay_available ? " · replay available" : ""}</option>)}</select></label>
      <label>Source section<textarea value={source} onChange={(event) => setSource(event.target.value)} rows={6} /></label>
      <div className="step-through-actions"><button type="button" onClick={() => generate("replay")} disabled={!source}>Replay (0 calls)</button><button className="btn btn-primary" type="button" onClick={() => generate("live")} disabled={!source}>Live generate once</button></div>
    </div>
    {error && <p className="error" role="alert">{error}</p>}
    {result && <section className="step-through-result" aria-live="polite"><dl className="step-through-metrics"><div><dt>Validation</dt><dd>{result.metadata.validation}</dd></div><div><dt>Model calls this invocation</dt><dd>{result.metadata.model_call_count}</dd></div><div><dt>Fixture</dt><dd>{result.metadata.cache_hit ? "replay hit" : "live miss"}</dd></div><div><dt>Latency</dt><dd>{Math.round(result.metadata.latency_ms)} ms</dd></div><div><dt>Model</dt><dd>{result.metadata.model ?? "none (replay)"}</dd></div></dl><details><summary>Generated semantic JSON</summary><pre>{JSON.stringify(result.mechanism, null, 2)}</pre></details><h2>{result.mechanism.title}</h2><StepThroughMechanism data={rendererData!} /></section>}
    {!result && selected === "gram-schmidt" && <section className="step-through-result"><p className="step-through-muted">The built-in golden replay is also available as a visual reference.</p><StepThroughMechanism data={gramSchmidtGolden} /></section>}
    {fixture && <p className="step-through-hash">Source hash: {fixture.source_hash}</p>}
  </section>
}
