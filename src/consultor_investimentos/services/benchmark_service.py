from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from consultor_investimentos.config import Benchmark
from consultor_investimentos.repositories.benchmark_repository import BenchmarkRepository
from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository
from consultor_investimentos.services.dto import (
    BenchmarkPointDTO,
    BenchmarkSeriesDTO,
    PortfolioVsBenchmarkDTO,
)
from consultor_investimentos.services.market_data.bcb_provider import BCBProvider
from consultor_investimentos.services.market_data.yahoo_provider import YahooProvider

_BCB_CODES = {
    Benchmark.CDI: 12,
    Benchmark.SELIC: 11,
    Benchmark.IPCA: 433,
}
_YAHOO_TICKERS = {
    Benchmark.IBOV: "^BVSP",
    Benchmark.SP500: "^GSPC",
}
_DEFAULT_HISTORY_YEARS = 3


def _compound_rates(history: list) -> list[BenchmarkPointDTO]:
    """Computa fator acumulado (base 100) para séries de taxas periódicas (CDI/SELIC/IPCA)."""
    cumulative = Decimal("1")
    raw = []
    for h in history:
        factor = Decimal("1") + h.value / Decimal("100")
        cumulative *= factor
        raw.append((h.reference_date, cumulative))

    if not raw:
        return []

    base = raw[0][1]
    if base == 0:
        return []
    return [BenchmarkPointDTO(date=d, value=(v / base * Decimal("100")).quantize(Decimal("0.0001")))
            for d, v in raw]


def _normalize_price_series(history: list) -> list[BenchmarkPointDTO]:
    """Normaliza série de preços absolutos (IBOV, SP500) para base 100."""
    if not history:
        return []
    base = history[0].value
    if base == 0:
        return []
    return [
        BenchmarkPointDTO(
            date=h.reference_date,
            value=(h.value / base * Decimal("100")).quantize(Decimal("0.0001")),
        )
        for h in history
    ]


def _normalize_portfolio(snapshots: list) -> list[BenchmarkPointDTO]:
    if not snapshots:
        return []
    base = snapshots[0].total_value
    if base == 0:
        return []
    return [
        BenchmarkPointDTO(
            date=s.snapshot_date,
            value=(s.total_value / base * Decimal("100")).quantize(Decimal("0.0001")),
        )
        for s in snapshots
    ]


class BenchmarkService:
    def __init__(
        self,
        session: Session,
        yahoo: YahooProvider | None = None,
        bcb: BCBProvider | None = None,
    ) -> None:
        self._session = session
        self._repo = BenchmarkRepository(session)
        self._snapshot_repo = SnapshotRepository(session)
        self._yahoo = yahoo or YahooProvider()
        self._bcb = bcb or BCBProvider()

    def update_benchmarks(self) -> dict[str, int]:
        """Atualiza histórico de todos os benchmarks. Retorna contagem por benchmark."""
        default_start = date.today() - timedelta(days=365 * _DEFAULT_HISTORY_YEARS)
        results: dict[str, int] = {}

        for benchmark, code in _BCB_CODES.items():
            try:
                latest = self._repo.get_latest(benchmark.value)
                start = (latest.reference_date + timedelta(days=1)) if latest else default_start
                if start > date.today():
                    results[benchmark.value] = 0
                    continue
                series = self._bcb.get_series_range(code, start, date.today())
                count = 0
                for ref_date, value in series:
                    self._repo.upsert(benchmark.value, ref_date, value)
                    count += 1
                results[benchmark.value] = count
            except Exception:
                results[benchmark.value] = -1

        for benchmark, ticker in _YAHOO_TICKERS.items():
            try:
                latest = self._repo.get_latest(benchmark.value)
                start = (latest.reference_date + timedelta(days=1)) if latest else default_start
                if start > date.today():
                    results[benchmark.value] = 0
                    continue
                series = self._yahoo.get_history(ticker, start, date.today())
                count = 0
                for ref_date, value in series:
                    self._repo.upsert(benchmark.value, ref_date, value)
                    count += 1
                results[benchmark.value] = count
            except Exception:
                results[benchmark.value] = -1

        return results

    def get_benchmark_series(
        self, name: str, start: date | None = None, end: date | None = None
    ) -> BenchmarkSeriesDTO:
        history = self._repo.get_history(name, start, end)
        if not history:
            return BenchmarkSeriesDTO(name=name, points=[])

        if name in (Benchmark.CDI.value, Benchmark.SELIC.value, Benchmark.IPCA.value):
            points = _compound_rates(history)
        else:
            points = _normalize_price_series(history)

        return BenchmarkSeriesDTO(name=name, points=points)

    def compare_with_portfolio(
        self, start_date: date, end_date: date
    ) -> PortfolioVsBenchmarkDTO:
        snapshots = self._snapshot_repo.get_history(start=start_date, end=end_date)
        portfolio_points = _normalize_portfolio(snapshots)
        portfolio = BenchmarkSeriesDTO(name="Carteira", points=portfolio_points)

        def _series(b: Benchmark) -> BenchmarkSeriesDTO:
            return self.get_benchmark_series(b.value, start_date, end_date)

        return PortfolioVsBenchmarkDTO(
            portfolio=portfolio,
            cdi=_series(Benchmark.CDI),
            selic=_series(Benchmark.SELIC),
            ipca=_series(Benchmark.IPCA),
            ibov=_series(Benchmark.IBOV),
            sp500=_series(Benchmark.SP500),
            start_date=start_date,
            end_date=end_date,
        )
