"""Testes do bulk update de posições VALUE_ONLY."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType, TransactionType
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.holding_repository import HoldingRepository
from consultor_investimentos.services.portfolio_service import PortfolioService


def _make_value_only(session: Session, ticker: str, initial: Decimal) -> object:
    repo = AssetRepository(session)
    asset = repo.create(
        ticker=ticker,
        name=f"Fundo {ticker}",
        asset_class=AssetClass.FIXED_INCOME,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=initial,
    )
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2024, 1, 2),
        price=initial,
    )
    return asset


def _make_quantity_price(session: Session, ticker: str) -> object:
    repo = AssetRepository(session)
    return repo.create(
        ticker=ticker,
        name=f"Ação {ticker}",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )


def test_get_value_only_assets_exclui_quantity_price(session: Session) -> None:
    _make_value_only(session, "CDB-XP", Decimal("10000"))
    _make_quantity_price(session, "VALE3")

    assets = PortfolioService(session).get_value_only_assets_for_update()

    tickers = [a["ticker"] for a in assets]
    assert "CDB-XP" in tickers
    assert "VALE3" not in tickers


def test_get_value_only_retorna_ultimo_preco(session: Session) -> None:
    asset = _make_value_only(session, "CDB-XP", Decimal("10000"))
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2024, 6, 1),
        price=Decimal("10500"),
    )

    assets = PortfolioService(session).get_value_only_assets_for_update()
    found = next(a for a in assets if a["ticker"] == "CDB-XP")

    assert found["last_price"] == Decimal("10500")
    assert found["last_date"] == date(2024, 6, 1)


def test_bulk_update_persiste_valores(session: Session) -> None:
    a1 = _make_value_only(session, "CDB-XP", Decimal("10000"))
    a2 = _make_value_only(session, "FIRF-XP", Decimal("5000"))

    ref_date = date(2024, 7, 1)
    svc = PortfolioService(session)
    count = svc.bulk_update_prices([
        (a1.id, ref_date, Decimal("10800")),
        (a2.id, ref_date, Decimal("5200")),
    ])

    assert count == 2

    repo = HoldingRepository(session)
    p1 = repo.get_on_date(a1.id, ref_date)
    p2 = repo.get_on_date(a2.id, ref_date)
    assert p1 is not None and p1.price == Decimal("10800")
    assert p2 is not None and p2.price == Decimal("5200")


def test_bulk_update_nao_duplica_registro_por_dia(session: Session) -> None:
    asset = _make_value_only(session, "CDB-XP", Decimal("10000"))
    ref_date = date(2024, 7, 1)
    svc = PortfolioService(session)

    svc.bulk_update_prices([(asset.id, ref_date, Decimal("10800"))])
    svc.bulk_update_prices([(asset.id, ref_date, Decimal("10900"))])

    repo = HoldingRepository(session)
    history = repo.get_history(asset.id)
    prices_on_date = [p for p in history if p.price_date == ref_date]
    assert len(prices_on_date) == 1
    assert prices_on_date[0].price == Decimal("10900")


def test_bulk_update_atualiza_valor_existente(session: Session) -> None:
    asset = _make_value_only(session, "CDB-XP", Decimal("10000"))
    ref_date = date(2024, 7, 1)
    svc = PortfolioService(session)

    svc.bulk_update_prices([(asset.id, ref_date, Decimal("10800"))])
    svc.bulk_update_prices([(asset.id, ref_date, Decimal("11000"))])

    latest = HoldingRepository(session).get_latest(asset.id)
    assert latest is not None
    assert latest.price == Decimal("11000")


def test_bulk_update_batch_vazio_retorna_zero(session: Session) -> None:
    svc = PortfolioService(session)
    count = svc.bulk_update_prices([])
    assert count == 0
