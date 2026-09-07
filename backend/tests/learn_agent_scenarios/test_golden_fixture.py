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

