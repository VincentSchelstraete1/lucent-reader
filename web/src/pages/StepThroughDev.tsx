import { useEffect, useMemo, useState } from "react"
import { ApiError, api, type StepThroughFixture, type StepThroughResponse } from "../api/client"
import { generatedMechanismToRendererData, StepThroughMechanism, summarizeVisualProgram } from "../learning/experiences/StepThroughMechanism"
import { gramSchmidtGolden } from "../learning/experiences/goldenExamples"

export function StepThroughDev() {
  const [fixtures, setFixtures] = useState<StepThroughFixture[]>([])
  const [selected, setSelected] = useState("gram-schmidt")
  const [source, setSource] = useState("")
  const [result, setResult] = useState<StepThroughResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [validationErrors, setValidationErrors] = useState<ApiError["details"]>([])
  const [status, setStatus] = useState<"idle" | "generating" | "replay_loaded" | "live_succeeded" | "validation_failed" | "truncated" | "timed_out" | "request_failed">("idle")
  const [invocationCallCount, setInvocationCallCount] = useState<0 | 1>(0)
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
    setValidationErrors([])
    setStatus("idle")
    setInvocationCallCount(0)
  }

  async function generate(mode: "replay" | "live") {
    setResult(null)
    setError(null)
    setValidationErrors([])
    setStatus("generating")
    setInvocationCallCount(mode === "live" ? 1 : 0)
    try {
      const response = await api.generateStepThrough({ fixture_name: selected, source_text: source, mode, save_fixture: mode === "live" })
      setResult(response)
      setStatus(mode === "replay" ? "replay_loaded" : "live_succeeded")
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : "Step-through generation failed")
      if (err instanceof ApiError && err.code === "invalid_generation") {
        setValidationErrors(err.details)
        setStatus("validation_failed")
      } else if (err instanceof ApiError && err.code === "generation_truncated") {
        setStatus("truncated")
      } else if (err instanceof ApiError && err.code === "generation_timeout") {
        setStatus("timed_out")
      } else {
        setStatus("request_failed")
      }
    }
  }

  const rendererData = result ? (result.metadata.fixture_kind === "golden_manual" ? gramSchmidtGolden : generatedMechanismToRendererData(result.mechanism)) : null
  const summary = rendererData ? summarizeVisualProgram(rendererData) : null
  const origin = result?.metadata.fixture_kind === "golden_manual" ? "Golden / manual" : result?.metadata.fixture_kind === "sample_manual" ? "Manual regression sample" : result?.metadata.fixture_kind === "recorded_live" ? "Recorded live model output" : "—"
  const statusLabel = { idle: "Ready", generating: "Generating…", replay_loaded: "Replay loaded", live_succeeded: "Live generation succeeded", validation_failed: "Live generation failed validation", truncated: "Live generation was truncated (no retry)", timed_out: "Live generation timed out (no retry)", request_failed: "Generation request failed" }[status]
  return <section className="page step-through-dev">
    <header className="page-header"><p className="note-kicker">Development tool</p><h1>Step-through generator</h1><p className="page-subtitle">Generate one semantic mechanism with zero or one model call, then replay it for free. Live policy: 25-second limit, zero retries.</p></header>
    <div className="step-through-toolbar">
      <label>Source fixture<select value={selected} onChange={(event) => choose(event.target.value)}>{fixtures.map((item) => <option key={item.name} value={item.name}>{item.name}{item.replay_available ? " · replay available" : ""}</option>)}</select></label>
      <label>Source section<textarea value={source} onChange={(event) => setSource(event.target.value)} rows={6} /></label>
      <div className="step-through-actions"><button type="button" onClick={() => generate("replay")} disabled={!source || status === "generating"}>Replay (0 calls)</button><button className="btn btn-primary" type="button" onClick={() => generate("live")} disabled={!source || status === "generating"}>Live generate once</button></div>
    </div>
    <p className={`step-through-status status-${status}`} aria-live="polite"><strong>Status:</strong> {statusLabel} <span>· Model calls this invocation: {result?.metadata.model_call_count ?? invocationCallCount}</span></p>
    {error && <div className="error" role="alert"><strong>{error}</strong>{validationErrors.length > 0 && <ul>{validationErrors.map((item) => <li key={`${item.location}-${item.type}`}><code>{item.location}</code>: {item.message}</li>)}</ul>}</div>}
    {result && summary && <section className="step-through-result" aria-live="polite"><dl className="step-through-metrics"><div><dt>Result</dt><dd>{statusLabel}</dd></div><div><dt>Validation</dt><dd>{result.metadata.validation}</dd></div><div><dt>Model calls this invocation</dt><dd>{result.metadata.model_call_count}</dd></div><div><dt>Fixture</dt><dd>{result.metadata.cache_hit ? "replay hit" : "live miss"}</dd></div><div><dt>Origin</dt><dd>{origin}</dd></div><div><dt>Latency</dt><dd>{Math.round(result.metadata.latency_ms)} ms</dd></div><div><dt>Model</dt><dd>{result.metadata.model ?? "none (replay)"}</dd></div><div><dt>Input tokens</dt><dd>{result.metadata.input_tokens ?? "not reported"}</dd></div><div><dt>Output tokens</dt><dd>{result.metadata.output_tokens ?? "not reported"}</dd></div></dl><div className="visual-program-summary"><strong>Visual program</strong><span>{summary.entities} entities</span><span>{summary.stages} stages</span><span>{summary.operations} semantic operations</span><span>{summary.stateChangingOperations} state-changing operations</span><span>scene: {summary.scene}</span><span>renderable stages: {summary.availableStages}/{summary.stages}</span></div><details><summary>Generated semantic JSON</summary><pre>{JSON.stringify(result.mechanism, null, 2)}</pre></details><h2>{result.mechanism.title}</h2><StepThroughMechanism data={rendererData!} /></section>}
    {!result && selected === "gram-schmidt" && <section className="step-through-result"><p className="step-through-muted">The built-in golden replay is also available as a visual reference.</p><StepThroughMechanism data={gramSchmidtGolden} /></section>}
    {fixture && <p className="step-through-hash">Source hash: {fixture.source_hash}</p>}
  </section>
}
