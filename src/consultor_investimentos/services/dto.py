from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from consultor_investimentos.config import AssetClass, ProjectionScenario, TransactionType


@dataclass
class SettingsDTO:
    user_name: str
    monthly_contribution: Decimal
    monthly_expenses: Decimal
    risk_profile: str
    target_equity_pct: Decimal
    target_fixed_pct: Decimal
    target_fii_pct: Decimal
    target_intl_pct: Decimal
    target_crypto_pct: Decimal
    target_other_pct: Decimal


@dataclass
class TransactionDTO:
    id: int
    asset_id: int
    asset_ticker: str
    transaction_type: str
    date: date
    quantity: Decimal | None
    unit_price: Decimal | None
    total_amount: Decimal
    fees: Decimal
    notes: str | None
    can_delete: bool


@dataclass
class Position:
    asset_id: int
    ticker: str
    name: str
    asset_class: AssetClass
    tracking_type: str
    quantity: Decimal | None
    average_price: Decimal | None
    current_price: Decimal
    current_value: Decimal
    total_cost: Decimal
    absolute_return: Decimal
    pct_return: Decimal
    portfolio_pct: Decimal
    price_date: date | None
    notes: str | None = None


@dataclass
class AllocationData:
    asset_class: AssetClass
    total_value: Decimal
    percentage: Decimal


@dataclass
class PortfolioSummary:
    total_value: Decimal
    total_cost: Decimal
    absolute_return: Decimal
    pct_return: Decimal
    positions: list[Position]
    allocation: list[AllocationData]
    unpriced_tickers: list[str]
    has_incomplete_prices: bool = field(init=False)

    def __post_init__(self) -> None:
        self.has_incomplete_prices = len(self.unpriced_tickers) > 0


@dataclass
class SnapshotPoint:
    snapshot_date: date
    total_value: Decimal
    snapshot_type: str


@dataclass
class ProjectionPoint:
    month: int
    value: Decimal


@dataclass
class ProjectionResult:
    scenario: ProjectionScenario
    annual_rate: Decimal
    monthly_rate: Decimal
    months_to_goal: int | None
    target_value: Decimal | None
    is_achievable: bool
    points: list[ProjectionPoint] = field(default_factory=list)


@dataclass
class FireMetrics:
    monthly_expenses: Decimal
    fire_number: Decimal
    current_value: Decimal
    pct_of_fire: Decimal
    is_achieved: bool
    months_to_fire: dict[ProjectionScenario, int | None] = field(default_factory=dict)
    fire_projections: dict[ProjectionScenario, "ProjectionResult"] = field(default_factory=dict)


@dataclass
class ImportTransaction:
    ticker: str
    transaction_type: TransactionType
    tx_date: date
    total_amount: Decimal
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    fees: Decimal = Decimal("0")
    notes: str | None = None
    new_position_value: Decimal | None = None
    row_number: int = 0


@dataclass
class ImportRowResult:
    row_number: int
    ticker: str
    transaction_type: str
    tx_date: date | None
    total_amount: Decimal | None
    status: Literal["ok", "error", "warning"]
    message: str | None = None


@dataclass
class ImportResult:
    total_rows: int
    valid_rows: int
    error_rows: int
    rows: list[ImportRowResult]
    is_duplicate: bool = False


@dataclass
class GoalProgress:
    goal_id: int
    goal_name: str
    goal_target_value: Decimal
    goal_target_date: date | None
    current_value: Decimal
    remaining_value: Decimal
    pct_complete: Decimal
    is_achieved: bool
    on_track: bool
    projections: dict[ProjectionScenario, ProjectionResult] = field(default_factory=dict)
