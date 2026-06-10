from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from consultor_investimentos.config import (
    AssetClass,
    AssetTrackingType,
    IncomeType,
    TransactionType,
)
from consultor_investimentos.database import models  # noqa: F401 — registra todos os modelos
from consultor_investimentos.database.connection import Base
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.goal_repository import GoalRepository


@pytest.fixture(scope="session")
def engine():
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(_engine, "connect")
    def set_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(_engine)
    yield _engine
    _engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as sess:
        yield sess
        sess.rollback()


# --- Fixtures de dados reutilizáveis ---


@pytest.fixture
def asset_qp(session: Session) -> models.Asset:
    """Ativo do tipo QUANTITY_PRICE (ação)."""
    repo = AssetRepository(session)
    return repo.create(
        ticker="VALE3",
        name="Vale S.A.",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )


@pytest.fixture
def asset_vo(session: Session) -> models.Asset:
    """Ativo do tipo VALUE_ONLY (CDB)."""
    repo = AssetRepository(session)
    return repo.create(
        ticker="CDB-XP-2027",
        name="CDB XP Investimentos 2027",
        asset_class=AssetClass.FIXED_INCOME,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )


@pytest.fixture
def asset_qp_with_initial(session: Session, asset_qp: models.Asset) -> models.Asset:
    """Ativo QUANTITY_PRICE com INITIAL_BALANCE já lançado."""
    repo = ContributionRepository(session)
    repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=__import__("datetime").date(2024, 1, 2),
        total_amount=Decimal("4960.00"),
        quantity=Decimal("80"),
        unit_price=Decimal("62.00"),
    )
    return asset_qp


@pytest.fixture
def asset_vo_with_initial(session: Session, asset_vo: models.Asset) -> models.Asset:
    """Ativo VALUE_ONLY com INITIAL_BALANCE já lançado."""
    repo = ContributionRepository(session)
    repo.create(
        asset_id=asset_vo.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=__import__("datetime").date(2024, 1, 2),
        total_amount=Decimal("45000.00"),
    )
    return asset_vo


@pytest.fixture
def goal(session: Session) -> models.Goal:
    """Meta financeira básica."""
    repo = GoalRepository(session)
    return repo.create(
        name="Meta 1 — R$ 500k",
        target_value=Decimal("500000.00"),
    )
