import sqlite3

import pytest

from app.data.seed import seed_analytics_database
from app.database.analytics_repository import (
    AnalyticsQueryError,
    AnalyticsRepository,
    QueryResultLimitExceeded,
    QueryTimeoutError,
)
from app.policies.sql_policy import QueryPolicyError, ValidatedQuery, validate_query


@pytest.fixture
def analytics_db(tmp_path):
    return seed_analytics_database(tmp_path / "analytics.sqlite3")


def test_allowed_select_returns_seeded_evidence(analytics_db):
    repository = AnalyticsRepository(analytics_db)

    result = repository.execute_query(
        """
        SELECT SUM(net_revenue_usd) AS total_usd
        FROM monthly_sales
        WHERE month_start >= '2025-01-01' AND month_start < '2025-04-01'
        """
    )

    assert result.columns == ["total_usd"]
    assert result.rows == [[1_200_000]]
    assert result.row_count == 1


def test_seeded_golden_facts_cover_all_documented_periods_and_regions(analytics_db):
    repository = AnalyticsRepository(analytics_db)
    result = repository.execute_query(
        """
        SELECT month_start, region, SUM(net_revenue_usd) AS total_usd
        FROM monthly_sales
        GROUP BY month_start, region
        ORDER BY month_start, region
        """
    )
    monthly = {}
    quarterly = {"Q1": {}, "Q2": {}}
    for month, region, value in result.rows:
        monthly.setdefault(month[:7], 0)
        monthly[month[:7]] += value
        quarter = "Q1" if month < "2025-04" else "Q2"
        quarterly[quarter][region] = quarterly[quarter].get(region, 0) + value

    q1_total = sum(quarterly["Q1"].values())
    q2_total = sum(quarterly["Q2"].values())
    assert monthly == {
        "2025-01": 390_000,
        "2025-02": 400_000,
        "2025-03": 410_000,
        "2025-04": 330_000,
        "2025-05": 335_000,
        "2025-06": 335_000,
    }
    assert quarterly == {
        "Q1": {"North": 400_000, "South": 450_000, "West": 350_000},
        "Q2": {"North": 360_000, "South": 400_000, "West": 240_000},
    }
    assert (q1_total, q2_total, q2_total - q1_total) == (1_200_000, 1_000_000, -200_000)
    assert round((q2_total - q1_total) / q1_total * 100, 1) == -16.7
    assert round((quarterly["Q2"]["West"] - quarterly["Q1"]["West"]) / quarterly["Q1"]["West"] * 100, 1) == -31.4


def test_allowed_cte_and_region_breakdown(analytics_db):
    repository = AnalyticsRepository(analytics_db)

    result = repository.execute_query(
        """
        WITH q2 AS (
            SELECT region, SUM(net_revenue_usd) AS total_usd
            FROM monthly_sales
            WHERE month_start >= '2025-04-01'
            GROUP BY region
        )
        SELECT region, total_usd FROM q2 ORDER BY region
        """
    )

    assert result.rows == [
        ["North", 360_000],
        ["South", 400_000],
        ["West", 240_000],
    ]


def test_query_values_are_passed_as_bound_parameters(analytics_db):
    repository = AnalyticsRepository(analytics_db)

    result = repository.execute_query(
        """
        SELECT SUM(net_revenue_usd) AS total_usd
        FROM monthly_sales
        WHERE month_start >= ? AND month_start < ? AND region = ?
        """,
        ("2025-01-01", "2025-04-01", "South"),
    )

    assert result.rows == [[450_000]]


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE monthly_sales SET net_revenue_usd = 0",
        "DELETE FROM monthly_sales",
        "INSERT INTO monthly_sales VALUES ('2025-07-01', 'North', 1)",
        "DROP TABLE monthly_sales",
        "PRAGMA table_info(monthly_sales)",
        "ATTACH DATABASE 'other.sqlite3' AS other",
        "SELECT 1 UNION VALUES (2)",
    ],
)
def test_rejects_writes_ddl_and_pragma(sql):
    with pytest.raises(QueryPolicyError) as error:
        validate_query(sql, max_rows=100)

    assert error.value.code == "read_only_select_required"


