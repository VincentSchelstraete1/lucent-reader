import { Component, type ReactNode } from "react"
import styles from "./auth.module.css"

type Props = { children: ReactNode }
type State = { error: Error | null }

// The lanyard is a required feature, not an optional decoration - if it
// throws (bad GLB, WebGL unavailable, etc.) this must not silently collapse
// into "just a login form". In dev, show the actual error so it's obvious
// and fixable. In production, fall back to a static (still visible) card.
export class LanyardErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error("[LucentLanyard] render error", error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      if (import.meta.env.DEV) {
        return (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 24,
              textAlign: "center"
            }}
          >
            <div
              style={{
                border: "1px solid #c0504d",
                background: "#fbeaea",
                color: "#8a2e2e",
                borderRadius: 10,
                padding: "16px 20px",
                fontSize: 13,
                fontFamily: "monospace",
                maxWidth: 360
              }}
            >
              LucentLanyard failed to render:
              <br />
              {this.state.error.message}
              <br />
              (see console for the full stack - this box only shows in dev)
            </div>
          </div>
        )
      }
      return <StaticFallbackCard />
    }
    return this.props.children
  }
}

function StaticFallbackCard() {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        pointerEvents: "none"
      }}
    >
      <div className={styles.staticCardCord} />
      <div className={styles.staticCard} />
    </div>
  )
}
