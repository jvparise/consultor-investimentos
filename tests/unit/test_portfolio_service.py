"""Testes do PortfolioService — cálculos de PVPM e posição."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType, TransactionType
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.holding_repository import HoldingRepository
from consultor_investimentos.services.portfolio_service import PortfolioService


@pytest.fixture
def vale3(session: Session):
    asset = AssetRepository(session).create(
        ticker="VALE3",
        name="Vale S.A.",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("6200.00"),
        quantity=Decimal("100"),
        unit_price=Decimal("62.00"),
    )
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2024, 6, 1),
        price=Decimal("70.00"),
    )
    return asset


@pytest.fixture
def cdb(session: Session):
    asset = AssetRepository(session).create(
        ticker="CDB-XP-2027",
        name="CDB XP 2027",
        asset_class=AssetClass.FIXED_INCOME,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("50000.00"),
    )
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2024, 6, 1),
        price=Decimal("52000.00"),
    )
    return asset


def test_position_quantity_price(session: Session, vale3) -> None:
    svc = PortfolioService(session)
    position = svc.get_position(vale3.id)

    assert position is not None
    assert position.ticker == "VALE3"
    assert position.quantity == Decimal("100.000000")
    assert position.current_price == Decimal("70.00")
    assert position.current_value == Decimal("7000.00")
    assert position.total_cost == Decimal("6200.00")
    assert position.absolute_return == Decimal("800.00")


def test_position_pct_return_quantity_price(session: Session, vale3) -> None:
    svc = PortfolioService(session)
    position = svc.get_position(vale3.id)

    # (7000 - 6200) / 6200 * 100 = 12.90%
    assert position is not None
    assert position.pct_return == Decimal("12.90")


def test_position_value_only(session: Session, cdb) -> None:
    svc = PortfolioService(session)
    position = svc.get_position(cdb.id)

    assert position is not None
    assert position.quantity is None
    assert position.average_price is None
    assert position.current_value == Decimal("52000.00")
    assert position.total_cost == Decimal("50000.00")
    assert position.absolute_return == Decimal("2000.00")


def test_position_retorna_none_sem_preco(session: Session) -> None:
    asset = AssetRepository(session).create(
        ticker="PETR4",
        name="Petrobras",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("3000.00"),
        quantity=Decimal("100"),
        unit_price=Decimal("30.00"),
    )
    svc = PortfolioService(session)
    assert svc.get_position(asset.id) is None


def test_pvpm_com_compras_multiplas(session: Session) -> None:
    """BUY 100 @ 62, BUY 50 @ 70 → PVPM = (6200 + 3500) / 150 = 64.67."""
    asset = AssetRepository(session).create(
        ticker="BBAS3",
        name="Banco do Brasil",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    contrib = ContributionRepository(session)
    contrib.create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("6200.00"),
        quantity=Decimal("100"),
        unit_price=Decimal("62.00"),
    )
    contrib.create(
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        date=date(2024, 3, 1),
        total_amount=Decimal("3500.00"),
        quantity=Decimal("50"),
        unit_price=Decimal("70.00"),
    )
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2024, 6, 1),
        price=Decimal("75.00"),
    )

    svc = PortfolioService(session)
    position = svc.get_position(asset.id)

    assert position is not None
    assert position.quantity == Decimal("150.000000")
    assert position.average_price == pytest.approx(Decimal("64.666667"), abs=Decimal("0.000001"))
    assert position.current_value == Decimal("11250.00")


def test_pvpm_sell_reduz_quantidade_nao_muda_preco_medio(session: Session) -> None:
    """Após SELL de 30 cotas, quantidade cai para 70 mas PVPM permanece 62."""
    asset = AssetRepository(session).create(
        ticker="ITUB4",
        name="Itaú Unibanco",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    contrib = ContributionRepository(session)
    contrib.create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("6200.00"),
        quantity=Decimal("100"),
        unit_price=Decimal("62.00"),
    )
    contrib.create(
        asset_id=asset.id,
        transaction_type=TransactionType.SELL,
        date=date(2024, 4, 1),
        total_amount=Decimal("2100.00"),
        quantity=Decimal("30"),
        unit_price=Decimal("70.00"),
    )
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2024, 6, 1),
        price=Decimal("70.00"),
    )

    svc = PortfolioService(session)
    position = svc.get_position(asset.id)

    assert position is not None
    assert position.quantity == Decimal("70.000000")
    assert position.average_price == Decimal("62.000000")


def test_get_portfolio_summary_dois_ativos(session: Session, vale3, cdb) -> None:
    svc = PortfolioService(session)
    summary = svc.get_portfolio_summary()

    # VALE3: 100 × 70 = 7000; CDB: 52000
    assert summary.total_value == Decimal("59000.00")
    assert summary.total_cost == Decimal("56200.00")
    assert summary.absolute_return == Decimal("2800.00")
    assert len(summary.positions) == 2


def test_get_portfolio_summary_portfolio_pct(session: Session, vale3, cdb) -> None:
    svc = PortfolioService(session)
    summary = svc.get_portfolio_summary()

    total = summary.total_value
    for p in summary.positions:
        assert p.portfolio_pct > Decimal("0")
    pcts = sum(p.portfolio_pct for p in summary.positions)
    assert abs(pcts - Decimal("100")) <= Decimal("0.02")


def test_get_allocation_by_class(session: Session, vale3, cdb) -> None:
    svc = PortfolioService(session)
    summary = svc.get_portfolio_summary()

    classes = {a.asset_class for a in summary.allocation}
    assert AssetClass.EQUITY in classes
    assert AssetClass.FIXED_INCOME in classes


def test_get_all_positions_ativo_sem_preco_nao_aparece(session: Session) -> None:
    asset = AssetRepository(session).create(
        ticker="XPTO3",
        name="Ativo sem preço",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("1000.00"),
        quantity=Decimal("10"),
        unit_price=Decimal("100.00"),
    )

    svc = PortfolioService(session)
    positions = svc.get_all_positions()
    tickers = [p.ticker for p in positions]
    assert "XPTO3" not in tickers


def test_unpriced_tickers_vazio_quando_todos_tem_preco(session: Session, vale3, cdb) -> None:
    svc = PortfolioService(session)
    summary = svc.get_portfolio_summary()

    assert summary.unpriced_tickers == []
    assert summary.has_incomplete_prices is False


def test_unpriced_tickers_um_ativo_sem_preco(session: Session, vale3) -> None:
    unpriced = AssetRepository(session).create(
        ticker="SEMPRECO",
        name="Sem preço",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    ContributionRepository(session).create(
        asset_id=unpriced.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("500.00"),
        quantity=Decimal("5"),
        unit_price=Decimal("100.00"),
    )

    svc = PortfolioService(session)
    summary = svc.get_portfolio_summary()

    assert "SEMPRECO" in summary.unpriced_tickers
    assert summary.has_incomplete_prices is True
    assert len(summary.positions) == 1


def test_unpriced_tickers_multiplos_sem_preco(session: Session) -> None:
    repo = AssetRepository(session)
    contrib = ContributionRepository(session)

    for ticker in ("AAA3", "BBB3"):
        asset = repo.create(
            ticker=ticker,
            name=ticker,
            asset_class=AssetClass.EQUITY,
            income_type=IncomeType.VARIABLE,
            tracking_type=AssetTrackingType.QUANTITY_PRICE,
        )
        contrib.create(
            asset_id=asset.id,
            transaction_type=TransactionType.INITIAL_BALANCE,
            date=date(2024, 1, 2),
            total_amount=Decimal("1000.00"),
            quantity=Decimal("10"),
            unit_price=Decimal("100.00"),
        )

    svc = PortfolioService(session)
    summary = svc.get_portfolio_summary()

    assert set(summary.unpriced_tickers) == {"AAA3", "BBB3"}
    assert summary.has_incomplete_prices is True
    assert summary.positions == []


def test_has_incomplete_prices_deriva_de_unpriced_tickers(session: Session) -> None:
    from consultor_investimentos.services.dto import PortfolioSummary, AllocationData

    summary_com = PortfolioSummary(
        total_value=Decimal("0"),
        total_cost=Decimal("0"),
        absolute_return=Decimal("0"),
        pct_return=Decimal("0"),
        positions=[],
        allocation=[],
        unpriced_tickers=["TICKER1"],
    )
    assert summary_com.has_incomplete_prices is True

    summary_sem = PortfolioSummary(
        total_value=Decimal("0"),
        total_cost=Decimal("0"),
        absolute_return=Decimal("0"),
        pct_return=Decimal("0"),
        positions=[],
        allocation=[],
        unpriced_tickers=[],
    )
    assert summary_sem.has_incomplete_prices is False


def test_update_asset_price_atualiza_holding(session: Session, vale3) -> None:
    svc = PortfolioService(session)
    svc.update_asset_price(vale3.id, date(2024, 9, 1), Decimal("85.00"))

    latest = HoldingRepository(session).get_latest(vale3.id)
    assert latest is not None
    assert latest.price == Decimal("85.00")
    assert latest.price_date == date(2024, 9, 1)
