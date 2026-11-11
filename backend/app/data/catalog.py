from app.schemas.catalog import (
    ColumnDefinition,
    DataCatalog,
    MetricDefinition,
    TableDefinition,
)


CATALOG = DataCatalog(
    dataset_name="Synthetic monthly revenue demo dataset",
    currency="USD",
    coverage_start="2025-01-01",
    coverage_end="2025-06-30",
    reporting_calendar="Calendar months and calendar quarters",
    tables=[
        TableDefinition(
            name="monthly_sales",
            description=(
                "Synthetic monthly net revenue by region. Contains aggregate "
                "values only and no customer, product, or causal-driver detail."
            ),
            grain="One row per month_start and region",
            columns=[
                ColumnDefinition(
                    name="month_start",
                    data_type="TEXT (ISO date)",
                    description="First day of the reporting month.",
                ),
                ColumnDefinition(
                    name="region",
                    data_type="TEXT",
                    description="One of North, South, or West.",
                ),
                ColumnDefinition(
                    name="net_revenue_usd",
                    data_type="INTEGER",
                    description=(
                        "Non-negative whole USD after discounts; excludes tax, "
                        "shipping, and refunds."
                    ),
                ),
            ],
        )
    ],
    metrics=[
        MetricDefinition(
            id="net_revenue_usd",
            name="Net revenue",
            expression="SUM(monthly_sales.net_revenue_usd)",
            unit="whole USD",
            description=(
                "Revenue after discounts, excluding tax, shipping, and refunds. "
                "The data supports descriptive comparisons only and cannot "
                "establish causal drivers."
            ),
            time_column="monthly_sales.month_start",
            supported_dimensions=["region"],
        )
    ],
)


def get_catalog() -> DataCatalog:
    return CATALOG
