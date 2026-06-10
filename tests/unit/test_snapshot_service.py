"""Testes de integração do SnapshotService."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType, SnapshotType, TransactionType
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.holding_repository import HoldingRepository
from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository
from consultor_investimentos.services.snapshot_service import SnapshotService


@pytest.fixture
def portfolio_completo(session: Session):
    """Dois ativos com preço: VALE3 (QP) e CDB (VO)."""
    ar = AssetRepository(session)
    cr = ContributionRepository(session)
    hr = HoldingRepository(session)

    vale = ar.create(
        ticker="VALE3S",
        name="Vale S.A.",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    cr.create(
        asset_id=vale.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("6200.00"),
        quantity=Decimal("100"),
        unit_price=Decimal("62.00"),
    )
    hr.upsert(vale.id, date(2024, 6, 1), Decimal("70.00"))

    cdb = ar.create(
        ticker="CDB-SNAP",
        name="CDB Snapshot",
        asset_class=AssetClass.FIXED_INCOME,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )
    cr.create(
        asset_id=cdb.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("50000.00"),
    )
    hr.upsert(cdb.id, date(2024, 6, 1), Decimal("52000.00"))

    return {"vale": vale, "cdb": cdb}


def test_try_auto_snapshot_cria_se_nao_existir(session: Session, portfolio_completo) -> None:
    svc = SnapshotService(session)
    today = date.today()

    with patch("consultor_investimentos.services.snapshot_service.date") as mock_date:
        mock_date.today.return_value = today
        created = svc.try_auto_snapshot()

    assert created is True
    repo = SnapshotRepository(session)
    assert repo.exists_for_date(today)


def test_try_auto_snapshot_nao_duplica(session: Session, portfolio_completo) -> None:
    svc = SnapshotService(session)
    today = date.today()

    with patch("consultor_investimentos.services.snapshot_service.date") as mock_date:
        mock_date.today.return_value = today
        svc.try_auto_snapshot()
        created_second = svc.try_auto_snapshot()

    assert created_second is False


def test_create_manual_snapshot(session: Session, portfolio_completo) -> None:
    svc = SnapshotService(session)
    target = date(2024, 6, 1)
    svc.create_manual_snapshot(target)

    repo = SnapshotRepository(session)
    snapshot = repo.get_by_date(target)
    assert snapshot is not None
    assert snapshot.snapshot_type == SnapshotType.MANUAL.value


def test_snapshot_calcula_valor_correto_qp(session: Session, portfolio_completo) -> None:
    """VALE3: 100 cotas × R$70 = R$7.000. CDB: R$52.000. Total: R$59.000."""
    svc = SnapshotService(session)
    target = date(2024, 6, 15)
    svc.create_manual_snapshot(target)

    repo = SnapshotRepository(session)
    snapshot = repo.get_by_date(target)
    assert snapshot is not None
    assert snapshot.total_value == Decimal("59000.00")


def test_snapshot_detalhes_por_classe(session: Session, portfolio_completo) -> None:
    svc = SnapshotService(session)
    target = date(2024, 6, 20)
    svc.create_manual_snapshot(target)

    repo = SnapshotRepository(session)
    snapshot = repo.get_by_date(target)
    assert snapshot is not None
    classes = {d.asset_class for d in snapshot.details}
    assert AssetClass.EQUITY.value in classes
    assert AssetClass.FIXED_INCOME.value in classes


def test_snapshot_sem_ativos_nao_cria(session: Session) -> None:
    svc = SnapshotService(session)
    target = date(2025, 1, 1)
    svc.create_manual_snapshot(target)

    repo = SnapshotRepository(session)
    assert repo.get_by_date(target) is None


def test_get_history_retorna_pontos(session: Session, portfolio_completo) -> None:
    svc = SnapshotService(session)
    svc.create_manual_snapshot(date(2024, 1, 1))
    svc.create_manual_snapshot(date(2024, 6, 1))

    history = svc.get_history()
    assert len(history) >= 2
    dates = [h.snapshot_date for h in history]
    assert dates == sorted(dates)


def test_get_history_com_filtro(session: Session, portfolio_completo) -> None:
    svc = SnapshotService(session)
    svc.create_manual_snapshot(date(2024, 1, 1))
    svc.create_manual_snapshot(date(2024, 6, 1))
    svc.create_manual_snapshot(date(2025, 1, 1))

    history = svc.get_history(start=date(2024, 1, 1), end=date(2024, 12, 31))
    assert all(date(2024, 1, 1) <= h.snapshot_date <= date(2024, 12, 31) for h in history)


def test_ensure_snapshot_for_today_cria_se_nao_existir(session: Session, portfolio_completo) -> None:
    svc = SnapshotService(session)
    today = date.today()

    with patch("consultor_investimentos.services.snapshot_service.date") as mock_date:
        mock_date.today.return_value = today
        svc.ensure_snapshot_for_today()

    repo = SnapshotRepository(session)
    assert repo.exists_for_date(today)


def test_ensure_snapshot_for_today_sobrescreve_existente(session: Session, portfolio_completo) -> None:
    """ensure_snapshot_for_today deve upsert independente de já existir snapshot."""
    svc = SnapshotService(session)
    today = date.today()

    with patch("consultor_investimentos.services.snapshot_service.date") as mock_date:
        mock_date.today.return_value = today
        svc.try_auto_snapshot()

    repo = SnapshotRepository(session)
    snap_before = repo.get_by_date(today)
    assert snap_before is not None
    old_value = snap_before.total_value

    HoldingRepository(session).upsert(
        asset_id=portfolio_completo["vale"].id,
        price_date=today,
        price=Decimal("90.00"),
    )

    with patch("consultor_investimentos.services.snapshot_service.date") as mock_date:
        mock_date.today.return_value = today
        svc.ensure_snapshot_for_today()

    snap_after = repo.get_by_date(today)
    assert snap_after is not None
    assert snap_after.total_value != old_value, (
        "ensure_snapshot_for_today deve atualizar o valor com dados frescos"
    )


def test_ensure_snapshot_idempotente(session: Session, portfolio_completo) -> None:
    """Chamar ensure_snapshot_for_today múltiplas vezes não causa erro."""
    svc = SnapshotService(session)
    today = date.today()

    with patch("consultor_investimentos.services.snapshot_service.date") as mock_date:
        mock_date.today.return_value = today
        svc.ensure_snapshot_for_today()
        svc.ensure_snapshot_for_today()
        svc.ensure_snapshot_for_today()

    repo = SnapshotRepository(session)
    assert repo.exists_for_date(today)
