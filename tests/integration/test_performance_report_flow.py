"""Teste de integração: fluxo completo do Relatório de Performance."""
from datetime import date
from decimal import Decimal

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


def test_fluxo_completo_brl(session: Session) -> None:
    """Asset → Transaction → AssetPrice → ReportService → DTO."""
    # Setup
    asset = AssetRepository(session).create(
        ticker="BBAS3",
        name="Banco do Brasil",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2026, 1, 2),
        total_amount=Decimal("5500"),
        quantity=Decimal("100"),
        unit_price=Decimal("55.00"),
    )
    # Preço base (fim de abril)
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2026, 4, 30),
        price=Decimal("58.00"),
    )
    # Preço atual (fim de maio)
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2026, 5, 28),
        price=Decimal("60.50"),
    )
    # Dividendo em maio
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.DIVIDEND,
        date=date(2026, 5, 15),
        total_amount=Decimal("250.00"),
    )

    report = PerformanceReportService(session).generate(2026, 5)

    all_rows = [r for c in report.classes for r in c.rows]
    row = next(r for r in all_rows if r.ticker == "BBAS3")

    assert row.previous_price == Decimal("58.00")
    assert row.current_price == Decimal("60.50")
    assert row.appreciation == Decimal("2.50")
    assert row.income == Decimal("250.00")
    assert row.total_result == Decimal("252.50")
    assert report.total_result >= Decimal("252.50")


def test_fluxo_completo_usd(session: Session) -> None:
    """Ativo em USD deve ser convertido para BRL no relatório."""
    ExchangeRateRepository(session).upsert(Currency.USD, Decimal("5.00"))

    asset = AssetRepository(session).create(
        ticker="IVV",
        name="iShares S&P 500",
        asset_class=AssetClass.INTERNATIONAL,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
        currency=Currency.USD,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2026, 1, 2),
        total_amount=Decimal("2500.00"),
        quantity=Decimal("5"),
        unit_price=Decimal("500.00"),
    )
    # Preço em USD
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2026, 4, 30),
        price=Decimal("510.00"),   # USD
    )
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2026, 5, 31),
        price=Decimal("520.00"),   # USD
    )

    report = PerformanceReportService(session).generate(2026, 5)

    all_rows = [r for c in report.classes for r in c.rows]
    row = next(r for r in all_rows if r.ticker == "IVV")

    # Valores nativos devem estar em USD
    assert row.previous_price_native == Decimal("510.00")
    assert row.current_price_native == Decimal("520.00")

    # Valores em BRL = valor_nativo × taxa (5.00)
    assert row.previous_price == Decimal("510.00") * Decimal("5")
    assert row.current_price == Decimal("520.00") * Decimal("5")

    # Valorização = (520 - 510) × 5 = 50 BRL
    assert row.appreciation == Decimal("50.00")


def test_relatorio_sem_preco_nao_quebra(session: Session) -> None:
    """Ativo sem nenhum preço não deve lançar exceção."""
    AssetRepository(session).create(
        ticker="SEM-PRECO",
        name="Ativo Sem Preço",
        asset_class=AssetClass.CASH,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )

    report = PerformanceReportService(session).generate(2026, 5)

    all_rows = [r for c in report.classes for r in c.rows]
    row = next(r for r in all_rows if r.ticker == "SEM-PRECO")
    assert row.previous_price is None
    assert row.current_price is None
    assert row.appreciation == Decimal("0")
    assert row.total_result == Decimal("0")


def test_dividendo_fora_do_mes_nao_conta(session: Session) -> None:
    """Dividendo lançado em mês diferente do relatório não deve ser incluído."""
    asset = AssetRepository(session).create(
        ticker="ITUB4",
        name="Itaú Unibanco",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2026, 1, 2),
        total_amount=Decimal("3000"),
        quantity=Decimal("100"),
        unit_price=Decimal("30.00"),
    )
    # Dividendo em abril (fora do período de maio)
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.DIVIDEND,
        date=date(2026, 4, 15),
        total_amount=Decimal("500.00"),
    )

    report = PerformanceReportService(session).generate(2026, 5)

    all_rows = [r for c in report.classes for r in c.rows]
    row = next(r for r in all_rows if r.ticker == "ITUB4")
    assert row.income == Decimal("0")


def test_csv_contem_todos_ativos(session: Session) -> None:
    """CSV exportado deve conter uma linha para cada ativo ativo."""
    for i in range(3):
        a = AssetRepository(session).create(
            ticker=f"CSV-{i}",
            name=f"Ativo CSV {i}",
            asset_class=AssetClass.FIXED_INCOME,
            income_type=IncomeType.FIXED,
            tracking_type=AssetTrackingType.VALUE_ONLY,
        )
        HoldingRepository(session).upsert(
            asset_id=a.id,
            price_date=date(2026, 5, 31),
            price=Decimal(f"{1000 * (i + 1)}"),
        )

    svc = PerformanceReportService(session)
    report = svc.generate(2026, 5)
    rows = svc.to_csv_rows(report)

    tickers_in_csv = [r["Ticker"] for r in rows]
    for i in range(3):
        assert f"CSV-{i}" in tickers_in_csv
