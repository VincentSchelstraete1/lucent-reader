import { BrowserRouter, Routes, Route, Navigate, Link, NavLink, Outlet, useParams } from "react-router-dom"
import { Library } from "./pages/Library"
import { SourceDetail } from "./pages/SourceDetail"
import { QuizGenerationPage, QuizPage } from "./pages/QuizPage"
import { LandingPage } from "./pages/LandingPage"
import { AuthPage } from "./pages/AuthPage"
import { OnboardingPage } from "./pages/OnboardingPage"
import { AppWalkthrough } from "./components/walkthrough/AppWalkthrough"
import { ProtectedRoute } from "./components/auth/ProtectedRoute"
import { LearningCanvasDemo } from "./learning/components/LearningCanvasDemo"
import { DocumentIngestionDemo } from "./pages/DocumentIngestionDemo"
import { Notes } from "./pages/Notes"
import { StepThroughDev } from "./pages/StepThroughDev"

function LegacyDocumentRedirect() {
  const { documentId } = useParams()
  return <Navigate to={`/app/material/${documentId}?mode=notes`} replace />
}

function SidebarIcon({ name }: { name: "library" | "learn" | "cards" | "quiz" }) {
  const paths = { library: <><path d="M3 5.5h6l1.5 2H21v11H3z" /><path d="M3 8h18" /></>, learn: <><path d="M3 5.5c3.4-.8 6 .2 9 2.2v11c-3-2-5.6-3-9-2.2z" /><path d="M21 5.5c-3.4-.8-6 .2-9 2.2v11c3-2 5.6-3 9-2.2z" /></>, cards: <><rect x="4" y="6" width="14" height="11" rx="1.5" /><path d="M7 4h13v11" /></>, quiz: <><circle cx="12" cy="12" r="8.5" /><path d="M9.8 9.5a2.3 2.3 0 1 1 3.8 1.7c-1 .7-1.6 1.1-1.6 2.3" /><path d="M12 16.2h.01" /></> }[name]
  return <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths}</svg>
}

// Wraps only the existing logged-in app routes with the original header, so
// the new public pages (landing/login/signup/onboarding) render without it.
function AppLayout() {
  return (
    <div className="app-shell">
      <aside className="app-sidebar" aria-label="Study navigation">
        <Link to="/app" className="brand" data-tour="app-brand">Lucent</Link>
        <nav className="app-sidebar-nav">
          <NavLink to="/app" end className={({ isActive }) => isActive ? "active" : ""}><SidebarIcon name="library" />Library</NavLink>
          <NavLink to="/app?view=learn" className={({ isActive }) => isActive ? "active" : ""}><SidebarIcon name="learn" />Learn</NavLink>
          <NavLink to="/app?view=flashcards" className={({ isActive }) => isActive ? "active" : ""}><SidebarIcon name="cards" />Flashcards</NavLink>
          <NavLink to="/app?view=quiz" className={({ isActive }) => isActive ? "active" : ""}><SidebarIcon name="quiz" />Quiz</NavLink>
        </nav>
      </aside>
      <main><Outlet /></main>
      <AppWalkthrough />
    </div>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/signup" element={<AuthPage mode="signup" />} />
        <Route path="/onboarding" element={<OnboardingPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/app" element={<Library />} />
            <Route path="/app/notes" element={<Notes />} />
            <Route path="/app/material/:documentId" element={<Notes />} />
            <Route path="/sources/:sourceId" element={<SourceDetail />} />
            <Route path="/documents/:documentId" element={<LegacyDocumentRedirect />} />
            <Route path="/quizzes/:quizId" element={<QuizPage />} />
            <Route path="/quizzes/generating" element={<QuizGenerationPage />} />
            <Route path="/app/learning-canvas" element={<LearningCanvasDemo />} />
            {import.meta.env.DEV && <Route path="/app/dev/ingestion" element={<DocumentIngestionDemo />} />}
            {import.meta.env.DEV && <Route path="/app/dev/step-through" element={<StepThroughDev />} />}
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
