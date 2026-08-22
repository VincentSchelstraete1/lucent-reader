import { Link } from "react-router-dom"
import type { Quiz } from "../api/client"

export function QuizCard({ quiz }: { quiz: Quiz }) {
  return (
    <Link to={`/quizzes/${quiz.id}`} className="card card-link-wrap">
      <div className="card-title">{quiz.title}</div>
      <div className="card-subtext">{quiz.questions.length} questions</div>
      <div className="card-meta">Created {new Date(quiz.created_at).toLocaleString()}</div>
    </Link>
  )
}
