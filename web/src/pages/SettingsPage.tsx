import { Link } from "react-router-dom"
import { useAuth } from "../lib/AuthContext"

export function SettingsPage() {
  const { user } = useAuth()
  const name = user?.display_name || "Lucent learner"

  return (
    <div className="page settings-page">
      <header className="settings-header">
        <p className="note-kicker">Your account</p>
        <h1>Settings</h1>
        <p className="page-subtitle">Review your account and Lucent information.</p>
      </header>

      <section className="settings-section" aria-labelledby="account-settings-title">
        <h2 id="account-settings-title">Account</h2>
        <dl className="settings-details">
          <div><dt>Name</dt><dd>{name}</dd></div>
          <div><dt>Email</dt><dd>{user?.email || "Not available"}</dd></div>
          <div><dt>Sign-in method</dt><dd>Google</dd></div>
        </dl>
      </section>

      <section className="settings-section" aria-labelledby="legal-settings-title">
        <h2 id="legal-settings-title">Privacy and terms</h2>
        <p>Read how Lucent handles your materials and the terms for using the service.</p>
        <div className="settings-links"><Link to="/privacy">Privacy notice</Link><Link to="/terms">Terms of use</Link></div>
      </section>
    </div>
  )
}
