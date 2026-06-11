"""Serviço de geração do Relatório Mensal de Performance."""
import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, Currency
from consultor_investimentos.repositories import ExchangeRateRepository, PerformanceRepository
from consultor_investimentos.services.dto import (
    PerformanceClassSummaryDTO,
    PerformanceReportDTO,
    PerformanceRowDTO,
)
from consultor_investimentos.utils.currency import convert_to_brl


class PerformanceReportService:
    def __init__(self, session: Session) -> None:
        self._perf_repo = PerformanceRepository(session)
        self._fx_repo = ExchangeRateRepository(session)

    def generate(self, year: int, month: int) -> PerformanceReportDTO:
        """Gera o relatório de performance para o mês/ano informados.

        Preço base: último AssetPrice com price_date <= último dia do mês anterior.
        Preço atual: último AssetPrice com price_date <= último dia do mês selecionado.
        Valorização: preço_atual_brl − preço_base_brl.
        Rendimentos: soma de DIVIDENDO + JUROS/CUPOM com date dentro do mês.
        """
        _, last_day = calendar.monthrange(year, month)
        period_start = date(year, month, 1)
        period_end = date(year, month, last_day)
        # Último dia do mês anterior
        base_date = date(year, month, 1).__class__(
            year if month > 1 else year - 1,
            month - 1 if month > 1 else 12,
            calendar.monthrange(
                year if month > 1 else year - 1,
                month - 1 if month > 1 else 12,
            )[1],
        )

        rates = self._fx_repo.get_rates()
        rates[Currency.BRL] = Decimal("1")

        assets = self._perf_repo.get_active_assets()

        rows_by_class: dict[AssetClass, list[PerformanceRowDTO]] = {}

        for asset in assets:
            currency = Currency(asset.currency)

            prev_ap = self._perf_repo.get_price_up_to(asset.id, base_date)
            prev_native = prev_ap.price if prev_ap else None
            prev_brl = (
                convert_to_brl(prev_native, currency, rates) if prev_native is not None else None
            )
            prev_date = prev_ap.price_date if prev_ap else None

            curr_ap = self._perf_repo.get_price_up_to(asset.id, period_end)
            curr_native = curr_ap.price if curr_ap else None
            curr_brl = (
                convert_to_brl(curr_native, currency, rates) if curr_native is not None else None
            )
            curr_date = curr_ap.price_date if curr_ap else None

            if prev_brl is not None and curr_brl is not None:
                appreciation = (curr_brl - prev_brl).quantize(Decimal("0.01"))
            else:
                appreciation = Decimal("0")

            # total_amount das transações de renda é sempre em BRL
            income_txs = self._perf_repo.get_income_in_period(asset.id, period_start, period_end)
            income = sum(
                (tx.total_amount for tx in income_txs), Decimal("0")
            ).quantize(Decimal("0.01"))

            row = PerformanceRowDTO(
                asset_id=asset.id,
                ticker=asset.ticker,
                asset_name=asset.name,
                asset_class=AssetClass(asset.asset_class),
                currency=currency,
                previous_price=prev_brl,
                current_price=curr_brl,
                previous_price_native=prev_native,
                current_price_native=curr_native,
                previous_price_date=prev_date,
                current_price_date=curr_date,
                appreciation=appreciation,
                income=income,
                total_result=(appreciation + income).quantize(Decimal("0.01")),
            )

            ac = AssetClass(asset.asset_class)
            rows_by_class.setdefault(ac, []).append(row)

        classes: list[PerformanceClassSummaryDTO] = []
        for ac, rows in rows_by_class.items():
            total_app = sum((r.appreciation for r in rows), Decimal("0")).quantize(Decimal("0.01"))
            total_inc = sum((r.income for r in rows), Decimal("0")).quantize(Decimal("0.01"))
            classes.append(
                PerformanceClassSummaryDTO(
                    asset_class=ac,
                    rows=rows,
                    total_appreciation=total_app,
                    total_income=total_inc,
                    total_result=(total_app + total_inc).quantize(Decimal("0.01")),
                )
            )

        total_appreciation = sum(
            (c.total_appreciation for c in classes), Decimal("0")
        ).quantize(Decimal("0.01"))
        total_income = sum(
            (c.total_income for c in classes), Decimal("0")
        ).quantize(Decimal("0.01"))

        return PerformanceReportDTO(
            year=year,
            month=month,
            classes=classes,
            total_appreciation=total_appreciation,
            total_income=total_income,
            total_result=(total_appreciation + total_income).quantize(Decimal("0.01")),
        )

    def to_csv_rows(self, report: PerformanceReportDTO) -> list[dict]:
        """Converte o relatório para lista de dicts prontos para CSV."""
        rows: list[dict] = []
        for cls_summary in report.classes:
            for row in cls_summary.rows:
                rows.append({
                    "Ticker": row.ticker,
                    "Ativo": row.asset_name,
                    "Classe": row.asset_class.value,
                    "Preço Base (BRL)": float(row.previous_price) if row.previous_price is not None else "",
                    "Preço Atual (BRL)": float(row.current_price) if row.current_price is not None else "",
                    "Valorização (BRL)": float(row.appreciation),
                    "Rendimentos (BRL)": float(row.income),
                    "Resultado (BRL)": float(row.total_result),
                })
        return rows
