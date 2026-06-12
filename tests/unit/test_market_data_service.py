"""Testes unitários para MarketDataService — providers mockados."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from consultor_investimentos.config import (
    AssetClass,
    AssetTrackingType,
    Currency,
    IncomeType,
)
from consultor_investimentos.database import models  # noqa: F401 — registra tabelas
from consultor_investimentos.database.connection import Base
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.exchange_rate_repository import ExchangeRateRepository
from consultor_investimentos.repositories.holding_repository import HoldingRepository
from consultor_investimentos.services.market_data.market_data_service import (
    MarketDataService,
)


@pytest.fixture
def engine():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture
def session(engine):
    s = Session(engine)
    yield s
    s.rollback()
    s.close()


def _make_asset(
    session,
    ticker: str = "PETR4",
    tracking: AssetTrackingType = AssetTrackingType.QUANTITY_PRICE,
    currency: Currency = Currency.BRL,
    asset_class: AssetClass = AssetClass.EQUITY,
) -> object:
    asset = AssetRepository(session).create(
        ticker=ticker,
        name=f"Ativo {ticker}",
        asset_class=asset_class,
        income_type=IncomeType.VARIABLE,
        tracking_type=tracking,
        currency=currency,
    )
    session.flush()
    return asset


def _mock_yahoo(price: Decimal | None = None, yahoo_ticker: str = "PETR4.SA") -> MagicMock:
    m = MagicMock()
    m.get_price.return_value = price
    m.to_yahoo_ticker.return_value = yahoo_ticker
    return m


def _mock_bcb(rate: Decimal | None = None) -> MagicMock:
    m = MagicMock()
    m.get_ptax.return_value = rate
    return m


# ── update_asset_price ─────────────────────────────────────────────────────────

def test_update_asset_price_ok(session):
    asset = _make_asset(session, "PETR4")
    yahoo = _mock_yahoo(Decimal("38.50"), "PETR4.SA")
    svc = MarketDataService(session, yahoo=yahoo, bcb=MagicMock())

    result = svc.update_asset_price(asset.id)

    assert result.status == "updated"
    assert result.new_price == Decimal("38.50")
    assert result.ticker == "PETR4"
    assert result.yahoo_ticker == "PETR4.SA"
    assert result.error_message is None


def test_update_asset_price_salva_no_banco(session):
    asset = _make_asset(session, "VALE3")
    yahoo = _mock_yahoo(Decimal("75.00"), "VALE3.SA")
    MarketDataService(session, yahoo=yahoo).update_asset_price(asset.id)

    latest = HoldingRepository(session).get_latest(asset.id)
    assert latest is not None
    assert latest.price == Decimal("75.00")
    assert latest.source == "YAHOO"


def test_update_asset_price_value_only_skipped(session):
    asset = _make_asset(session, "CDB1", tracking=AssetTrackingType.VALUE_ONLY)
    svc = MarketDataService(session, yahoo=_mock_yahoo(), bcb=MagicMock())

    result = svc.update_asset_price(asset.id)

    assert result.status == "skipped"
    assert result.new_price is None


def test_update_asset_price_not_found(session):
    svc = MarketDataService(session, yahoo=_mock_yahoo(), bcb=MagicMock())
    result = svc.update_asset_price(9999)

    assert result.status == "error"
    assert "não encontrado" in result.error_message


def test_update_asset_price_yahoo_returns_none(session):
    asset = _make_asset(session, "UNKN")
    yahoo = _mock_yahoo(None, "UNKN.SA")
    svc = MarketDataService(session, yahoo=yahoo, bcb=MagicMock())

    result = svc.update_asset_price(asset.id)

    assert result.status == "error"
    assert result.new_price is None
    assert "UNKN.SA" in result.error_message


def test_update_asset_price_nao_salva_quando_yahoo_falha(session):
    asset = _make_asset(session, "XPTO")
    yahoo = _mock_yahoo(None, "XPTO.SA")
    MarketDataService(session, yahoo=yahoo).update_asset_price(asset.id)

    latest = HoldingRepository(session).get_latest(asset.id)
    assert latest is None


def test_update_asset_price_retorna_preco_anterior(session):
    from datetime import date
    asset = _make_asset(session, "ITUB4")
    HoldingRepository(session).upsert(asset.id, date(2026, 6, 10), Decimal("30.00"))

    yahoo = _mock_yahoo(Decimal("32.00"), "ITUB4.SA")
    svc = MarketDataService(session, yahoo=yahoo)

    result = svc.update_asset_price(asset.id)

    assert result.previous_price == Decimal("30.00")
    assert result.new_price == Decimal("32.00")


# ── update_all_prices ──────────────────────────────────────────────────────────

def test_update_all_prices_summary(session):
    _make_asset(session, "PETR4", AssetTrackingType.QUANTITY_PRICE)
    _make_asset(session, "VALE3", AssetTrackingType.QUANTITY_PRICE)
    _make_asset(session, "CDB1", AssetTrackingType.VALUE_ONLY)

    yahoo = MagicMock()
    yahoo.to_yahoo_ticker.side_effect = lambda t, ac, c: f"{t}.SA"
    yahoo.get_price.side_effect = lambda t: (
        Decimal("38.50") if "PETR4" in t else None
    )

    svc = MarketDataService(session, yahoo=yahoo, bcb=MagicMock())
    summary = svc.update_all_prices()

    assert summary.updated == 1   # PETR4
    assert summary.errors == 1    # VALE3 (yahoo returns None)
    assert summary.skipped == 1   # CDB1 (VALUE_ONLY)
    assert len(summary.results) == 3


# ── update_exchange_rates ──────────────────────────────────────────────────────

def test_update_exchange_rates_ok(session):
    bcb = _mock_bcb(Decimal("5.71"))
    svc = MarketDataService(session, yahoo=MagicMock(), bcb=bcb)

    results = svc.update_exchange_rates()

    assert all(r.status == "updated" for r in results)
    usd = ExchangeRateRepository(session).get(Currency.USD)
    eur = ExchangeRateRepository(session).get(Currency.EUR)
    assert usd is not None
    assert eur is not None


def test_update_exchange_rates_bcb_fails(session):
    bcb = _mock_bcb(None)
    svc = MarketDataService(session, yahoo=MagicMock(), bcb=bcb)

    results = svc.update_exchange_rates()

    assert all(r.status == "error" for r in results)
    assert all(r.error_message is not None for r in results)


def test_update_exchange_rates_atualiza_valor(session):
    ExchangeRateRepository(session).upsert(Currency.USD, Decimal("5.50"))
    bcb = _mock_bcb(Decimal("5.75"))
    svc = MarketDataService(session, yahoo=MagicMock(), bcb=bcb)

    results = svc.update_exchange_rates()

    usd_result = next(r for r in results if r.currency == "USD")
    assert usd_result.previous_rate == Decimal("5.50")
    assert usd_result.new_rate == Decimal("5.75")


# ── get_price_status ───────────────────────────────────────────────────────────

def test_get_price_status_inclui_todos_ativos(session):
    _make_asset(session, "PETR4", AssetTrackingType.QUANTITY_PRICE)
    _make_asset(session, "CDB1", AssetTrackingType.VALUE_ONLY)

    yahoo = MagicMock()
    yahoo.to_yahoo_ticker.return_value = "PETR4.SA"
    svc = MarketDataService(session, yahoo=yahoo, bcb=MagicMock())

    status = svc.get_price_status()

    tickers = {s["ticker"] for s in status}
    assert "PETR4" in tickers
    assert "CDB1" in tickers


def test_get_price_status_value_only_sem_yahoo_ticker(session):
    _make_asset(session, "LCI1", AssetTrackingType.VALUE_ONLY)

    svc = MarketDataService(session, yahoo=MagicMock(), bcb=MagicMock())
    status = svc.get_price_status()

    lci = next(s for s in status if s["ticker"] == "LCI1")
    assert lci["yahoo_ticker"] is None


def test_get_price_status_sem_preco_retorna_none(session):
    _make_asset(session, "NOVO3")

    yahoo = MagicMock()
    yahoo.to_yahoo_ticker.return_value = "NOVO3.SA"
    svc = MarketDataService(session, yahoo=yahoo)
    status = svc.get_price_status()

    item = next(s for s in status if s["ticker"] == "NOVO3")
    assert item["last_price"] is None
    assert item["last_date"] is None
