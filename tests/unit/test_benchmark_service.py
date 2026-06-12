"""Testes unitários para BenchmarkService — providers e banco mockados."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from consultor_investimentos.config import Benchmark, SnapshotType
from consultor_investimentos.database import models  # noqa: F401
from consultor_investimentos.database.connection import Base
from consultor_investimentos.repositories.benchmark_repository import BenchmarkRepository
from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository
from consultor_investimentos.services.benchmark_service import (
    BenchmarkService,
    _compound_rates,
    _normalize_price_series,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = Session(engine)
    yield s
    s.close()
    engine.dispose()


def _bcb_returning(series: list[tuple[date, Decimal]]) -> MagicMock:
    m = MagicMock()
    m.get_series_range.return_value = series
    return m


def _bcb_empty() -> MagicMock:
    m = MagicMock()
    m.get_series_range.return_value = []
    return m


def _yahoo_returning(series: list[tuple[date, Decimal]]) -> MagicMock:
    m = MagicMock()
    m.get_history.return_value = series
    return m


def _yahoo_empty() -> MagicMock:
    m = MagicMock()
    m.get_history.return_value = []
    return m


def _make_snapshot(session, snap_date: date, value: Decimal) -> None:
    SnapshotRepository(session).upsert(
        snapshot_date=snap_date,
        total_value=value,
        snapshot_type=SnapshotType.CALCULATED,
        details=[],
    )
    session.flush()


# ── update_benchmarks ──────────────────────────────────────────────────────────

def test_update_cdi_persiste_serie_bcb(session):
    series = [(date(2026, 6, i + 1), Decimal("0.044")) for i in range(5)]
    bcb = _bcb_returning(series)
    yahoo = _yahoo_empty()

    svc = BenchmarkService(session, yahoo=yahoo, bcb=bcb)
    result = svc.update_benchmarks()

    assert result[Benchmark.CDI.value] == 5
    history = BenchmarkRepository(session).get_history("CDI")
    assert len(history) == 5


def test_update_ibov_persiste_serie_yahoo(session):
    series = [(date(2026, 6, i + 1), Decimal(f"{130000 + i * 100}")) for i in range(3)]
    bcb = _bcb_empty()
    yahoo = _yahoo_returning(series)

    svc = BenchmarkService(session, yahoo=yahoo, bcb=bcb)
    result = svc.update_benchmarks()

    assert result[Benchmark.IBOV.value] == 3
    history = BenchmarkRepository(session).get_history("IBOV")
    assert len(history) == 3


def test_update_incremental_busca_apenas_novos(session):
    # Pre-populate CDI até o dia 5
    repo = BenchmarkRepository(session)
    for i in range(5):
        repo.upsert("CDI", date(2026, 6, i + 1), Decimal("0.044"))
    session.flush()

    # BCB retorna dados novos do dia 6 em diante
    new_series = [(date(2026, 6, i + 6), Decimal("0.044")) for i in range(3)]
    bcb = _bcb_returning(new_series)

    svc = BenchmarkService(session, yahoo=_yahoo_empty(), bcb=bcb)
    svc.update_benchmarks()

    # Verifica que get_series_range foi chamado com start = dia 6
    call_args = bcb.get_series_range.call_args_list
    cdi_calls = [c for c in call_args if c.args[0] == 12]
    assert len(cdi_calls) > 0
    start_arg = cdi_calls[0].args[1]
    assert start_arg == date(2026, 6, 6)


def test_update_falha_em_um_nao_afeta_outros(session):
    bcb = MagicMock()
    bcb.get_series_range.side_effect = Exception("timeout")

    yahoo_series = [(date(2026, 6, 1), Decimal("130000"))]
    yahoo = _yahoo_returning(yahoo_series)

    svc = BenchmarkService(session, yahoo=yahoo, bcb=bcb)
    result = svc.update_benchmarks()

    assert result[Benchmark.CDI.value] == -1
    assert result[Benchmark.IBOV.value] == 1


# ── _compound_rates ────────────────────────────────────────────────────────────

def _make_history_objs(session, name: str, rates: list[tuple[date, str]]):
    repo = BenchmarkRepository(session)
    for d, v in rates:
        repo.upsert(name, d, Decimal(v))
    session.flush()
    return repo.get_history(name)


def test_compound_rates_primeiro_ponto_100(session):
    history = _make_history_objs(session, "CDI", [
        (date(2026, 6, 1), "0.05"),
        (date(2026, 6, 2), "0.05"),
        (date(2026, 6, 3), "0.05"),
    ])
    points = _compound_rates(history)
    assert points[0].value == Decimal("100")


def test_compound_rates_crescimento_correto(session):
    """Taxa 0.05% ao dia por 3 dias deve resultar em ~100.15."""
    history = _make_history_objs(session, "CDI", [
        (date(2026, 6, 1), "0.05"),
        (date(2026, 6, 2), "0.05"),
        (date(2026, 6, 3), "0.05"),
    ])
    points = _compound_rates(history)
    # (1.0005)^3 / (1.0005) * 100 ≈ 100.10 no ponto 2
    assert points[-1].value > points[0].value


def test_compound_rates_vazio():
    assert _compound_rates([]) == []


# ── _normalize_price_series ────────────────────────────────────────────────────

def test_normalize_price_series_primeiro_ponto_100(session):
    history = _make_history_objs(session, "IBOV", [
        (date(2026, 6, 1), "130000"),
        (date(2026, 6, 2), "131000"),
        (date(2026, 6, 3), "132000"),
    ])
    points = _normalize_price_series(history)
    assert points[0].value == Decimal("100")


def test_normalize_price_series_calculo_correto(session):
    history = _make_history_objs(session, "IBOV", [
        (date(2026, 6, 1), "100"),
        (date(2026, 6, 2), "110"),
    ])
    points = _normalize_price_series(history)
    assert points[1].value == Decimal("110")


def test_normalize_price_series_vazio():
    assert _normalize_price_series([]) == []


# ── compare_with_portfolio ─────────────────────────────────────────────────────

def test_compare_normaliza_base_100(session):
    _make_snapshot(session, date(2026, 6, 1), Decimal("10000"))
    _make_snapshot(session, date(2026, 6, 5), Decimal("11000"))

    repo = BenchmarkRepository(session)
    repo.upsert("CDI", date(2026, 6, 1), Decimal("0.05"))
    repo.upsert("CDI", date(2026, 6, 5), Decimal("0.05"))
    session.flush()

    svc = BenchmarkService(session, yahoo=_yahoo_empty(), bcb=_bcb_empty())
    dto = svc.compare_with_portfolio(date(2026, 6, 1), date(2026, 6, 10))

    assert dto.portfolio.points[0].value == Decimal("100")
    assert dto.cdi.points[0].value == Decimal("100")


def test_compare_carteira_vazia_retorna_serie_vazia(session):
    svc = BenchmarkService(session, yahoo=_yahoo_empty(), bcb=_bcb_empty())
    dto = svc.compare_with_portfolio(date(2026, 6, 1), date(2026, 6, 10))

    assert dto.portfolio.is_empty()


def test_compare_sem_benchmark_retorna_serie_vazia(session):
    _make_snapshot(session, date(2026, 6, 1), Decimal("10000"))

    svc = BenchmarkService(session, yahoo=_yahoo_empty(), bcb=_bcb_empty())
    dto = svc.compare_with_portfolio(date(2026, 6, 1), date(2026, 6, 10))

    assert dto.cdi.is_empty()
    assert dto.ibov.is_empty()


def test_compare_retorna_todos_benchmarks(session):
    _make_snapshot(session, date(2026, 6, 1), Decimal("10000"))

    repo = BenchmarkRepository(session)
    for b in ("CDI", "SELIC", "IPCA"):
        repo.upsert(b, date(2026, 6, 1), Decimal("0.05"))
    for b in ("IBOV", "SP500"):
        repo.upsert(b, date(2026, 6, 1), Decimal("100"))
    session.flush()

    svc = BenchmarkService(session, yahoo=_yahoo_empty(), bcb=_bcb_empty())
    dto = svc.compare_with_portfolio(date(2026, 6, 1), date(2026, 6, 10))

    assert not dto.cdi.is_empty()
    assert not dto.selic.is_empty()
    assert not dto.ipca.is_empty()
    assert not dto.ibov.is_empty()
    assert not dto.sp500.is_empty()


def test_rentability_pct_positivo(session):
    _make_snapshot(session, date(2026, 6, 1), Decimal("10000"))
    _make_snapshot(session, date(2026, 6, 30), Decimal("11000"))

    svc = BenchmarkService(session, yahoo=_yahoo_empty(), bcb=_bcb_empty())
    dto = svc.compare_with_portfolio(date(2026, 6, 1), date(2026, 6, 30))

    ret = dto.portfolio.rentability_pct()
    assert ret is not None
    assert ret > 0


def test_rentability_pct_serie_vazia():
    from consultor_investimentos.services.dto import BenchmarkSeriesDTO
    s = BenchmarkSeriesDTO(name="CDI", points=[])
    assert s.rentability_pct() is None
