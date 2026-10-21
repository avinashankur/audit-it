"""Test suite for LLMClient, multi-provider adapters, prompt builders, and QA integration."""

from unittest.mock import MagicMock, patch
import pytest

from src.core.exceptions import (
    AuthenticationError,
    ConfigurationError,
    LLMProviderError,
    ModelResponseError,
    RateLimitExceededError,
)
from src.reasoning.llm_client import (
    AnthropicProvider,
    GeminiProvider,
    LLMClient,
    MockLLMProvider,
    OpenAIProvider,
)
from src.reasoning.offline_engine import OfflineEngine, generate_offline_answer
from src.reasoning.prompts import (
    AUDIT_SYSTEM_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    build_audit_prompt,
    build_extraction_prompt,
)
from src.reasoning.qa_service import QAService
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.vector_store import VectorStore
from src.db.graph.store import GraphStore
from src.db.models.entities import FinancialMetricNode, MetricUnit, StatementType, TextChunk


def test_mock_llm_provider_generation():
    """Verify that MockLLMProvider produces expected responses."""
    # Default mock
    mock_provider = MockLLMProvider()
    resp = mock_provider.generate(prompt="What was revenue?", system_prompt="System instructions")
    assert "[MockLLM Analysis]" in resp
    assert "System instructions" not in resp  # default returns summary

    # Custom string
    mock_str = MockLLMProvider("Verified Gross Margin is $500M.")
    assert mock_str.generate("Query") == "Verified Gross Margin is $500M."

    # Callable generator
    mock_fn = MockLLMProvider(lambda p, s: f"Answer to {p}")
    assert mock_fn.generate("Net Sales") == "Answer to Net Sales"


def test_llm_client_initialization_and_mock():
    """Verify LLMClient initialization for mock and factory methods."""
    client = LLMClient.create_mock("Custom audit answer")
    ans = client.generate("Test query", system_prompt=AUDIT_SYSTEM_PROMPT)
    assert ans == "Custom audit answer"

    # Offline / mock provider name
    client_offline = LLMClient(provider="offline")
    assert "[MockLLM Analysis]" in client_offline.generate("Test")

    # Unsupported provider
    with pytest.raises(ConfigurationError) as exc_info:
        LLMClient(provider="unsupported_ai_service")
    assert "Unsupported LLM provider" in str(exc_info.value)


def test_llm_client_missing_api_key_raises_configuration_error():
    """Verify that configuring a live provider without an API key raises ConfigurationError."""
    with patch("src.reasoning.llm_client.get_settings") as mock_settings:
        mock_settings.return_value.get_api_key.return_value = None
        with pytest.raises(ConfigurationError) as exc_info:
            LLMClient(provider="gemini", api_key=None)
        assert "No API key provided for gemini" in str(exc_info.value)

        with pytest.raises(ConfigurationError):
            LLMClient(provider="openai", api_key="")

        with pytest.raises(ConfigurationError):
            LLMClient(provider="anthropic", api_key="")


def test_gemini_provider_success_and_error_handling():
    """Verify GeminiProvider calls Google GenAI SDK and maps errors accurately."""
    with patch("google.genai.Client") as mock_genai_client:
        mock_instance = MagicMock()
        mock_genai_client.return_value = mock_instance

        # 1. Successful generation
        mock_resp = MagicMock()
        mock_resp.text = "Gross margin was 42% on Page 14."
        mock_instance.models.generate_content.return_value = mock_resp

        provider = GeminiProvider(api_key="valid-test-key")
        result = provider.generate("Analyze margins", system_prompt="Audit instructions")
        assert result == "Gross margin was 42% on Page 14."
        mock_instance.models.generate_content.assert_called_once()

        # 2. Empty response error
        mock_resp.text = "   "
        with pytest.raises(ModelResponseError):
            provider.generate("Analyze margins")

        # 3. Authentication failure mapping
        mock_instance.models.generate_content.side_effect = Exception("API_KEY_INVALID: unauthenticated caller")
        with pytest.raises(AuthenticationError):
            provider.generate("Analyze margins")

        # 4. Quota / Rate limit failure mapping
        mock_instance.models.generate_content.side_effect = Exception("RESOURCE_EXHAUSTED: quota exceeded")
        with pytest.raises(RateLimitExceededError):
            provider.generate("Analyze margins")