def test_rejects_multiple_statements_before_opening_database(tmp_path):
    database_path = tmp_path / "must-not-be-opened.sqlite3"
    repository = AnalyticsRepository(database_path)

    with pytest.raises(QueryPolicyError) as error:
        repository.execute_query("SELECT 1; SELECT 2")

    assert error.value.code == "single_statement_required"
    assert not database_path.exists()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT name FROM sqlite_master",
        "SELECT * FROM customer_records",
        "SELECT * FROM pragma_table_info('monthly_sales')",
        "SELECT * FROM main.monthly_sales",
    ],
)
def test_rejects_disallowed_objects(sql):
    with pytest.raises(QueryPolicyError) as error:
        validate_query(sql, max_rows=100)

    assert error.value.code == "object_not_allowed"


def test_rejects_explicit_limit_over_cap_before_database_open(tmp_path):
    database_path = tmp_path / "must-not-be-opened.sqlite3"
    repository = AnalyticsRepository(database_path, max_rows=3)

    with pytest.raises(QueryPolicyError) as error:
        repository.execute_query("SELECT * FROM monthly_sales LIMIT 4")

    assert error.value.code == "row_limit_exceeded"
    assert not database_path.exists()


def test_result_without_explicit_limit_is_bounded_and_rejected_when_too_large(
    analytics_db,
):
    repository = AnalyticsRepository(analytics_db, max_rows=3)

    with pytest.raises(QueryResultLimitExceeded) as error:
        repository.execute_query("SELECT * FROM monthly_sales")

    assert error.value.code == "result_row_limit_exceeded"


def test_empty_result_is_returned_as_empty_not_as_a_failure(analytics_db):
    result = AnalyticsRepository(analytics_db).execute_query(
        "SELECT region FROM monthly_sales WHERE month_start >= ?", ("2030-01-01",)
    )

    assert result.columns == ["region"]
    assert result.rows == []
    assert result.row_count == 0


def test_missing_database_returns_structured_database_error(tmp_path):
    repository = AnalyticsRepository(tmp_path / "missing.sqlite3")

    with pytest.raises(AnalyticsQueryError) as error:
        repository.execute_query("SELECT SUM(net_revenue_usd) FROM monthly_sales")

    assert error.value.code == "analytics_database_unavailable"


def test_rejects_non_integer_or_negative_limits():
    for sql in (
        "SELECT 1 LIMIT 1.5",
        "SELECT 1 LIMIT -1",
        "SELECT 1 LIMIT 1 OFFSET -2",
    ):
        with pytest.raises(QueryPolicyError) as error:
            validate_query(sql, max_rows=100)
        assert error.value.code == "invalid_row_limit"


def test_sqlite_progress_handler_enforces_timeout(analytics_db):
    repository = AnalyticsRepository(
        analytics_db,
        timeout_seconds=0.001,
        max_rows=10,
    )

    with pytest.raises(QueryTimeoutError) as error:
        repository.execute_query(
            """
            WITH RECURSIVE seq(value) AS (
                SELECT 1
                UNION ALL
                SELECT value + 1 FROM seq WHERE value < 100000000
            )
            SELECT SUM(value) FROM seq
            """
        )

    assert error.value.code == "query_timeout"


def test_database_file_remains_unchanged_after_rejected_write(analytics_db):
    repository = AnalyticsRepository(analytics_db)

    with pytest.raises(QueryPolicyError):
        repository.execute_query("DELETE FROM monthly_sales")

    with sqlite3.connect(analytics_db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM monthly_sales").fetchone()[0] == 18


def test_sqlite_connection_stays_read_only_if_policy_layer_is_bypassed(
    analytics_db, monkeypatch
):
    repository = AnalyticsRepository(analytics_db)
    monkeypatch.setattr(
        "app.database.analytics_repository.validate_query",
        lambda _sql, *, max_rows: ValidatedQuery(
            "DELETE FROM monthly_sales", returns_at_most=None
        ),
    )

    with pytest.raises(AnalyticsQueryError) as error:
        repository.execute_query("SELECT 1")

    assert getattr(error.value, "code", None) == "read_only_enforcement"
    with sqlite3.connect(analytics_db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM monthly_sales").fetchone()[0] == 18


def test_sqlite_authorizer_blocks_file_access_functions(analytics_db):
    repository = AnalyticsRepository(analytics_db)

    with pytest.raises(QueryPolicyError) as error:
        repository.execute_query("SELECT readfile('backend/.env')")

    assert error.value.code == "function_not_allowed"
