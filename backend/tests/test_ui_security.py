"""Security tests for UI graph rendering and XSS prevention."""

import html

from src.db.graph.store import GraphStore
from src.db.models.entities import FinancialMetricNode, MetricUnit, StatementType


def test_mermaid_html_injection_prevention():
    """Verify that malicious payload in metric name is properly escaped before HTML injection."""
    store = GraphStore.create(backend_type="networkx")
    malicious_payload = "</div><script>alert(1)</script>"

    store.add_metric_node(
        FinancialMetricNode(
            node_id="xss1",
            name=malicious_payload,
            normalized_key="xss_test",
            value=10.0,
            unit=MetricUnit.USD,
            period="2023",
            statement_type=StatementType.INCOME_STATEMENT,
            source_doc_id="d1",
            source_page=1,
        )
    )

    mermaid_code = store.to_mermaid(root_node=malicious_payload, hops=1)
    raw_mermaid = mermaid_code.replace("```mermaid", "").replace("```", "").strip()

    # The Mermaid raw output contains the payload string
    assert "<script>" in raw_mermaid

    # When escaped as in app.py:
    escaped_mermaid = html.escape(raw_mermaid)
    assert "<script>" not in escaped_mermaid
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in escaped_mermaid
    assert "&lt;/div&gt;" in escaped_mermaid