def test_openai_provider_success_and_error_handling():
    """Verify OpenAIProvider calls OpenAI SDK and maps errors accurately."""
    with patch("openai.OpenAI") as mock_openai_client:
        mock_instance = MagicMock()
        mock_openai_client.return_value = mock_instance

        # 1. Successful generation
        mock_choice = MagicMock()
        mock_choice.message.content = "Operating income reached $250M."
        mock_choice.finish_reason = "stop"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_instance.chat.completions.create.return_value = mock_resp

        provider = OpenAIProvider(api_key="test-sk-key")
        result = provider.generate("What is operating income?", system_prompt="Audit expert")
        assert result == "Operating income reached $250M."

        # 2. Empty response error
        mock_choice.message.content = None
        with pytest.raises(ModelResponseError):
            provider.generate("Query")

        # 3. Truncated finish_reason='length' error
        mock_choice.message.content = "Cut off text..."
        mock_choice.finish_reason = "length"
        with pytest.raises(ModelResponseError) as exc_info:
            provider.generate("Query")
        assert "truncated by max token length" in str(exc_info.value)
        mock_choice.finish_reason = "stop"

        # 4. Authentication error mapping
        mock_instance.chat.completions.create.side_effect = Exception("401 incorrect api key provided")
        with pytest.raises(AuthenticationError):
            provider.generate("Query")

        # 5. Rate limit mapping
        mock_instance.chat.completions.create.side_effect = Exception("429 rate_limit exceeded")
        with pytest.raises(RateLimitExceededError):
            provider.generate("Query")


def test_anthropic_provider_success_and_error_handling():
    """Verify AnthropicProvider calls Anthropic SDK and maps errors accurately."""
    with patch("anthropic.Anthropic") as mock_anthropic_client:
        mock_instance = MagicMock()
        mock_anthropic_client.return_value = mock_instance

        # 1. Successful generation
        mock_block = MagicMock()
        mock_block.text = "Revenue expanded 15% year-over-year [Source: Page 10]."
        mock_resp = MagicMock()
        mock_resp.content = [mock_block]
        mock_resp.stop_reason = "end_turn"
        mock_instance.messages.create.return_value = mock_resp

        provider = AnthropicProvider(api_key="test-anthropic-key")
        result = provider.generate("Revenue growth?", system_prompt="Forensic auditor")
        assert result == "Revenue expanded 15% year-over-year [Source: Page 10]."

        # 2. Empty response error
        mock_resp.content = []
        with pytest.raises(ModelResponseError):
            provider.generate("Query")

        # 3. Authentication error mapping
        mock_instance.messages.create.side_effect = Exception("401 invalid api_key supplied")
        with pytest.raises(AuthenticationError):
            provider.generate("Query")

        # 4. Rate limit mapping
        mock_instance.messages.create.side_effect = Exception("429 rate_limit_error: request limit hit")
        with pytest.raises(RateLimitExceededError):
            provider.generate("Query")


def test_anthropic_provider_handles_truncated_max_tokens():
    """Verify AnthropicProvider retries when stop_reason is max_tokens, and raises ModelResponseError if still truncated."""
    with patch("anthropic.Anthropic") as mock_anthropic_client:
        mock_instance = MagicMock()
        mock_anthropic_client.return_value = mock_instance

        # 1. First call truncated, second call succeeds
        mock_resp_trunc = MagicMock()
        mock_resp_trunc.stop_reason = "max_tokens"
        mock_resp_trunc.content = [MagicMock(text="Partial text...")]

        mock_resp_success = MagicMock()
        mock_resp_success.stop_reason = "end_turn"
        mock_resp_success.content = [MagicMock(text="Full complete text [Page 1].")]

        mock_instance.messages.create.side_effect = [mock_resp_trunc, mock_resp_success]

        provider = AnthropicProvider(api_key="test-key")
        text = provider.generate("Prompt", max_tokens=100)
        assert text == "Full complete text [Page 1]."
        assert mock_instance.messages.create.call_count == 2

        # 2. Both calls truncated -> raises ModelResponseError
        mock_instance.messages.create.reset_mock()
        mock_instance.messages.create.side_effect = [mock_resp_trunc, mock_resp_trunc]
        with pytest.raises(ModelResponseError) as exc_info:
            provider.generate("Prompt", max_tokens=100)
        assert "stop_reason='max_tokens'" in str(exc_info.value)


