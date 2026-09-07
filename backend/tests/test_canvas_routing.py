from app.main import app

def test_canvas_routing_returns_plan_and_learning_object(client):
    examples = [
        "Temporal locality means recently accessed data is likely to be accessed again soon.",
        "Average memory access time equals hit time plus miss rate multiplied by miss penalty. If hit time is 2 ns, miss rate is 5%, and miss penalty is 80 ns, AMAT is 6 ns.",
    ]
    for text in examples:
        response = client.post("/routing/representation", json={"text": text})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["teaching_plan"]["contextPacket"]["currentText"] == text
        assert body["learning_object"]["type"] == body["teaching_plan"]["finalRepresentation"]
        assert body["learning_object"]["sourceText"] == text
