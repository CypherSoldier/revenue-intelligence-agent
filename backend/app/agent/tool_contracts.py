from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.agent.contracts import ModelTool, ModelToolCall


QueryValue = str | int | float | bool | None


class GetMetricCatalogArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunReadOnlyQueryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: Annotated[str, Field(min_length=1, max_length=64_000)]
    parameters: list[QueryValue] = Field(default_factory=list, max_length=100)


TOOL_ARGUMENT_MODELS: dict[str, type[BaseModel]] = {
    "get_metric_catalog": GetMetricCatalogArguments,
    "run_read_only_query": RunReadOnlyQueryArguments,
}

MODEL_TOOLS = (
    ModelTool(
        name="get_metric_catalog",
        description=(
            "Returns the approved revenue metric definition and allowed analytics "
            "schema. This tool takes no arguments."
        ),
        parameters=GetMetricCatalogArguments.model_json_schema(),
    ),
    ModelTool(
        name="run_read_only_query",
        description=(
            "Runs one read-only SELECT against the approved monthly_sales table. "
            "The server validates SQL, enforces timeout and row limits, and binds "
            "parameter values. Never include credentials or connection settings."
        ),
        parameters=RunReadOnlyQueryArguments.model_json_schema(),
    ),
)


class UnsupportedToolCallError(ValueError):
    code = "unsupported_tool"


def validate_tool_arguments(call: ModelToolCall) -> BaseModel:
    argument_model = TOOL_ARGUMENT_MODELS.get(call.name)
    if argument_model is None:
        raise UnsupportedToolCallError(
            f"The model requested unregistered tool '{call.name}'."
        )
    return argument_model.model_validate(call.arguments)
