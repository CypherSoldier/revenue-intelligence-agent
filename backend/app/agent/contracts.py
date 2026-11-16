from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModelTool(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    description: Annotated[str, Field(min_length=1, max_length=1000)]
    parameters: dict[str, Any]


class ModelToolCall(BaseModel):
    id: str | None = None
    name: Annotated[str, Field(min_length=1, max_length=64)]
    arguments: dict[str, Any] = Field(default_factory=dict)


class ModelMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "tool"]
    content: str | None = None
    tool_name: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    tool_call_id: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    tool_result: dict[str, Any] | None = None
    # Opaque provider replay state; never include this in reports or API responses.
    provider_context: str | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_role_content(self) -> "ModelMessage":
        if self.role == "user" and not self.content:
            raise ValueError("User messages require text content.")
        if self.role == "assistant" and not self.content and not self.provider_context:
            raise ValueError("Assistant messages require content or provider context.")
        if self.role == "tool" and (not self.tool_name or self.tool_result is None):
            raise ValueError("Tool messages require a name and structured result.")
        if self.role != "tool" and (self.tool_name or self.tool_result is not None):
            raise ValueError("Only tool messages can carry tool result fields.")
        return self


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_instruction: Annotated[str, Field(min_length=1, max_length=20_000)]
    messages: list[ModelMessage] = Field(min_length=1, max_length=64)
    tools: list[ModelTool] = Field(default_factory=list, max_length=16)
    response_schema: dict[str, Any] | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_output_tokens: int = Field(default=4096, ge=1, le=16_384)

class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    text: str | None = None
    tool_calls: list[ModelToolCall] = Field(default_factory=list, max_length=16)
    structured_output: dict[str, Any] | None = None
    # Gemini 3 function calls require this opaque history part on the next turn.
    provider_context: str | None = Field(default=None, exclude=True, repr=False)
    finish_reason: str | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
