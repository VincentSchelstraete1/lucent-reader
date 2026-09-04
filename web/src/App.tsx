import { BrowserRouter, Routes, Route, Navigate, Link, Outlet, useParams } from "react-router-dom"
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

// Wraps only the existing logged-in app routes with the original header, so
// the new public pages (landing/login/signup/onboarding) render without it.
function AppLayout() {
  return (
    <>
      <header className="app-header">
        <Link to="/app" className="brand" data-tour="app-brand">
          Lucent Library
        </Link>
        <Link to="/app" className="app-header-link">Library</Link>
      </header>
      <main>
        <Outlet />
      </main>
      <AppWalkthrough />
    </>
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
