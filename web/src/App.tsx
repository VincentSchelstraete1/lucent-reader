import { lazy, Suspense } from "react"
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom"
import { LandingPage } from "./pages/LandingPage"
import { ProtectedRoute } from "./components/auth/ProtectedRoute"

const AppLayout = lazy(() => import("./components/app/AppLayout").then(module => ({ default: module.AppLayout })))
const AuthPage = lazy(() => import("./pages/AuthPage").then(module => ({ default: module.AuthPage })))
const OnboardingPage = lazy(() => import("./pages/OnboardingPage").then(module => ({ default: module.OnboardingPage })))
const PrivacyPage = lazy(() => import("./pages/PolicyPage").then(module => ({ default: module.PrivacyPage })))
const TermsPage = lazy(() => import("./pages/PolicyPage").then(module => ({ default: module.TermsPage })))
const Library = lazy(() => import("./pages/Library").then(module => ({ default: module.Library })))
const SourceDetail = lazy(() => import("./pages/SourceDetail").then(module => ({ default: module.SourceDetail })))
const QuizGenerationPage = lazy(() => import("./pages/QuizPage").then(module => ({ default: module.QuizGenerationPage })))
const QuizPage = lazy(() => import("./pages/QuizPage").then(module => ({ default: module.QuizPage })))
const LearningCanvasDemo = lazy(() => import("./learning/components/LearningCanvasDemo").then(module => ({ default: module.LearningCanvasDemo })))
const Notes = lazy(() => import("./pages/Notes").then(module => ({ default: module.Notes })))
const SettingsPage = lazy(() => import("./pages/SettingsPage").then(module => ({ default: module.SettingsPage })))
const DocumentIngestionDemo = import.meta.env.DEV
  ? lazy(() => import("./pages/DocumentIngestionDemo").then(module => ({ default: module.DocumentIngestionDemo })))
  : null
const StepThroughDev = import.meta.env.DEV
  ? lazy(() => import("./pages/StepThroughDev").then(module => ({ default: module.StepThroughDev })))
  : null

function LegacyDocumentRedirect() {
  const { documentId } = useParams()
  return <Navigate to={`/app/material/${documentId}?mode=notes`} replace />
}

function RouteLoading() {
  return <div className="route-loading" role="status">Opening Lucent…</div>
}

export function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteLoading />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/signup" element={<AuthPage mode="signup" />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/terms" element={<TermsPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/app" element={<Library />} />
              <Route path="/app/settings" element={<SettingsPage />} />
              <Route path="/app/notes" element={<Notes />} />
              <Route path="/app/material/:documentId" element={<Notes />} />
              <Route path="/sources/:sourceId" element={<SourceDetail />} />
              <Route path="/documents/:documentId" element={<LegacyDocumentRedirect />} />
              <Route path="/quizzes/:quizId" element={<QuizPage />} />
              <Route path="/quizzes/generating" element={<QuizGenerationPage />} />
              <Route path="/app/learning-canvas" element={<LearningCanvasDemo />} />
              {DocumentIngestionDemo && <Route path="/app/dev/ingestion" element={<DocumentIngestionDemo />} />}
              {StepThroughDev && <Route path="/app/dev/step-through" element={<StepThroughDev />} />}
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
