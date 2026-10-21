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
    assert "empty" in response.json()["detail"].lower()


def test_upload_invalid_pdf_magic_bytes(client):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("fake.pdf", b"this is text content not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert "valid pdf header" in response.json()["detail"].lower()


def test_upload_oversized_file_rejected(client, monkeypatch):
    from src.core.env import get_settings

    # Set limit to 1MB for testing
    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)

    # 1.5MB of content
    large_pdf = b"%PDF-1.4\n" + (b"0" * (1500 * 1024))
    response = client.post(
        "/api/documents/upload",
        files={"file": ("large.pdf", large_pdf, "application/pdf")},
    )
    assert response.status_code == 413
    assert "maximum allowed size" in response.json()["detail"].lower()


def test_upload_rejected_when_queue_at_capacity(client, monkeypatch):
    from src.api.schemas import IngestJobStatus
    from src.api.session_mgr import get_session_manager

    mgr = get_session_manager()
    monkeypatch.setattr(mgr, "max_active_jobs", 2)

    # Mock 2 active processing jobs
    mgr.jobs["mock_job_1"] = IngestJobStatus(
        job_id="mock_job_1",
        document_id="doc1",
        filename="f1.pdf",
        status="PROCESSING",
        stage="parsing",
        progress=20,
    )
    mgr.jobs["mock_job_2"] = IngestJobStatus(
        job_id="mock_job_2",
        document_id="doc2",
        filename="f2.pdf",
        status="PROCESSING",
        stage="parsing",
        progress=20,
    )

    valid_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    response = client.post(
        "/api/documents/upload",
        files={"file": ("queued.pdf", valid_pdf, "application/pdf")},
    )
    assert response.status_code == 429
    assert "maximum concurrent ingestion jobs" in response.json()["detail"].lower()

    # Clean up mock jobs
    mgr.jobs.pop("mock_job_1", None)
    mgr.jobs.pop("mock_job_2", None)


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


