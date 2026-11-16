from hashlib import sha256
from threading import Lock

from app.config import Settings, get_settings
from app.providers.base import ModelProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.gemini import GeminiProvider


_PROVIDER_BUILDERS = {"gemini": GeminiProvider}
_PROVIDERS: dict[tuple[str, str, str], ModelProvider] = {}
_PROVIDER_LOCK = Lock()


def validate_provider_configuration(
    settings: Settings | None = None,
    *,
    require_credentials: bool = False,
) -> None:
    settings = settings or get_settings()
    if settings.llm_provider not in _PROVIDER_BUILDERS:
        raise ProviderConfigurationError(
            "unsupported_provider",
            f"LLM_PROVIDER '{settings.llm_provider}' has no registered adapter.",
            provider=settings.llm_provider,
        )
    if not settings.gemini_model.strip():
        raise ProviderConfigurationError(
            "model_not_configured",
            "Set GEMINI_MODEL to a non-empty model ID.",
            provider=settings.llm_provider,
        )
    if require_credentials and not settings.gemini_configured:
        raise ProviderConfigurationError(
            "model_not_configured",
            "Set GEMINI_API_KEY in backend/.env before submitting an investigation.",
            provider=settings.llm_provider,
        )


def get_model_provider(settings: Settings | None = None) -> ModelProvider:
    settings = settings or get_settings()
    validate_provider_configuration(settings, require_credentials=True)
    assert settings.gemini_api_key is not None
    cache_key = (
        settings.llm_provider,
        settings.gemini_model,
        sha256(settings.gemini_api_key.get_secret_value().encode()).hexdigest(),
    )
    with _PROVIDER_LOCK:
        provider = _PROVIDERS.get(cache_key)
        if provider is None:
            provider_builder = _PROVIDER_BUILDERS[settings.llm_provider]
            provider = provider_builder(settings)
            _PROVIDERS[cache_key] = provider
        return provider


def close_model_providers() -> None:
    with _PROVIDER_LOCK:
        providers = list(_PROVIDERS.values())
        _PROVIDERS.clear()
    for provider in providers:
        provider.close()
