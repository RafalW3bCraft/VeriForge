from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_health():
    assert client.get("/health").status_code == 200

def test_analysis_demo():
    r = client.post("/api/v1/analyze", json={
        "content": "URGENT: Your GitHub account is suspended. Sign in now at https://github-security-check.zip and enter your password.",
        "input_type": "message"
    })
    assert r.status_code == 200
    data = r.json()
    assert 0 <= data["score"] <= 100
    assert data["verdict"] in {"SAFE","LOW","SUSPICIOUS","HIGH","CRITICAL"}
