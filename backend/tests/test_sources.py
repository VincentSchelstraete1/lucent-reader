def test_create_and_get_source(client):
    response = client.post("/sources", json={"type": "website", "url": "https://example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "website"
    assert body["url"] == "https://example.com"

    get_response = client.get(f"/sources/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]

def test_list_sources(client):
    client.post("/sources", json={"type": "website", "url": "https://a.com"})
    client.post("/sources", json={"type": "pdf", "url": None})
    response = client.get("/sources")
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_patch_source_partial_update(client):
    created = client.post("/sources", json={"type": "website", "url": "https://old.com"}).json()
    response = client.patch(f"/sources/{created['id']}", json={"url": "https://new.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["url"] == "https://new.com"
    assert body["type"] == "website"

def test_delete_source(client):
    created = client.post("/sources", json={"type": "website", "url": "https://gone.com"}).json()
    assert client.delete(f"/sources/{created['id']}").status_code == 200
    assert client.get(f"/sources/{created['id']}").status_code == 404

def test_get_missing_source_404(client):
    assert client.get("/sources/999999").status_code == 404

def test_patch_missing_source_404(client):
    assert client.patch("/sources/999999", json={"url": "https://x.com"}).status_code == 404
