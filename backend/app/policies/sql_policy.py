from dataclasses import dataclass

from sqlglot import ErrorLevel, exp, parse
from sqlglot.errors import ParseError


APPROVED_TABLES = frozenset({"monthly_sales"})
BLOCKED_FUNCTIONS = frozenset({"load_extension", "readfile", "writefile"})


class QueryPolicyError(ValueError):
    """A query rejected before it is submitted to SQLite."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str
    returns_at_most: int | None


def validate_query(sql: str, *, max_rows: int) -> ValidatedQuery:
    if not sql or not sql.strip():
        raise QueryPolicyError("empty_query", "Provide one read-only SELECT query.")

    try:
        statements = [
            statement
            for statement in parse(sql, read="sqlite", error_level=ErrorLevel.RAISE)
            if statement is not None
        ]
    except ParseError as error:
        raise QueryPolicyError(
            "invalid_sql", "The SQL could not be parsed as a SQLite query."
        ) from error

    if len(statements) != 1:
        raise QueryPolicyError(
            "single_statement_required", "Submit exactly one SQL statement per query."
        )

    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise QueryPolicyError(
            "read_only_select_required", "Only SELECT queries are permitted."
        )

    forbidden_types = tuple(
        expression_type
        for expression_type in (
            getattr(exp, "Insert", None),
            getattr(exp, "Update", None),
            getattr(exp, "Delete", None),
            getattr(exp, "Create", None),
            getattr(exp, "Drop", None),
            getattr(exp, "Alter", None),
            getattr(exp, "Command", None),
            getattr(exp, "Merge", None),
            getattr(exp, "TruncateTable", None),
            getattr(exp, "Pragma", None),
            getattr(exp, "Transaction", None),
            getattr(exp, "Attach", None),
            getattr(exp, "Detach", None),
            getattr(exp, "Into", None),
            getattr(exp, "Values", None),
        )
        if expression_type is not None
    )
    if any(isinstance(node, forbidden_types) for node in statement.walk()):
        raise QueryPolicyError(
            "read_only_select_required", "Only read-only SELECT queries are permitted."
        )

    for function in statement.find_all(exp.Anonymous):
        if function.name.casefold() in BLOCKED_FUNCTIONS:
            raise QueryPolicyError(
                "function_not_allowed",
                f"The SQLite function '{function.name}' is not permitted.",
            )

    cte_names = {
        cte.alias_or_name.casefold()
        for cte in statement.find_all(exp.CTE)
        if cte.alias_or_name
    }
    for table in statement.find_all(exp.Table):
        if table.catalog or table.db:
            raise QueryPolicyError(
                "object_not_allowed",
                "Database-qualified table references are not permitted.",
            )
        if table.name.casefold() in cte_names:
            continue
        if table.name.casefold() not in APPROVED_TABLES:
            raise QueryPolicyError(
                "object_not_allowed",
                f"The object '{table.name}' is not in the approved analytics schema.",
            )

    offset = statement.args.get("offset")
    if offset is not None:
        _non_negative_integer(offset.args.get("expression"), "OFFSET")

    limit = statement.args.get("limit")
    if limit is not None:
        requested_limit = _non_negative_integer(limit.args.get("expression"), "LIMIT")
        if requested_limit > max_rows:
            raise QueryPolicyError(
                "row_limit_exceeded",
                f"LIMIT cannot exceed the configured {max_rows}-row result cap.",
            )
        return ValidatedQuery(statement.sql(dialect="sqlite"), requested_limit)

    bounded = statement.copy().limit(max_rows + 1, copy=False)
    return ValidatedQuery(bounded.sql(dialect="sqlite"), max_rows + 1)


def _non_negative_integer(expression: exp.Expression | None, name: str) -> int:
    if (
        not isinstance(expression, exp.Literal)
        or not expression.is_number
        or not str(expression.this).isdigit()
    ):
        raise QueryPolicyError(
            "invalid_row_limit", f"{name} must be a non-negative integer literal."
        )
    return int(expression.this)
