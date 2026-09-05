"""HTTP-level smoke coverage for the autonomous tutor's browser contract."""

from .harness import FakeTutorProvider, TutorScenarioTrace, assert_trace_invariants, create_source_material, provider_context, response_for, run_turn


def test_browser_contract_survives_teach_hint_answer_ask_and_resume(client):
    provider = FakeTutorProvider()
    with provider_context(provider):
        document, session = create_source_material(client)
        trace = TutorScenarioTrace("browser_smoke")
        session = run_turn(client, trace, session, {})
        if session["step"].get("hintsAvailable"):
            hint = client.post(f"/learn-sessions/{session['id']}/hints", json={})
            assert hint.status_code == 200
        session = run_turn(client, trace, session, response_for(session.get("step"), text="I'm not sure; partially"))
        ask = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Can you explain the energy conversion another way?"})
        assert ask.status_code == 200
        resumed = client.get(f"/documents/{document['id']}/learn-sessions/active")
        assert resumed.status_code == 200 and resumed.json()["id"] == session["id"]
    assert_trace_invariants(trace)
    assert session["step"]["title"]
    assert session["step"]["sourceBlockIds"] == ["b1"]
