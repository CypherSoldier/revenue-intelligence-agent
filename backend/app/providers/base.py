from typing import Protocol

from app.agent.contracts import ModelRequest, ModelResponse


class ModelProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(self, request: ModelRequest) -> ModelResponse: ...

    def close(self) -> None: ...
