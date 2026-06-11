"""Testes unitários para PerformanceReportService."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import (
    AssetClass,
    AssetTrackingType,
    Currency,
    IncomeType,
    TransactionType,
)
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.exchange_rate_repository import ExchangeRateRepository
from consultor_investimentos.repositories.holding_repository import HoldingRepository
from consultor_investimentos.services.performance_report_service import PerformanceReportService


# ── Helpers ────────────────────────────────────────────────────────────────────

def _asset_vo(session: Session, ticker: str, asset_class: AssetClass = AssetClass.FIXED_INCOME) -> object:
    return AssetRepository(session).create(
        ticker=ticker,
        name=f"Fundo {ticker}",
        asset_class=asset_class,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )


def _asset_qp(session: Session, ticker: str, asset_class: AssetClass = AssetClass.EQUITY) -> object:
    return AssetRepository(session).create(
        ticker=ticker,
        name=f"Ação {ticker}",
        asset_class=asset_class,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )


def _price(session: Session, asset_id: int, d: date, price: Decimal) -> None:
    HoldingRepository(session).upsert(asset_id=asset_id, price_date=d, price=price)


def _income(
    session: Session,
    asset_id: int,
    d: date,
    amount: Decimal,
    tx_type: TransactionType = TransactionType.DIVIDEND,
) -> None:
    ContributionRepository(session).create(
        asset_id=asset_id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 1),
        total_amount=Decimal("1000"),
    )
    ContributionRepository(session).create(
        asset_id=asset_id,
        transaction_type=tx_type,
        date=d,
        total_amount=amount,
    )


# ── Testes ─────────────────────────────────────────────────────────────────────

def test_preco_base_encontrado(session: Session) -> None:
    asset = _asset_vo(session, "CDB-A")
    _price(session, asset.id, date(2026, 4, 30), Decimal("10000"))
    _price(session, asset.id, date(2026, 5, 31), Decimal("10200"))

    report = PerformanceReportService(session).generate(2026, 5)

    row = next(r for c in report.classes for r in c.rows if r.ticker == "CDB-A")
    assert row.previous_price == Decimal("10000")
    assert row.previous_price_date == date(2026, 4, 30)


def test_preco_atual_encontrado(session: Session) -> None:
    asset = _asset_vo(session, "CDB-B")
    _price(session, asset.id, date(2026, 4, 30), Decimal("10000"))
    _price(session, asset.id, date(2026, 5, 31), Decimal("10300"))

    report = PerformanceReportService(session).generate(2026, 5)

    row = next(r for c in report.classes for r in c.rows if r.ticker == "CDB-B")
    assert row.current_price == Decimal("10300")


def test_ativo_sem_preco_base(session: Session) -> None:
    asset = _asset_vo(session, "CDB-C")
    _price(session, asset.id, date(2026, 5, 15), Decimal("5000"))

    report = PerformanceReportService(session).generate(2026, 5)

    row = next(r for c in report.classes for r in c.rows if r.ticker == "CDB-C")
    assert row.previous_price is None
    assert row.appreciation == Decimal("0")


def test_ativo_sem_preco_algum(session: Session) -> None:
    """Ativo sem nenhum preço registrado: ambos None, sem crash."""
    _asset_vo(session, "CDB-D")

    report = PerformanceReportService(session).generate(2026, 5)

    row = next(r for c in report.classes for r in c.rows if r.ticker == "CDB-D")
    assert row.previous_price is None
    assert row.current_price is None
    assert row.appreciation == Decimal("0")


def test_ativo_sem_rendimento(session: Session) -> None:
    asset = _asset_vo(session, "CDB-E")
    _price(session, asset.id, date(2026, 4, 30), Decimal("10000"))
    _price(session, asset.id, date(2026, 5, 31), Decimal("10100"))

    report = PerformanceReportService(session).generate(2026, 5)

    row = next(r for c in report.classes for r in c.rows if r.ticker == "CDB-E")
    assert row.income == Decimal("0")


def test_dividendos_somados(session: Session) -> None:
    asset = _asset_qp(session, "VALE3-DIV")
    # Saldo inicial obrigatório
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2026, 1, 1),
        total_amount=Decimal("5000"),
        quantity=Decimal("100"),
        unit_price=Decimal("50"),
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.DIVIDEND,
        date=date(2026, 5, 10),
        total_amount=Decimal("200"),
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.DIVIDEND,
        date=date(2026, 5, 20),
        total_amount=Decimal("150"),
    )

    report = PerformanceReportService(session).generate(2026, 5)

    row = next(r for c in report.classes for r in c.rows if r.ticker == "VALE3-DIV")
    assert row.income == Decimal("350")


def test_juros_somados(session: Session) -> None:
    asset = _asset_vo(session, "CDB-JUROS")
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2026, 1, 1),
        total_amount=Decimal("20000"),
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INTEREST,
        date=date(2026, 5, 15),
        total_amount=Decimal("300"),
    )

    report = PerformanceReportService(session).generate(2026, 5)

    row = next(r for c in report.classes for r in c.rows if r.ticker == "CDB-JUROS")
    assert row.income == Decimal("300")


def test_agrupamento_por_classe(session: Session) -> None:
    _asset_vo(session, "RF-01", AssetClass.FIXED_INCOME)
    _asset_vo(session, "RF-02", AssetClass.FIXED_INCOME)
    _asset_qp(session, "ACOES-01", AssetClass.EQUITY)

    report = PerformanceReportService(session).generate(2026, 5)

    class_names = [c.asset_class for c in report.classes]
    assert AssetClass.FIXED_INCOME in class_names
    assert AssetClass.EQUITY in class_names

    rf_cls = next(c for c in report.classes if c.asset_class == AssetClass.FIXED_INCOME)
    rf_tickers = [r.ticker for r in rf_cls.rows]
    assert "RF-01" in rf_tickers
    assert "RF-02" in rf_tickers


def test_subtotal_por_classe(session: Session) -> None:
    asset1 = _asset_vo(session, "RF-SUB1", AssetClass.FIXED_INCOME)
    asset2 = _asset_vo(session, "RF-SUB2", AssetClass.FIXED_INCOME)
    _price(session, asset1.id, date(2026, 4, 30), Decimal("10000"))
    _price(session, asset1.id, date(2026, 5, 31), Decimal("10200"))
    _price(session, asset2.id, date(2026, 4, 30), Decimal("5000"))
    _price(session, asset2.id, date(2026, 5, 31), Decimal("5100"))

    report = PerformanceReportService(session).generate(2026, 5)

    rf_cls = next(c for c in report.classes if c.asset_class == AssetClass.FIXED_INCOME
                  and any(r.ticker in ("RF-SUB1", "RF-SUB2") for r in c.rows))
    # Subtotal = 200 + 100 = 300
    assert rf_cls.total_appreciation == Decimal("300")


def test_total_geral(session: Session) -> None:
    a1 = _asset_vo(session, "TOT-1", AssetClass.FIXED_INCOME)
    a2 = _asset_vo(session, "TOT-2", AssetClass.CASH)
    _price(session, a1.id, date(2026, 4, 30), Decimal("10000"))
    _price(session, a1.id, date(2026, 5, 31), Decimal("10500"))
    _price(session, a2.id, date(2026, 4, 30), Decimal("2000"))
    _price(session, a2.id, date(2026, 5, 31), Decimal("2000"))

    report = PerformanceReportService(session).generate(2026, 5)

    # Total deve incluir a1 (500) + a2 (0) entre outros ativos da sessão
    # Verifica apenas a presença dos ativos e que total é consistente
    all_rows = [r for c in report.classes for r in c.rows]
    t1 = next(r for r in all_rows if r.ticker == "TOT-1")
    t2 = next(r for r in all_rows if r.ticker == "TOT-2")
    assert t1.appreciation == Decimal("500")
    assert t2.appreciation == Decimal("0")
    assert report.total_result == report.total_appreciation + report.total_income


def test_mes_sem_movimentacoes(session: Session) -> None:
    _asset_vo(session, "SEM-MOV")

    report = PerformanceReportService(session).generate(2026, 5)

    row = next((r for c in report.classes for r in c.rows if r.ticker == "SEM-MOV"), None)
    assert row is not None
    assert row.income == Decimal("0")
    assert row.appreciation == Decimal("0")


def test_exportacao_csv(session: Session) -> None:
    asset = _asset_vo(session, "CSV-TEST")
    _price(session, asset.id, date(2026, 4, 30), Decimal("1000"))
    _price(session, asset.id, date(2026, 5, 31), Decimal("1050"))

    svc = PerformanceReportService(session)
    report = svc.generate(2026, 5)
    rows = svc.to_csv_rows(report)

    assert any(r["Ticker"] == "CSV-TEST" for r in rows)
    row = next(r for r in rows if r["Ticker"] == "CSV-TEST")
    assert "Valorização (BRL)" in row
    assert "Rendimentos (BRL)" in row
    assert "Resultado (BRL)" in row
