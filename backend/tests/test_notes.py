def test_create_list_get_note(client):
    response = client.post("/notes", json={"title": "t", "content": "c", "content_type": "highlight"})
    assert response.status_code == 200
    note = response.json()

    assert client.get("/notes").status_code == 200
    assert client.get(f"/notes/{note['id']}").status_code == 200

def test_patch_note_partial_update(client):
    note = client.post("/notes", json={"title": "t", "content": "c", "content_type": "highlight"}).json()
    response = client.patch(f"/notes/{note['id']}", json={"content": "updated"})
    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "updated"
    assert body["title"] == "t"

def test_delete_note(client):
    note = client.post("/notes", json={"title": "t", "content": "c", "content_type": "highlight"}).json()
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
