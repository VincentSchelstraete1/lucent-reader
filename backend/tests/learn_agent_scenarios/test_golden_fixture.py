"""The deterministic source/session setup used by golden browser runs."""

from .golden_fixture import GOLDEN_DOMAINS, seed_golden_domain


def test_golden_fixture_seeds_two_substantive_domains_without_cross_contamination(client):
    sessions = []
    for domain in GOLDEN_DOMAINS:
        document, session = seed_golden_domain(client, domain)
        assert document["content"] == domain.content
        assert session["status"] == "active"
        scene = session.get("scene") or {}
        assert scene.get("sourceBlockIds") == [f"golden-{domain.key}-block"]
        assert "insufficient source material" not in str(scene).casefold()
        sessions.append((document["id"], session["id"]))
    assert len({document_id for document_id, _ in sessions}) == 2
    assert len({session_id for _, session_id in sessions}) == 2


def test_restart_archives_prior_active_session_for_deterministic_resume(client):
    from app.database import SessionLocal
    from app.models.learn import LearnSession
    from sqlalchemy import select

    document, first = seed_golden_domain(client, GOLDEN_DOMAINS[0])
    second = client.post(
        f"/documents/{document['id']}/learn-sessions",
        json={"goal": "understand", "familiarity": "new", "restart": True},
    )
    assert second.status_code == 200
    assert second.json()["id"] != first["id"]
    active = client.get(f"/documents/{document['id']}/learn-sessions/active")
    assert active.status_code == 200 and active.json()["id"] == second.json()["id"]
    with SessionLocal() as db:
        rows = db.execute(select(LearnSession).where(LearnSession.document_id == document["id"])).scalars().all()
        assert sum(row.status == "active" for row in rows) == 1
        old = next(row for row in rows if str(row.id) == first["id"])
        assert old.status == "stopped" and old.ended_reason == "restarted"
