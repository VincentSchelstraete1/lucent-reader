import { Link } from "react-router-dom"
import styles from "./policyPage.module.css"

const supportEmail = (import.meta.env.VITE_SUPPORT_EMAIL || "vincent.sch2006@gmail.com").trim()
const effectiveDate = (import.meta.env.VITE_POLICY_EFFECTIVE_DATE || "September 10, 2026").trim()

function PolicyShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className={styles.page}>
      <nav className={styles.nav}><Link to="/">Lucent</Link><Link to="/login">Log in</Link></nav>
      <article className={styles.card}>
        <p className={styles.eyebrow}>LUCENT WEB APP</p>
        <h1>{title}</h1>
        <p className={styles.updated}>Effective {effectiveDate}</p>
        {children}
        <p className={styles.contact}>Questions? <a href={`mailto:${supportEmail}`}>{supportEmail}</a></p>
      </article>
      <footer className={styles.footer}><Link to="/privacy">Privacy</Link><Link to="/terms">Terms</Link></footer>
    </main>
  )
}

export function PrivacyPage() {
  return (
    <PolicyShell title="Privacy notice">
      <h2>What Lucent stores</h2>
      <p>When you sign in, Lucent stores the account details Google provides for authentication, such as your email address, display name, and profile image. Lucent also stores material you upload or save, generated study material, learning-session state, answers, and progress in its application database.</p>

      <h2>How material is processed</h2>
      <p>Lucent sends relevant document excerpts, prompts, and learner interactions to Anthropic to generate explanations and tutoring responses. It sends bounded source text to Voyage to create and query embeddings used for source-backed retrieval. Those providers process this information under their own terms and privacy practices.</p>

      <h2>Operational data</h2>
      <p>Lucent records limited operational metadata needed to diagnose reliability and usage, such as route names, status codes, timings, provider operation names, and error categories. Application logging is designed not to include uploaded passages, prompts, learner answers, or generated tutor text.</p>

      <h2>Your choices</h2>
      <p>You can delete saved sources and documents through the application, or permanently delete your account and its application data from Settings. Account export is not yet self-service; contact support for assistance. Backup copies may persist until the applicable backup retention period expires.</p>

      <h2>Important launch review</h2>
      <p>The service owner must approve final retention periods and confirm Anthropic and Voyage processing terms before accepting real student documents in production.</p>
    </PolicyShell>
  )
}

export function TermsPage() {
  return (
    <PolicyShell title="Terms of use">
      <h2>Using Lucent</h2>
      <p>Lucent is a study and accessibility tool. You are responsible for checking important answers against the original material and for deciding whether the service is appropriate for your situation.</p>

      <h2>Material you provide</h2>
      <p>Only upload or save material you are allowed to use and process. Do not use Lucent to submit unlawful content or to violate another person's privacy or intellectual-property rights.</p>

      <h2>Generated material</h2>
      <p>Explanations, notes, questions, and tutor responses are generated automatically and may be incomplete or incorrect. They are not professional, medical, legal, or financial advice.</p>

      <h2>Availability and limits</h2>
      <p>Lucent may apply file-size, processing, or temporary usage limits to keep the service reliable and control provider costs. Features may occasionally be unavailable while the service or an external provider is recovering.</p>

      <h2>Accounts</h2>
      <p>Keep access to your Google account secure and use Lucent only through your own account. Contact support if you believe your Lucent access has been compromised.</p>
    </PolicyShell>
  )
}
