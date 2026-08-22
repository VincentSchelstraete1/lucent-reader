def _make_source(client):
    return client.post("/sources", json={"type": "website", "url": "https://docs.example.com"}).json()

def test_create_list_get_document(client):
    source = _make_source(client)
    response = client.post("/documents", json={
        "source_id": source["id"], "title": "Doc", "content": "Body text"
    })
    assert response.status_code == 200
    document = response.json()
    assert document["source_id"] == source["id"]

    assert client.get("/documents").status_code == 200
    assert client.get(f"/documents/{document['id']}").status_code == 200

def test_patch_document_partial_update(client):
    source = _make_source(client)
    document = client.post("/documents", json={
        "source_id": source["id"], "title": "Old", "content": "Body"
    }).json()
    response = client.patch(f"/documents/{document['id']}", json={"title": "New"})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New"
    assert body["content"] == "Body"

def test_delete_document(client):
    source = _make_source(client)
    document = client.post("/documents", json={
        "source_id": source["id"], "title": "Gone", "content": "Body"
    }).json()
    assert client.delete(f"/documents/{document['id']}").status_code == 200
    assert client.get(f"/documents/{document['id']}").status_code == 404

def test_get_missing_document_404(client):
    assert client.get("/documents/999999").status_code == 404
