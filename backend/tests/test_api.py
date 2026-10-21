"""Integration tests for AuditIt FastAPI backend."""

import time
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.session_mgr import get_session_manager


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "networkx" in data["backends_available"]


def test_list_samples(client):
    response = client.get("/api/samples")
    assert response.status_code == 200
    samples = response.json()
    assert isinstance(samples, list)
    assert len(samples) > 0
    sample_names = [s["name"] for s in samples]
    assert any("DrinkPAK" in name or "EOS" in name for name in sample_names)


def test_invalid_sample_load(client):
    response = client.post("/api/samples/NonExistent_10K_9999.pdf/load")
    assert response.status_code == 404


def test_upload_invalid_file_extension(client):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_empty_file(client):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400


def test_end_to_end_sample_ingest_and_query(client):
    # 1. Get first sample report
    samples_resp = client.get("/api/samples")
    assert samples_resp.status_code == 200
    first_sample = samples_resp.json()[0]["name"]

    # 2. Trigger load
    load_resp = client.post(f"/api/samples/{first_sample}/load")
    assert load_resp.status_code == 200
    job_data = load_resp.json()
    job_id = job_data["job_id"]
    doc_id = job_data["document_id"]
    assert job_id
    assert doc_id

    # 3. Poll job until complete (with timeout)
    timeout = 30.0
    start = time.time()
    job_status = "PROCESSING"
    while time.time() - start < timeout:
        poll_resp = client.get(f"/api/documents/jobs/{job_id}")
        assert poll_resp.status_code == 200
        status_data = poll_resp.json()
        job_status = status_data["status"]
        if job_status in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.5)

    assert job_status == "COMPLETED"

    # 4. Check document metadata
    doc_resp = client.get(f"/api/documents/{doc_id}")
    assert doc_resp.status_code == 200
    doc_info = doc_resp.json()
    assert doc_info["document_id"] == doc_id
    assert doc_info["total_pages"] >= 1
    assert doc_info["status"] == "Ready"

    # 5. Check graph retrieval
    graph_resp = client.get(f"/api/documents/{doc_id}/graph")
    assert graph_resp.status_code == 200
    graph_data = graph_resp.json()
    assert "nodes" in graph_data
    assert "edges" in graph_data
    assert len(graph_data["nodes"]) > 0

    # 6. Execute synchronous audit query
    query_resp = client.post(
        f"/api/documents/{doc_id}/query",
        json={
            "query_text": "What drove changes in revenue or gross margin?",
            "model_provider": "Offline Grounded",
        },
    )
    assert query_resp.status_code == 200
    query_data = query_resp.json()
    assert query_data["query_text"] == "What drove changes in revenue or gross margin?"
    assert len(query_data["answer_text"]) > 0
    assert "citations" in query_data

    # 7. Execute streaming audit query
    stream_resp = client.post(
        f"/api/documents/{doc_id}/query/stream",
        json={
            "query_text": "Explain operating income drivers",
            "model_provider": "Offline Grounded",
        },
    )
    assert stream_resp.status_code == 200
    stream_text = stream_resp.text
    assert "event: start" in stream_text
    assert "event: token" in stream_text
    assert "event: done" in stream_text
