import { BrowserRouter, Routes, Route, Navigate, Link } from "react-router-dom"
import { Library } from "./pages/Library"
import { SourceDetail } from "./pages/SourceDetail"
import { DocumentDetail } from "./pages/DocumentDetail"
import { QuizPage } from "./pages/QuizPage"

export function App() {
  return (
    <BrowserRouter>
      <header className="app-header">
        <Link to="/" className="brand">
          Lucent Library
        </Link>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/sources/:sourceId" element={<SourceDetail />} />
          <Route path="/documents/:documentId" element={<DocumentDetail />} />
          <Route path="/quizzes/:quizId" element={<QuizPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
