import { BrowserRouter, Routes, Route, Navigate, Link, Outlet } from "react-router-dom"
import { Library } from "./pages/Library"
import { SourceDetail } from "./pages/SourceDetail"
import { DocumentDetail } from "./pages/DocumentDetail"
import { QuizPage } from "./pages/QuizPage"
import { LandingPage } from "./pages/LandingPage"
import { AuthPage } from "./pages/AuthPage"
import { OnboardingPage } from "./pages/OnboardingPage"
import { AppWalkthrough } from "./components/walkthrough/AppWalkthrough"

// Wraps only the existing logged-in app routes with the original header, so
// the new public pages (landing/login/signup/onboarding) render without it.
function AppLayout() {
  return (
    <>
      <header className="app-header">
        <Link to="/app" className="brand" data-tour="app-brand">
          Lucent Library
        </Link>
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

        <Route element={<AppLayout />}>
          <Route path="/app" element={<Library />} />
          <Route path="/sources/:sourceId" element={<SourceDetail />} />
          <Route path="/documents/:documentId" element={<DocumentDetail />} />
          <Route path="/quizzes/:quizId" element={<QuizPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
