import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useAuth } from "../lib/AuthContext"

export function SettingsPage() {
  const { user, deleteAccount } = useAuth()
  const navigate = useNavigate()
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState("")
  const name = user?.display_name || "Lucent learner"

  async function handleDeleteAccount() {
    setDeleting(true)
    setDeleteError("")
    try {
      await deleteAccount()
      navigate("/", { replace: true })
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "We couldn't delete your account. Please try again.")
      setDeleting(false)
    }
  }

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

      <section className="settings-section settings-danger" aria-labelledby="delete-account-title">
        <div>
          <h2 id="delete-account-title">Delete account</h2>
          <p>Permanently remove your account, saved materials, generated study content, and learning progress.</p>
        </div>
        <button className="btn btn-danger" type="button" onClick={() => setConfirmingDelete(true)}>Delete account</button>
      </section>

      {confirmingDelete && (
        <div className="dialog-backdrop" role="presentation">
          <section className="library-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-delete-account-title" aria-describedby="confirm-delete-account-description">
            <h2 id="confirm-delete-account-title">Delete your Lucent account?</h2>
            <p id="confirm-delete-account-description">This permanently deletes your materials, generated study content, and learning progress. This action cannot be undone.</p>
            {deleteError && <p className="error" role="alert">{deleteError}</p>}
            <div className="settings-dialog-actions">
              <button className="btn btn-secondary" type="button" disabled={deleting} onClick={() => setConfirmingDelete(false)}>Cancel</button>
              <button className="btn btn-danger" type="button" disabled={deleting} onClick={() => void handleDeleteAccount()}>{deleting ? "Deleting…" : "Delete account permanently"}</button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
