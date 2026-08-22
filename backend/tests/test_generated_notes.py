import json

def _make_document(client):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com"}).json()
    return client.post("/documents", json={
        "source_id": source["id"],
        "title": "Test Doc",
        "content": "Some long educational content about photosynthesis."
    }).json()

def test_generate_note_success(client, mock_generated_note):
    document = _make_document(client)
    response = client.post(f"/documents/{document['id']}/generate-note")
    assert response.status_code == 200
    body = response.json()
    assert body["content_type"] == "generated_note"
    assert body["document_id"] == document["id"]

    parsed = json.loads(body["content"])
    assert parsed["title"] == "Mock Note"
    assert parsed["key_points"] == ["Point one", "Point two"]
    assert parsed["sections"][0]["heading"] == "Intro"

def test_generate_note_missing_document_404(client, mock_generated_note):
    assert client.post("/documents/999999/generate-note").status_code == 404

def test_generate_note_invalid_ai_output_rejected(client, mock_invalid_structured_output):
    document = _make_document(client)
    response = client.post(f"/documents/{document['id']}/generate-note")
    assert response.status_code == 502
