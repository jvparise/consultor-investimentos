"""Testes de integração: MarketDataService → banco de dados (providers mockados).

Usa engines SQLite isoladas com estado commitado, simulando produção.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Generator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from consultor_investimentos.config import (
    AssetClass,
    AssetTrackingType,
    Currency,
    IncomeType,
    TransactionType,
)
from consultor_investimentos.database import models  # noqa: F401 — registra tabelas
from consultor_investimentos.database.connection import Base
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.exchange_rate_repository import ExchangeRateRepository
from consultor_investimentos.repositories.holding_repository import HoldingRepository
from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository
from consultor_investimentos.services.market_data.market_data_service import MarketDataService
from consultor_investimentos.services.snapshot_service import SnapshotService

# ── Infra ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@contextmanager
def _db(engine) -> Generator[Session, None, None]:
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _make_qp_asset(
    engine,
    ticker: str = "PETR4",
    currency: Currency = Currency.BRL,
    asset_class: AssetClass = AssetClass.EQUITY,
    qty: str = "100",
    price: str = "50.00",
) -> int:
    """Cria ativo QUANTITY_PRICE com saldo inicial e preço no banco."""
    with _db(engine) as session:
        asset = AssetRepository(session).create(
            ticker=ticker,
            name=f"Ativo {ticker}",
            asset_class=asset_class,
            income_type=IncomeType.VARIABLE,
            tracking_type=AssetTrackingType.QUANTITY_PRICE,
            currency=currency,
        )
        ContributionRepository(session).create(
            asset_id=asset.id,
            transaction_type=TransactionType.INITIAL_BALANCE,
            date=date(2026, 1, 2),
            total_amount=Decimal(qty) * Decimal(price),
            quantity=Decimal(qty),
            unit_price=Decimal(price),
        )
        HoldingRepository(session).upsert(
            asset_id=asset.id,
            price_date=date(2026, 1, 2),
            price=Decimal(price),
        )
        return asset.id


def _make_vo_asset(engine, ticker: str = "CDB1") -> int:
    with _db(engine) as session:
        asset = AssetRepository(session).create(
            ticker=ticker,
            name=f"Ativo {ticker}",
            asset_class=AssetClass.FIXED_INCOME,
            income_type=IncomeType.FIXED,
            tracking_type=AssetTrackingType.VALUE_ONLY,
        )
        return asset.id


def _yahoo_returning(price: Decimal) -> MagicMock:
    m = MagicMock()
    m.get_price.return_value = price
    m.to_yahoo_ticker.side_effect = lambda t, ac, c: f"{t}.SA"
    return m


def _yahoo_failing() -> MagicMock:
    m = MagicMock()
    m.get_price.return_value = None
    m.to_yahoo_ticker.side_effect = lambda t, ac, c: f"{t}.SA"
    return m


def _bcb_returning(rate: Decimal) -> MagicMock:
    m = MagicMock()
    m.get_ptax.return_value = rate
    return m


def _bcb_failing() -> MagicMock:
    m = MagicMock()
    m.get_ptax.return_value = None
    return m


# ── Testes de update_asset_price ───────────────────────────────────────────────

def test_preco_salvo_no_banco(fresh_engine) -> None:
    asset_id = _make_qp_asset(fresh_engine, "PETR4")

    with _db(fresh_engine) as session:
        svc = MarketDataService(session, yahoo=_yahoo_returning(Decimal("38.50")))
        svc.update_asset_price(asset_id)

    with _db(fresh_engine) as session:
        latest = HoldingRepository(session).get_latest(asset_id)
        assert latest is not None
        assert latest.price == Decimal("38.50")


def test_source_yahoo_salvo_no_banco(fresh_engine) -> None:
    asset_id = _make_qp_asset(fresh_engine, "VALE3")

    with _db(fresh_engine) as session:
        MarketDataService(session, yahoo=_yahoo_returning(Decimal("75.00"))).update_asset_price(asset_id)

    with _db(fresh_engine) as session:
        latest = HoldingRepository(session).get_latest(asset_id)
        assert latest.source == "YAHOO"


def test_preco_nao_salvo_quando_yahoo_falha(fresh_engine) -> None:
    asset_id = _make_qp_asset(fresh_engine, "XPTO")
    # Apaga o preço inicial para garantir que nenhum preço foi salvo pelo Yahoo
    with _db(fresh_engine) as session:
        from consultor_investimentos.database.models import AssetPrice
        from sqlalchemy import delete
        session.execute(delete(AssetPrice).where(AssetPrice.asset_id == asset_id))

    with _db(fresh_engine) as session:
        MarketDataService(session, yahoo=_yahoo_failing()).update_asset_price(asset_id)

    with _db(fresh_engine) as session:
        latest = HoldingRepository(session).get_latest(asset_id)
    assert latest is None


def test_value_only_nao_atualizado(fresh_engine) -> None:
    asset_id = _make_vo_asset(fresh_engine, "CDB1")

    with _db(fresh_engine) as session:
        result = MarketDataService(session, yahoo=_yahoo_returning(Decimal("9999.00"))).update_asset_price(asset_id)

    assert result.status == "skipped"

    with _db(fresh_engine) as session:
        latest = HoldingRepository(session).get_latest(asset_id)
    assert latest is None


def test_upsert_sobreescreve_preco_do_dia(fresh_engine) -> None:
    """Duas chamadas no mesmo dia sobrescrevem o preço (idempotente por data)."""
    asset_id = _make_qp_asset(fresh_engine, "BBAS3")

    with _db(fresh_engine) as session:
        MarketDataService(session, yahoo=_yahoo_returning(Decimal("30.00"))).update_asset_price(asset_id)

    with _db(fresh_engine) as session:
        MarketDataService(session, yahoo=_yahoo_returning(Decimal("31.50"))).update_asset_price(asset_id)

    today = date.today()
    with _db(fresh_engine) as session:
        from consultor_investimentos.database.models import AssetPrice
        from sqlalchemy import select
        prices_today = list(
            session.execute(
                select(AssetPrice).where(
                    AssetPrice.asset_id == asset_id,
                    AssetPrice.price_date == today,
                )
            ).scalars()
        )
        assert len(prices_today) == 1
        assert prices_today[0].price == Decimal("31.50")


# ── Testes de update_exchange_rates ───────────────────────────────────────────

def test_cambio_salvo_no_banco(fresh_engine) -> None:
    with _db(fresh_engine) as session:
        results = MarketDataService(session, yahoo=MagicMock(), bcb=_bcb_returning(Decimal("5.71"))).update_exchange_rates()

    assert all(r.status == "updated" for r in results)

    with _db(fresh_engine) as session:
        usd = ExchangeRateRepository(session).get(Currency.USD)
        eur = ExchangeRateRepository(session).get(Currency.EUR)
        assert usd.rate == Decimal("5.71")
        assert eur.rate == Decimal("5.71")


def test_cambio_nao_atualizado_quando_bcb_falha(fresh_engine) -> None:
    with _db(fresh_engine) as session:
        ExchangeRateRepository(session).upsert(Currency.USD, Decimal("5.50"))

    with _db(fresh_engine) as session:
        results = MarketDataService(session, yahoo=MagicMock(), bcb=_bcb_failing()).update_exchange_rates()

    assert all(r.status == "error" for r in results)

    with _db(fresh_engine) as session:
        usd = ExchangeRateRepository(session).get(Currency.USD)
        assert usd.rate == Decimal("5.50")  # não alterado


# ── Testes de update_all_prices ────────────────────────────────────────────────

def test_resumo_contabiliza_corretamente(fresh_engine) -> None:
    _make_qp_asset(fresh_engine, "PETR4")
    _make_qp_asset(fresh_engine, "VALE3")
    _make_vo_asset(fresh_engine, "CDB1")

    yahoo = MagicMock()
    yahoo.to_yahoo_ticker.side_effect = lambda t, ac, c: f"{t}.SA"
    yahoo.get_price.side_effect = lambda t: Decimal("50.00") if "PETR4" in t else None

    with _db(fresh_engine) as session:
        summary = MarketDataService(session, yahoo=yahoo, bcb=MagicMock()).update_all_prices()

    assert summary.updated == 1   # PETR4
    assert summary.errors == 1    # VALE3
    assert summary.skipped == 1   # CDB1


def test_snapshot_criado_apos_update_all(fresh_engine) -> None:
    """Após update_all + ensure_snapshot, snapshot deve existir e ter valor > 0."""
    _make_qp_asset(fresh_engine, "WEGE3")

    with _db(fresh_engine) as session:
        svc = MarketDataService(session, yahoo=_yahoo_returning(Decimal("42.00")))
        svc.update_all_prices()
        SnapshotService(session).ensure_snapshot_for_today()

    with _db(fresh_engine) as session:
        snap = SnapshotRepository(session).get_latest()
        assert snap is not None
        assert snap.total_value > Decimal("0")


# ── get_price_status ───────────────────────────────────────────────────────────

def test_get_price_status_todos_os_ativos(fresh_engine) -> None:
    _make_qp_asset(fresh_engine, "PETR4")
    _make_vo_asset(fresh_engine, "CDB1")

    yahoo = MagicMock()
    yahoo.to_yahoo_ticker.side_effect = lambda t, ac, c: f"{t}.SA"

    with _db(fresh_engine) as session:
        status = MarketDataService(session, yahoo=yahoo).get_price_status()

    tickers = {s["ticker"] for s in status}
    assert "PETR4" in tickers
    assert "CDB1" in tickers


def test_get_price_status_mostra_fonte(fresh_engine) -> None:
    asset_id = _make_qp_asset(fresh_engine, "ELET3")

    with _db(fresh_engine) as session:
        MarketDataService(session, yahoo=_yahoo_returning(Decimal("20.00"))).update_asset_price(asset_id)

    yahoo = MagicMock()
    yahoo.to_yahoo_ticker.return_value = "ELET3.SA"

    with _db(fresh_engine) as session:
        status = MarketDataService(session, yahoo=yahoo).get_price_status()

    item = next(s for s in status if s["ticker"] == "ELET3")
    assert item["source"] == "YAHOO"
