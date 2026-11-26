import json
from typing import Any

from google import genai
from google.genai import errors, types

from app.agent.contracts import ModelMessage, ModelRequest, ModelResponse, ModelToolCall
from app.config import Settings
from app.providers.errors import (
    ModelProviderError,
    ProviderConfigurationError,
    ProviderResponseError,
    provider_http_error,
)

_GENERATION_SCHEMA_LIMIT_KEYS = {
    "maximum",
    "maxItems",
    "maxLength",
    "minimum",
    "minItems",
    "minLength",
}


def _generation_json_schema(value):
    """Remove size bounds that make Gemini's constrained decoder too complex.

    The provider schema guides generation. Pydantic still enforces every original
    bound on the returned object before the application uses it.
    """
    if isinstance(value, dict):
        return {
            key: _generation_json_schema(item)
            for key, item in value.items()
            if key not in _GENERATION_SCHEMA_LIMIT_KEYS
        }
    if isinstance(value, list):
        return [_generation_json_schema(item) for item in value]
    return value


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_configured or settings.gemini_api_key is None:
            raise ProviderConfigurationError(
                "model_not_configured",
                "Set GEMINI_API_KEY in backend/.env before requesting model generation.",
                provider=self.provider_name,
            )
        self.model_name = settings.gemini_model
        self._client = genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(api_version="v1beta"),
        )

    def generate(self, request: ModelRequest) -> ModelResponse:
        config = self._generation_config(request)
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=self._contents(request.messages),
                config=config,
            )
        except errors.APIError as error:
            raise provider_http_error(error.code) from error
        except Exception as error:
            raise ModelProviderError(
                "provider_transport_error",
                "The model provider could not be reached. Check the network and try again.",
                provider=self.provider_name,
                retryable=True,
            ) from error

        try:
            return self._normalize_response(response, request)
        except ModelProviderError:
            raise
        except Exception as error:
            raise ProviderResponseError(
                "invalid_provider_response",
                "The model provider returned a response the adapter could not read.",
                provider=self.provider_name,
            ) from error

    def close(self) -> None:
        self._client.close()

    def _generation_config(self, request: ModelRequest) -> types.GenerateContentConfig:
        config: dict[str, Any] = {
            "system_instruction": request.system_instruction,
            "temperature": request.temperature,
            "max_output_tokens": request.max_output_tokens,
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        }
        if request.response_schema is not None:
            config["response_mime_type"] = "application/json"
            config["response_json_schema"] = _generation_json_schema(
                request.response_schema
            )
        if request.tools:
            config["tools"] = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description,
                            parameters_json_schema=tool.parameters,
                        )
                        for tool in request.tools
                    ]
                )
            ]
        return types.GenerateContentConfig(**config)

    @staticmethod
    def _contents(messages: list[ModelMessage]) -> list[types.Content]:
        contents: list[types.Content] = []
        for message in messages:
            if message.role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=message.content)],
                    )
                )
            elif message.role == "assistant":
                if message.provider_context:
                    contents.append(
                        types.Content.model_validate_json(message.provider_context)
                    )
                else:
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[types.Part(text=message.content)],
                        )
                    )
            else:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    id=message.tool_call_id,
                                    name=message.tool_name,
                                    response=message.tool_result,
                                )
                            )
                        ],
                    )
                )
        return contents

    def _normalize_response(
        self, response: Any, request: ModelRequest
    ) -> ModelResponse:
        candidates = response.candidates or []
        if not candidates or candidates[0].content is None:
            raise ProviderResponseError(
                "empty_provider_response",
                "The model provider returned no candidate content.",
                provider=self.provider_name,
            )

        candidate = candidates[0]
        text_parts: list[str] = []
        tool_calls: list[ModelToolCall] = []
        for part in candidate.content.parts or []:
            # Thought parts are intentionally omitted from application-visible output.
            if getattr(part, "thought", False):
                continue
            if part.text:
                text_parts.append(part.text)
            function_call = part.function_call
            if function_call is not None:
                if not function_call.name:
                    raise ProviderResponseError(
                        "invalid_tool_call",
                        "The model provider returned a tool call without a name.",
                        provider=self.provider_name,
                    )
                tool_calls.append(
                    ModelToolCall(
                        id=function_call.id,
                        name=function_call.name,
                        arguments=function_call.args or {},
                    )
                )

        text = "\n".join(text_parts).strip() or None
        structured_output = None
        if request.response_schema is not None:
            if text is None:
                raise ProviderResponseError(
                    "missing_structured_output",
                    "The model provider returned no structured output.",
                    provider=self.provider_name,
                )
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError as error:
                raise ProviderResponseError(
                    "invalid_structured_output",
                    "The model provider returned output that was not valid JSON.",
                    provider=self.provider_name,
                ) from error
            if not isinstance(decoded, dict):
                raise ProviderResponseError(
                    "invalid_structured_output",
                    "The model provider returned JSON that was not an object.",
                    provider=self.provider_name,
                )
            structured_output = decoded

        usage = response.usage_metadata
        finish_reason = candidate.finish_reason
        if finish_reason is not None and hasattr(finish_reason, "name"):
            finish_reason = finish_reason.name

        return ModelResponse(
            provider=self.provider_name,
            model=self.model_name,
            text=text,
            tool_calls=tool_calls,
            structured_output=structured_output,
            provider_context=candidate.content.model_dump_json(exclude_none=True),
            finish_reason=str(finish_reason) if finish_reason is not None else None,
            prompt_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
        )
