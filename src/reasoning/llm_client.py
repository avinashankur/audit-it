
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from src.core.env import get_settings
from src.core.exceptions import (
    AuthenticationError,
    ConfigurationError,
    LLMProviderError,
    ModelResponseError,
    RateLimitExceededError,
)
from src.core.logging import get_logger, profile_stage

logger = get_logger(__name__)


class BaseLLMProvider(ABC):
    """Abstract interface for LLM provider adapters."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate response text from prompt and optional system instructions."""
        raise NotImplementedError


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider adapter using google-genai SDK."""

    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ConfigurationError("Gemini API key cannot be empty.")
        self.api_key = api_key.strip()
        try:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        except Exception as exc:
            raise ConfigurationError(f"Failed to initialize Gemini client: {exc}") from exc

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        target_model = model or self.DEFAULT_MODEL
        try:
            from google.genai import types

            config = None
            if system_prompt:
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                )

            response = self._client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=config,
            )
            text = response.text or ""
            if not text.strip():
                raise ModelResponseError(f"Gemini returned an empty response for model {target_model}")
            return text
        except Exception as exc:
            err_msg = str(exc)
            err_lower = err_msg.lower()
            if "api_key" in err_lower or "unauthenticated" in err_lower or "permission" in err_lower:
                raise AuthenticationError(f"Gemini authentication failed: {err_msg}", details={"provider": "gemini"}) from exc
            if "quota" in err_lower or "rate" in err_lower or "resource_exhausted" in err_lower:
                raise RateLimitExceededError(f"Gemini rate limit exceeded: {err_msg}", details={"provider": "gemini"}) from exc
            if isinstance(exc, (ModelResponseError, AuthenticationError, RateLimitExceededError)):
                raise
            raise LLMProviderError(f"Gemini request failed: {err_msg}", details={"provider": "gemini"}) from exc


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider adapter using official openai SDK."""

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ConfigurationError("OpenAI API key cannot be empty.")
        self.api_key = api_key.strip()
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key)
        except Exception as exc:
            raise ConfigurationError(f"Failed to initialize OpenAI client: {exc}") from exc

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        target_model = model or self.DEFAULT_MODEL
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=target_model,
                messages=messages,  # type: ignore[arg-type]
                **kwargs,
            )
            choices = response.choices
            if not choices or not choices[0].message or not choices[0].message.content:
                raise ModelResponseError(f"OpenAI returned an empty response for model {target_model}")
            return choices[0].message.content
        except Exception as exc:
            err_msg = str(exc)
            err_lower = err_msg.lower()
            if "auth" in err_lower or "incorrect api key" in err_lower or "401" in err_msg:
                raise AuthenticationError(f"OpenAI authentication failed: {err_msg}", details={"provider": "openai"}) from exc
            if "rate_limit" in err_lower or "quota" in err_lower or "429" in err_msg:
                raise RateLimitExceededError(f"OpenAI rate limit exceeded: {err_msg}", details={"provider": "openai"}) from exc
            if isinstance(exc, (ModelResponseError, AuthenticationError, RateLimitExceededError)):
                raise
            raise LLMProviderError(f"OpenAI request failed: {err_msg}", details={"provider": "openai"}) from exc


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider adapter using official anthropic SDK."""

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    def __init__(self, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ConfigurationError("Anthropic API key cannot be empty.")
        self.api_key = api_key.strip()
        try:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.api_key)
        except Exception as exc:
            raise ConfigurationError(f"Failed to initialize Anthropic client: {exc}") from exc

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        target_model = model or self.DEFAULT_MODEL
        max_tokens = kwargs.pop("max_tokens", 2048)

        call_kwargs: dict[str, Any] = {
            "model": target_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        if system_prompt:
            call_kwargs["system"] = system_prompt

        try:
            response = self._client.messages.create(**call_kwargs)
            content = response.content
            if not content:
                raise ModelResponseError(f"Anthropic returned an empty response for model {target_model}")
            text_blocks = [b.text for b in content if hasattr(b, "text")]
            full_text = "\n".join(text_blocks).strip()
            if not full_text:
                raise ModelResponseError(f"Anthropic returned no text content for model {target_model}")
            return full_text
        except Exception as exc:
            err_msg = str(exc)
            err_lower = err_msg.lower()
            if "auth" in err_lower or "api_key" in err_lower or "401" in err_msg or "permission" in err_lower:
                raise AuthenticationError(f"Anthropic authentication failed: {err_msg}", details={"provider": "anthropic"}) from exc
            if "rate_limit" in err_lower or "429" in err_msg or "overloaded" in err_lower:
                raise RateLimitExceededError(f"Anthropic rate limit exceeded: {err_msg}", details={"provider": "anthropic"}) from exc
            if isinstance(exc, (ModelResponseError, AuthenticationError, RateLimitExceededError)):
                raise
            raise LLMProviderError(f"Anthropic request failed: {err_msg}", details={"provider": "anthropic"}) from exc


class MockLLMProvider(BaseLLMProvider):
    """Deterministic provider for offline tests and simulations."""

    def __init__(self, response_generator: Callable[[str, str | None], str] | str | None = None) -> None:
        self.response_generator = response_generator

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        if callable(self.response_generator):
            return self.response_generator(prompt, system_prompt)
        if isinstance(self.response_generator, str):
            return self.response_generator
        return f"[MockLLM Analysis]\nQuery processed with system: {bool(system_prompt)}. Context length: {len(prompt)}."


class LLMClient:
    """Unified client orchestrating BYOK providers with automatic secret discovery."""

    PROVIDER_MAP = {
        "gemini": GeminiProvider,
        "google": GeminiProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "claude": AnthropicProvider,
        "mock": MockLLMProvider,
    }

    def __init__(
        self,
        provider: str = "mock",
        api_key: str | None = None,
        model: str | None = None,
        custom_provider: BaseLLMProvider | None = None,
    ) -> None:
        self.provider_name = provider.strip().lower()
        self.model = model
        self._provider: BaseLLMProvider

        if custom_provider is not None:
            self._provider = custom_provider
            return

        resolved_key = api_key
        if not resolved_key and self.provider_name not in ("mock", "offline"):
            resolved_key = get_settings().get_api_key(self.provider_name)

        if self.provider_name in ("mock", "offline"):
            self._provider = MockLLMProvider()
        elif self.provider_name in self.PROVIDER_MAP:
            provider_cls = self.PROVIDER_MAP[self.provider_name]
            if not resolved_key:
                raise ConfigurationError(
                    f"No API key provided for {self.provider_name}. "
                    f"Pass api_key or configure {self.provider_name.upper()}_API_KEY in .env.",
                    details={"provider": self.provider_name},
                )
            self._provider = provider_cls(api_key=resolved_key)  # type: ignore[call-arg]
        else:
            supported = ", ".join(sorted(set(self.PROVIDER_MAP.keys())))
            raise ConfigurationError(
                f"Unsupported LLM provider: '{provider}'. Supported providers: {supported}",
                details={"provider": provider},
            )

    @profile_stage("llm_generate")
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute text generation through the underlying configured provider."""
        target_model = model or self.model
        return self._provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=target_model,
            **kwargs,
        )

    @classmethod
    def create_mock(cls, response: str | Callable[[str, str | None], str] = "Mock audit response") -> LLMClient:
        """Create a lightweight mock client for tests."""
        return cls(provider="mock", custom_provider=MockLLMProvider(response))
