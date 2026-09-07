def test_create_list_get_note(client):
    source = client.post("/sources", json={"type": "website", "url": "https://x.com"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Doc", "content": "Body"}).json()
    response = client.post("/notes", json={"title": "t", "content": "c", "content_type": "highlight", "document_id": document["id"]})
    assert response.status_code == 200
    note = response.json()

    assert client.get("/notes").status_code == 200
    assert client.get(f"/notes/{note['id']}").status_code == 200

def test_patch_note_partial_update(client):
    source = client.post("/sources", json={"type": "website", "url": "https://x.com"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Doc", "content": "Body"}).json()
    note = client.post("/notes", json={"title": "t", "content": "c", "content_type": "highlight", "document_id": document["id"]}).json()
    response = client.patch(f"/notes/{note['id']}", json={"content": "updated"})
    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "updated"
    assert body["title"] == "t"

def test_delete_note(client):
    source = client.post("/sources", json={"type": "website", "url": "https://x.com"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Doc", "content": "Body"}).json()
    note = client.post("/notes", json={"title": "t", "content": "c", "content_type": "highlight", "document_id": document["id"]}).json()
    assert client.delete(f"/notes/{note['id']}").status_code == 200
    assert client.get(f"/notes/{note['id']}").status_code == 404

def test_get_missing_note_404(client):
    assert client.get("/notes/999999").status_code == 404

def test_note_can_be_linked_to_document(client):
    source = client.post("/sources", json={"type": "website", "url": "https://x.com"}).json()
    document = client.post("/documents", json={
        "source_id": source["id"], "title": "Doc", "content": "Body"
    }).json()
    note = client.post("/notes", json={
        "title": "t", "content": "c", "content_type": "highlight", "document_id": document["id"]
    }).json()
    assert note["document_id"] == document["id"]

def test_generated_result_retains_its_source_passage(client):
    source = client.post("/sources", json={"type": "website", "url": "https://x.com"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Doc", "content": "Dense original passage"}).json()
    response = client.post("/notes", json={
        "title": "Clear explanation",
        "content": "A clearer generated result",
        "content_type": "explanation",
        "source_passage": "Dense original passage",
        "document_id": document["id"]
    })
    assert response.status_code == 200
    assert response.json()["source_passage"] == "Dense original passage"

def test_generated_result_rejects_missing_source_passage(client):
    source = client.post("/sources", json={"type": "website", "url": "https://x.com"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Doc", "content": "Body"}).json()
    response = client.post("/notes", json={
        "title": "Unlinked result", "content": "Generated", "content_type": "simplification",
        "document_id": document["id"]
    })
    assert response.status_code == 422

def test_note_requires_a_persisted_document(client):
    missing = client.post("/notes", json={
        "title": "orphan", "content": "must not persist", "content_type": "highlight"
    })
    assert missing.status_code == 422

    unknown = client.post("/notes", json={
        "title": "orphan", "content": "must not persist", "content_type": "highlight",
        "document_id": 999999
    })
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Document not found; note was not saved"
    assert client.get("/notes").json() == []
