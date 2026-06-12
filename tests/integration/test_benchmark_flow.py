"""Testes de integração para o fluxo de benchmark (providers mockados)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from typing import Generator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from consultor_investimentos.config import Benchmark, SnapshotType
from consultor_investimentos.database import models  # noqa: F401
from consultor_investimentos.database.connection import Base
from consultor_investimentos.repositories.benchmark_repository import BenchmarkRepository
from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository
from consultor_investimentos.services.benchmark_service import BenchmarkService
from consultor_investimentos.services.market_data.market_data_service import MarketDataService


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


def _bcb_with_series(code_series: dict[int, list[tuple[date, Decimal]]]) -> MagicMock:
    m = MagicMock()
    m.get_series_range.side_effect = lambda code, start, end: code_series.get(code, [])
    m.get_ptax.return_value = None
    return m


def _yahoo_with_series(ticker_series: dict[str, list[tuple[date, Decimal]]]) -> MagicMock:
    m = MagicMock()
    m.get_history.side_effect = lambda ticker, start, end: ticker_series.get(ticker, [])
    m.get_price.return_value = None
    m.to_yahoo_ticker.return_value = "TEST"
    return m


def _make_cdi_series(n_days: int = 10) -> list[tuple[date, Decimal]]:
    return [(date(2026, 6, i + 1), Decimal("0.044")) for i in range(n_days)]


def _make_ibov_series(n_days: int = 10, base: int = 130000) -> list[tuple[date, Decimal]]:
    return [(date(2026, 6, i + 1), Decimal(str(base + i * 100))) for i in range(n_days)]


# ── Persistência ───────────────────────────────────────────────────────────────

def test_persistencia_cdi(fresh_engine) -> None:
    bcb = _bcb_with_series({12: _make_cdi_series(10)})
    yahoo = _yahoo_with_series({})

    with _db(fresh_engine) as session:
        BenchmarkService(session, yahoo=yahoo, bcb=bcb).update_benchmarks()

    with _db(fresh_engine) as session:
        history = BenchmarkRepository(session).get_history("CDI")
        assert len(history) == 10
        assert all(h.value == Decimal("0.044") for h in history)


def test_persistencia_ibov(fresh_engine) -> None:
    bcb = _bcb_with_series({})
    yahoo = _yahoo_with_series({"^BVSP": _make_ibov_series(5)})

    with _db(fresh_engine) as session:
        BenchmarkService(session, yahoo=yahoo, bcb=bcb).update_benchmarks()

    with _db(fresh_engine) as session:
        history = BenchmarkRepository(session).get_history("IBOV")
    assert len(history) == 5


def test_persistencia_todos_benchmarks(fresh_engine) -> None:
    series_per_code = {12: _make_cdi_series(3), 11: _make_cdi_series(3), 433: _make_cdi_series(3)}
    yahoo_series = {"^BVSP": _make_ibov_series(3), "^GSPC": _make_ibov_series(3, 5000)}

    bcb = _bcb_with_series(series_per_code)
    yahoo = _yahoo_with_series(yahoo_series)

    with _db(fresh_engine) as session:
        result = BenchmarkService(session, yahoo=yahoo, bcb=bcb).update_benchmarks()

    assert result[Benchmark.CDI.value] == 3
    assert result[Benchmark.IBOV.value] == 3
    assert result[Benchmark.SP500.value] == 3


# ── Update incremental ─────────────────────────────────────────────────────────

def test_incremental_busca_apenas_novos(fresh_engine) -> None:
    # Primeira carga: dias 1-5
    first_series = {12: _make_cdi_series(5)}
    with _db(fresh_engine) as session:
        BenchmarkService(
            session,
            yahoo=_yahoo_with_series({}),
            bcb=_bcb_with_series(first_series),
        ).update_benchmarks()

    # Segunda carga: apenas dias 6-10
    subsequent_series = {12: [(date(2026, 6, i + 6), Decimal("0.044")) for i in range(5)]}
    bcb2 = _bcb_with_series(subsequent_series)

    with _db(fresh_engine) as session:
        BenchmarkService(
            session,
            yahoo=_yahoo_with_series({}),
            bcb=bcb2,
        ).update_benchmarks()

        # Verifica que a segunda chamada pediu a partir do dia 6
        call_args = bcb2.get_series_range.call_args_list
        cdi_calls = [c for c in call_args if c.args[0] == 12]
        assert cdi_calls[0].args[1] == date(2026, 6, 6)


def test_atualizar_dois_dias_no_mesmo_dia_nao_duplica(fresh_engine) -> None:
    series = {12: [(date(2026, 6, 1), Decimal("0.044"))]}
    bcb = _bcb_with_series(series)

    with _db(fresh_engine) as session:
        BenchmarkService(session, yahoo=_yahoo_with_series({}), bcb=bcb).update_benchmarks()

    with _db(fresh_engine) as session:
        BenchmarkService(session, yahoo=_yahoo_with_series({}), bcb=bcb).update_benchmarks()

    with _db(fresh_engine) as session:
        history = BenchmarkRepository(session).get_history("CDI")
    assert len(history) == 1


# ── compare_with_portfolio ─────────────────────────────────────────────────────

def test_compare_fluxo_completo(fresh_engine) -> None:
    # Popula snapshots
    with _db(fresh_engine) as session:
        repo = SnapshotRepository(session)
        for i in range(5):
            repo.upsert(
                snapshot_date=date(2026, 6, i + 1),
                total_value=Decimal(f"{10000 + i * 100}"),
                snapshot_type=SnapshotType.CALCULATED,
                details=[],
            )

    # Popula CDI
    with _db(fresh_engine) as session:
        bcb = _bcb_with_series({
            12: [(date(2026, 6, i + 1), Decimal("0.05")) for i in range(5)],
        })
        BenchmarkService(
            session,
            yahoo=_yahoo_with_series({}),
            bcb=bcb,
        ).update_benchmarks()

    # Compara
    with _db(fresh_engine) as session:
        svc = BenchmarkService(session, yahoo=_yahoo_with_series({}), bcb=_bcb_with_series({}))
        dto = svc.compare_with_portfolio(date(2026, 6, 1), date(2026, 6, 5))

    assert len(dto.portfolio.points) == 5
    assert dto.portfolio.points[0].value == Decimal("100")
    assert len(dto.cdi.points) == 5
    assert dto.cdi.points[0].value == Decimal("100")


def test_compare_sem_dados_retorna_series_vazias(fresh_engine) -> None:
    with _db(fresh_engine) as session:
        dto = BenchmarkService(
            session,
            yahoo=_yahoo_with_series({}),
            bcb=_bcb_with_series({}),
        ).compare_with_portfolio(date(2026, 6, 1), date(2026, 6, 10))

    assert dto.portfolio.is_empty()
    assert dto.cdi.is_empty()
    assert dto.ibov.is_empty()


def test_benchmark_ausente_nao_afeta_portfolio(fresh_engine) -> None:
    """Ausência de IBOV não impede retornar portfolio e CDI."""
    with _db(fresh_engine) as session:
        repo = SnapshotRepository(session)
        repo.upsert(
            snapshot_date=date(2026, 6, 1),
            total_value=Decimal("10000"),
            snapshot_type=SnapshotType.CALCULATED,
            details=[],
        )
        BenchmarkRepository(session).upsert("CDI", date(2026, 6, 1), Decimal("0.05"))
        session.flush()

    with _db(fresh_engine) as session:
        dto = BenchmarkService(
            session,
            yahoo=_yahoo_with_series({}),
            bcb=_bcb_with_series({}),
        ).compare_with_portfolio(date(2026, 6, 1), date(2026, 6, 5))

    assert not dto.portfolio.is_empty()
    assert not dto.cdi.is_empty()
    assert dto.ibov.is_empty()


# ── Integração com MarketDataService ──────────────────────────────────────────

def test_update_benchmarks_via_market_data_service(fresh_engine) -> None:
    cdi_series = _make_cdi_series(5)
    bcb = _bcb_with_series({12: cdi_series, 11: cdi_series, 433: cdi_series})
    yahoo = _yahoo_with_series({"^BVSP": _make_ibov_series(5), "^GSPC": _make_ibov_series(5, 5000)})

    with _db(fresh_engine) as session:
        result = MarketDataService(session, yahoo=yahoo, bcb=bcb).update_benchmarks()

    assert result[Benchmark.CDI.value] == 5
    assert result[Benchmark.IBOV.value] == 5
