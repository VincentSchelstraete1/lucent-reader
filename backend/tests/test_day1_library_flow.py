def test_extension_save_to_learning_library_contract(client):
    passage = "Mitochondria use a proton gradient to help produce ATP."
    page = {
        "type": "website",
        "url": "https://example.com/cell-energy#overview",
    }

    source = client.post("/sources", json=page).json()
    reused_source = client.post("/sources", json={
        **page, "url": "https://example.com/cell-energy#details"
    }).json()
    assert reused_source["id"] == source["id"]

    document = client.post("/documents", json={
        "source_id": source["id"],
        "title": "How cells store energy",
        "content": f"An introduction. {passage} More detail follows.",
    }).json()
    reused_document = client.post("/documents", json={
        "source_id": source["id"],
        "title": "How cells store energy",
        "content": f"An introduction. {passage} More detail follows.",
    }).json()
    assert reused_document["id"] == document["id"]

    saves = [
        {
            "title": "Proton gradient",
            "content": passage,
            "content_type": "highlight",
            "document_id": document["id"],
        },
        {
            "title": "Proton gradient explained",
            "content": "Stored protons flow through a molecular motor that creates ATP.",
            "content_type": "explanation",
            "source_passage": passage,
            "document_id": document["id"],
        },
        {
            "title": "Proton gradient simplified",
            "content": "A flow of particles helps the cell make usable energy.",
            "content_type": "simplification",
            "source_passage": passage,
            "document_id": document["id"],
        },
    ]
    for save in saves:
        response = client.post("/notes", json=save)
        assert response.status_code == 200

    library_sources = client.get("/sources").json()
    library_documents = client.get("/documents").json()
    library_notes = client.get("/notes").json()

    assert library_sources == [source]
    assert library_documents[0]["id"] == document["id"]
    assert passage in library_documents[0]["content"]
    assert [note["content_type"] for note in library_notes] == [
        "highlight", "explanation", "simplification"
    ]
    assert library_notes[1]["source_passage"] == passage
    assert library_notes[2]["source_passage"] == passage
    assert all(note["document_id"] == document["id"] for note in library_notes)