def test_session_document_isolation(client):
    """Verify that documents, graphs, tables, and queries are isolated between sessions."""
    headers_user_a = {"X-Session-ID": "user_session_a"}
    headers_user_b = {"X-Session-ID": "user_session_b"}

    # 1. User A loads sample report
    samples_resp = client.get("/api/samples", headers=headers_user_a)
    assert samples_resp.status_code == 200
    first_sample = samples_resp.json()[0]["name"]

    load_resp = client.post(f"/api/samples/{first_sample}/load", headers=headers_user_a)
    assert load_resp.status_code == 200
    job_data = load_resp.json()
    job_id = job_data["job_id"]
    doc_id = job_data["document_id"]

    # Poll until ready for User A
    timeout = 30.0
    start = time.time()
    while time.time() - start < timeout:
        poll_resp = client.get(f"/api/documents/jobs/{job_id}", headers=headers_user_a)
        if poll_resp.status_code == 200 and poll_resp.json()["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.5)

    assert poll_resp.json()["status"] == "COMPLETED"

    # User A sees doc_id in document list
    docs_a = client.get("/api/documents", headers=headers_user_a).json()
    doc_ids_a = [d["document_id"] for d in docs_a]
    assert doc_id in doc_ids_a

    # User B lists documents: should NOT see User A's document
    docs_b = client.get("/api/documents", headers=headers_user_b).json()
    doc_ids_b = [d["document_id"] for d in docs_b]
    assert doc_id not in doc_ids_b

    # User B attempts to access User A's job -> 404
    job_b_resp = client.get(f"/api/documents/jobs/{job_id}", headers=headers_user_b)
    assert job_b_resp.status_code == 404

    # User B attempts to access User A's document metadata -> 404
    doc_b_resp = client.get(f"/api/documents/{doc_id}", headers=headers_user_b)
    assert doc_b_resp.status_code == 404

    # User B attempts to access User A's tables -> 404
    tables_b_resp = client.get(f"/api/documents/{doc_id}/tables", headers=headers_user_b)
    assert tables_b_resp.status_code == 404

    # User B attempts to access User A's graph -> 404
    graph_b_resp = client.get(f"/api/documents/{doc_id}/graph", headers=headers_user_b)
    assert graph_b_resp.status_code == 404

    # User B attempts to query User A's document -> 404
    query_b_resp = client.post(
        f"/api/documents/{doc_id}/query",
        json={"query_text": "What is revenue?", "model_provider": "Offline Grounded"},
        headers=headers_user_b,
    )
    assert query_b_resp.status_code == 404

    # User B attempts to stream query User A's document -> 404
    stream_b_resp = client.post(
        f"/api/documents/{doc_id}/query/stream",
        json={"query_text": "What is revenue?", "model_provider": "Offline Grounded"},
        headers=headers_user_b,
    )
    assert stream_b_resp.status_code == 404

    # User B attempts to delete User A's document -> 404
    delete_b_resp = client.delete(f"/api/documents/{doc_id}", headers=headers_user_b)
    assert delete_b_resp.status_code == 404

    # User A can successfully access, query, and delete their own document
    doc_a_resp = client.get(f"/api/documents/{doc_id}", headers=headers_user_a)
    assert doc_a_resp.status_code == 200

    query_a_resp = client.post(
        f"/api/documents/{doc_id}/query",
        json={"query_text": "What is revenue?", "model_provider": "Offline Grounded"},
        headers=headers_user_a,
    )
    assert query_a_resp.status_code == 200

    delete_a_resp = client.delete(f"/api/documents/{doc_id}", headers=headers_user_a)
    assert delete_a_resp.status_code == 200


def test_query_model_provider_resolution(client):
    """Verify body model_provider is optional and falls back to X-LLM-Provider before offline default."""
    # 1. Load sample report
    samples_resp = client.get("/api/samples")
    assert samples_resp.status_code == 200
    first_sample = samples_resp.json()[0]["name"]

    load_resp = client.post(f"/api/samples/{first_sample}/load")
    assert load_resp.status_code == 200
    job_id = load_resp.json()["job_id"]
    doc_id = load_resp.json()["document_id"]

    timeout = 30.0
    start = time.time()
    while time.time() - start < timeout:
        poll_resp = client.get(f"/api/documents/jobs/{job_id}")
        if poll_resp.status_code == 200 and poll_resp.json()["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.5)

    assert poll_resp.json()["status"] == "COMPLETED"

    # Case A: Omit model_provider in body, no X-LLM-Provider header -> defaults to "Offline Grounded"
    resp_default = client.post(
        f"/api/documents/{doc_id}/query",
        json={"query_text": "What are operating revenues?"},
    )
    assert resp_default.status_code == 200
    assert resp_default.json()["model_provider"] == "Offline Grounded"

    # Case B: Omit model_provider in body, set X-LLM-Provider header -> uses header value
    resp_header = client.post(
        f"/api/documents/{doc_id}/query",
        json={"query_text": "What are operating revenues?"},
        headers={"X-LLM-Provider": "Gemini"},
    )
    assert resp_header.status_code == 200
    assert resp_header.json()["model_provider"] == "Gemini"

    # Case C: Provide model_provider in body -> body overrides X-LLM-Provider header
    resp_override = client.post(
        f"/api/documents/{doc_id}/query",
        json={"query_text": "What are operating revenues?", "model_provider": "OpenAI"},
        headers={"X-LLM-Provider": "Gemini"},
    )
    assert resp_override.status_code == 200
    assert resp_override.json()["model_provider"] == "OpenAI"

    # Case D: Streaming query honors X-LLM-Provider when body omits it
    stream_resp = client.post(
        f"/api/documents/{doc_id}/query/stream",
        json={"query_text": "Explain operating revenue"},
        headers={"X-LLM-Provider": "Anthropic"},
    )
    assert stream_resp.status_code == 200
    assert '"provider": "Anthropic"' in stream_resp.text


