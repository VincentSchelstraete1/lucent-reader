from app.models.auth import User
from app.models.document import Document
from app.models.note import Note
from app.models.quiz import Quiz, QuizAttempt
from app.models.source import Source
from conftest import TestSessionLocal
from test_auth_security import _client_for, _user


def test_user_cannot_access_another_users_resource_graph():
    owner = _user("owner")
    other = _user("other")
    with TestSessionLocal() as db:
        source = Source(user_id=owner.id, type="website", url="https://private.example")
        db.add(source); db.flush()
        document = Document(source_id=source.id, title="Private", content="secret")
        db.add(document); db.flush()
        note = Note(title="Private", content="secret", content_type="highlight", document_id=document.id)
        quiz = Quiz(document_id=document.id, title="Private quiz", questions=[])
        db.add_all([note, quiz]); db.flush()
        attempt = QuizAttempt(user_id=owner.id, quiz_id=quiz.id, score=1, total=1)
        db.add(attempt); db.commit()
        ids = source.id, document.id, note.id, quiz.id, attempt.id
    client = _client_for(other)
    source_id, document_id, note_id, quiz_id, attempt_id = ids
    assert client.get("/sources").json() == []
    for path in [f"/sources/{source_id}", f"/documents/{document_id}", f"/notes/{note_id}", f"/quizzes/{quiz_id}", f"/quiz-attempts/{attempt_id}"]:
        assert client.get(path).status_code == 404
    assert client.patch(f"/notes/{note_id}", json={"title": "stolen"}).status_code == 404
    assert client.delete(f"/notes/{note_id}").status_code == 404
    assert client.post(f"/documents/{document_id}/generate-note").status_code == 404
    assert client.post(f"/quizzes/{quiz_id}/attempts", json={"score": 1, "total": 1}).status_code == 404
    owner_client = _client_for(owner)
    assert owner_client.get(f"/documents/{document_id}").status_code == 200
    assert owner_client.get(f"/notes/{note_id}").status_code == 200
