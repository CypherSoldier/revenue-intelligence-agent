import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from app.config import get_settings


SEED_ROWS = (
    ("2025-01-01", "North", 130_000),
    ("2025-01-01", "South", 150_000),
    ("2025-01-01", "West", 110_000),
    ("2025-02-01", "North", 130_000),
    ("2025-02-01", "South", 150_000),
    ("2025-02-01", "West", 120_000),
    ("2025-03-01", "North", 140_000),
    ("2025-03-01", "South", 150_000),
    ("2025-03-01", "West", 120_000),
    ("2025-04-01", "North", 120_000),
    ("2025-04-01", "South", 130_000),
    ("2025-04-01", "West", 80_000),
    ("2025-05-01", "North", 120_000),
    ("2025-05-01", "South", 135_000),
    ("2025-05-01", "West", 80_000),
    ("2025-06-01", "North", 120_000),
    ("2025-06-01", "South", 135_000),
    ("2025-06-01", "West", 80_000),
)


def seed_analytics_database(database_path: Path | None = None) -> Path:
    path = database_path or get_settings().analytics_db_path
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS monthly_sales (
                    month_start TEXT NOT NULL
                        CHECK (
                            length(month_start) = 10
                            AND substr(month_start, 9, 2) = '01'
                        ),
                    region TEXT NOT NULL CHECK (region IN ('North', 'South', 'West')),
                    net_revenue_usd INTEGER NOT NULL CHECK (net_revenue_usd >= 0),
                    PRIMARY KEY (month_start, region)
                )
                """
            )
            connection.execute("DELETE FROM monthly_sales")
            connection.executemany(
                """
                INSERT INTO monthly_sales (month_start, region, net_revenue_usd)
                VALUES (?, ?, ?)
                """,
                SEED_ROWS,
            )

    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or reset the synthetic monthly revenue analytics database."
    )
    parser.add_argument(
        "--database",
        type=Path,
        help="Optional SQLite file path; defaults to ANALYTICS_DB_PATH.",
    )
    args = parser.parse_args()
    path = seed_analytics_database(args.database)
    print(f"Seeded {len(SEED_ROWS)} monthly_sales rows in {path}")


if __name__ == "__main__":
    main()
