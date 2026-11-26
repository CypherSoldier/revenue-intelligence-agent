from pydantic import SecretStr

from app.agent.contracts import ModelMessage, ModelRequest
from app.config import Settings
from app.providers.gemini import GeminiProvider


def test_structured_output_uses_json_schema_generation_config():
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    request = ModelRequest(
        system_instruction="Return the requested JSON.",
        messages=[ModelMessage(role="user", content="Answer the question.")],
        response_schema=schema,
    )

    config = GeminiProvider._generation_config(object.__new__(GeminiProvider), request)

    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == schema
    assert config.response_schema is None


def test_gemini_developer_api_uses_beta_for_developer_instructions(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("app.providers.gemini.genai.Client", FakeClient)
    settings = Settings(
        gemini_api_key=SecretStr("test-only-key"),
        gemini_model="gemini-2.5-flash",
    )

    provider = GeminiProvider(settings)

    assert captured["http_options"].api_version == "v1beta"
    assert provider.model_name == "gemini-2.5-flash"


def test_generation_schema_drops_decoder_size_bounds_but_keeps_shape():
    schema = {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "maxItems": 50,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "maxLength": 4000},
                        "evidence_ids": {
                            "type": "array",
                            "maxItems": 20,
                            "items": {"type": "string", "format": "uuid"},
                        },
                    },
                    "required": ["text", "evidence_ids"],
                },
            }
        },
    }
    request = ModelRequest(
        system_instruction="Return the requested JSON.",
        messages=[ModelMessage(role="user", content="Answer the question.")],
        response_schema=schema,
    )

    config = GeminiProvider._generation_config(object.__new__(GeminiProvider), request)

    findings = config.response_json_schema["properties"]["findings"]
    text_schema = findings["items"]["properties"]["text"]
    ids_schema = findings["items"]["properties"]["evidence_ids"]
    assert "maxItems" not in findings
    assert "maxLength" not in text_schema
    assert "maxItems" not in ids_schema
    assert ids_schema["items"] == {"type": "string", "format": "uuid"}
    assert schema["properties"]["findings"]["maxItems"] == 50
