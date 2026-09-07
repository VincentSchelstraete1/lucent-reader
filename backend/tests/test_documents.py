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

def test_reuses_document_for_repeated_website_save(client):
    source = _make_source(client)
    first = client.post("/documents", json={
        "source_id": source["id"], "title": "First title", "content": "First snapshot"
    }).json()
    repeated = client.post("/documents", json={
        "source_id": source["id"], "title": "Current title", "content": "Current snapshot"
    }).json()
    assert repeated["id"] == first["id"]
    assert repeated["title"] == "Current title"
    assert repeated["content"] == "Current snapshot"
    assert len(client.get("/documents").json()) == 1

def test_non_website_source_can_contain_multiple_documents(client):
    source = client.post("/sources", json={"type": "pdf", "url": None}).json()
    for title in ("Chapter one", "Chapter two"):
        response = client.post("/documents", json={
            "source_id": source["id"], "title": title, "content": title
        })
        assert response.status_code == 200
    assert len(client.get("/documents").json()) == 2