def test_prompt_builders():
    """Verify prompt formatting functions generate correct structured text."""
    # Audit prompt
    context = "Reported Financial Metrics:\n- Revenue: $1,000M [Page 5]"
    prompt = build_audit_prompt(query="What was revenue?", context_str=context)
    assert "Verified Audit Context:" in prompt
    assert "Revenue: $1,000M [Page 5]" in prompt
    assert "User Audit Inquiry:" in prompt
    assert "What was revenue?" in prompt
    assert "Reported Financial Metrics" in prompt

    # Extraction prompt
    extract_p = build_extraction_prompt("Supply chain costs reduced margins by 150 bps.", page_number=18)
    assert "(Page 18)" in extract_p
    assert "Supply chain costs reduced margins by 150 bps." in extract_p
    assert "source_entity" in extract_p
    assert "target_entity" in extract_p


def test_qa_service_with_live_llm_client_mock():
    """Verify QAService successfully delegates generation to configured LLMClient."""
    graph_store = GraphStore.create(backend_type="networkx")
    graph_store.add_metric_node(
        FinancialMetricNode(
            node_id="m10",
            name="Gross Margin",
            normalized_key="gross_margin",
            value=650.0,
            unit=MetricUnit.USD,
            period="2024",
            statement_type=StatementType.INCOME_STATEMENT,
            source_doc_id="doc_qa_test",
            source_page=12,
        )
    )

    vec_store = VectorStore()
    retriever = HybridRetriever(vector_store=vec_store, graph_store=graph_store)

    # Inject mock LLM client that returns customized grounded answer
    mock_client = LLMClient.create_mock("LLM Analysis: Gross margin was $650.00 [Source: Page 12].")
    qa = QAService(retriever=retriever, llm_client=mock_client)

    resp = qa.answer_query(query="What was gross margin?", provider="Gemini", api_key="dummy-key")
    assert resp.answer_text == "LLM Analysis: Gross margin was $650.00 [Source: Page 12]."
    assert resp.model_provider == "Gemini"
    assert len(resp.citations) >= 1


def test_qa_service_configured_client_without_api_key():
    """Verify that a supplied llm_client is executed even when api_key is None and settings has no key."""
    graph_store = GraphStore.create(backend_type="networkx")
    graph_store.add_metric_node(
        FinancialMetricNode(
            node_id="m15",
            name="Revenue",
            normalized_key="revenue",
            value=1200.0,
            unit=MetricUnit.USD,
            period="2024",
            statement_type=StatementType.INCOME_STATEMENT,
            source_doc_id="doc_keyless",
            source_page=4,
        )
    )
    vec_store = VectorStore()
    retriever = HybridRetriever(vector_store=vec_store, graph_store=graph_store)

    mock_client = MagicMock()
    mock_client.generate.return_value = "Live response from configured client [Page 4]."

    qa = QAService(retriever=retriever, llm_client=mock_client)

    with patch("src.reasoning.qa_service.get_settings") as mock_settings:
        mock_settings.return_value.get_api_key.return_value = None
        resp = qa.answer_query(query="What was revenue?", provider="OpenAI", api_key=None)

    # Verify mock_client.generate was called and offline engine was NOT used
    mock_client.generate.assert_called_once()
    assert resp.answer_text == "Live response from configured client [Page 4]."


def test_qa_service_live_failure_falls_back_to_offline_engine():
    """Verify that if a live LLM provider throws an exception, QAService falls back gracefully to local offline engine."""
    graph_store = GraphStore.create(backend_type="networkx")
    graph_store.add_metric_node(
        FinancialMetricNode(
            node_id="m20",
            name="Operating Income",
            normalized_key="operating_income",
            value=320.0,
            unit=MetricUnit.USD,
            period="2024",
            statement_type=StatementType.INCOME_STATEMENT,
            source_doc_id="doc_fallback_test",
            source_page=16,
        )
    )

    vec_store = VectorStore()
    retriever = HybridRetriever(vector_store=vec_store, graph_store=graph_store)

    # Create mock client that raises an error
    failing_provider = MagicMock()
    failing_provider.generate.side_effect = LLMProviderError("Remote API Connection Timeout")
    failing_client = LLMClient(provider="mock", custom_provider=failing_provider)

    qa = QAService(retriever=retriever, llm_client=failing_client)
    resp = qa.answer_query(query="What was operating income?", provider="OpenAI", api_key="mock-key")

    # Verify fallback notice and verified local analysis
    assert "Live OpenAI call encountered an error" in resp.answer_text
    assert "Remote API Connection Timeout" in resp.answer_text
    assert "Operating Income" in resp.answer_text
    assert "320" in resp.answer_text
    assert "Page 16" in resp.answer_text
