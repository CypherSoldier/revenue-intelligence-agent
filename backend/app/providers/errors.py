class ModelProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        provider: str,
        retryable: bool = False,
        http_status: int | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.provider = provider
        self.retryable = retryable
        self.http_status = http_status
        super().__init__(message)


class ProviderConfigurationError(ModelProviderError):
    def __init__(self, code: str, message: str, *, provider: str) -> None:
        super().__init__(code, message, provider=provider)


class ProviderResponseError(ModelProviderError):
    def __init__(self, code: str, message: str, *, provider: str) -> None:
        super().__init__(code, message, provider=provider)


def provider_http_error(status_code: int) -> ModelProviderError:
    if status_code == 429:
        return ModelProviderError(
            "provider_rate_limited",
            "The model provider is rate limiting requests. Try again shortly.",
            provider="gemini",
            retryable=True,
            http_status=status_code,
        )
    if status_code in {401, 403}:
        return ModelProviderError(
            "provider_authentication_failed",
            "The model provider rejected the server credential. Check GEMINI_API_KEY.",
            provider="gemini",
            http_status=status_code,
        )
    if status_code >= 500:
        return ModelProviderError(
            "provider_unavailable",
            "The model provider is temporarily unavailable. Try again later.",
            provider="gemini",
            retryable=True,
            http_status=status_code,
        )
    return ModelProviderError(
        "provider_request_failed",
        "The model provider rejected the generation request. Check the model and request configuration.",
        provider="gemini",
        http_status=status_code,
    )
