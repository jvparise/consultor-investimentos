"""Testes unitários para BenchmarkRepository."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from consultor_investimentos.database import models  # noqa: F401
from consultor_investimentos.database.connection import Base
from consultor_investimentos.repositories.benchmark_repository import BenchmarkRepository


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = Session(engine)
    yield s
    s.close()
    engine.dispose()


# ── upsert ─────────────────────────────────────────────────────────────────────

def test_upsert_cria_registro(session):
    repo = BenchmarkRepository(session)
    record = repo.upsert("CDI", date(2026, 6, 1), Decimal("0.044"))

    assert record.id is not None
    assert record.benchmark_name == "CDI"
    assert record.reference_date == date(2026, 6, 1)
    assert record.value == Decimal("0.044")


def test_upsert_atualiza_existente(session):
    repo = BenchmarkRepository(session)
    repo.upsert("CDI", date(2026, 6, 1), Decimal("0.044"))
    updated = repo.upsert("CDI", date(2026, 6, 1), Decimal("0.045"))

    assert updated.value == Decimal("0.045")

    all_records = repo.get_history("CDI")
    assert len(all_records) == 1


def test_upsert_diferentes_benchmarks_nao_colidem(session):
    repo = BenchmarkRepository(session)
    repo.upsert("CDI", date(2026, 6, 1), Decimal("0.044"))
    repo.upsert("SELIC", date(2026, 6, 1), Decimal("1.093"))

    assert len(repo.get_history("CDI")) == 1
    assert len(repo.get_history("SELIC")) == 1


# ── get_latest ─────────────────────────────────────────────────────────────────

def test_get_latest_retorna_mais_recente(session):
    repo = BenchmarkRepository(session)
    repo.upsert("CDI", date(2026, 6, 1), Decimal("0.044"))
    repo.upsert("CDI", date(2026, 6, 10), Decimal("0.046"))
    repo.upsert("CDI", date(2026, 6, 5), Decimal("0.045"))

    latest = repo.get_latest("CDI")
    assert latest.reference_date == date(2026, 6, 10)


def test_get_latest_retorna_none_quando_vazio(session):
    assert BenchmarkRepository(session).get_latest("CDI") is None


def test_get_latest_nao_mistura_benchmarks(session):
    repo = BenchmarkRepository(session)
    repo.upsert("CDI", date(2026, 6, 10), Decimal("0.044"))

    assert repo.get_latest("IBOV") is None


# ── get_history ────────────────────────────────────────────────────────────────

def test_get_history_retorna_todos_em_ordem(session):
    repo = BenchmarkRepository(session)
    for i, v in enumerate(["0.044", "0.045", "0.046"]):
        repo.upsert("CDI", date(2026, 6, i + 1), Decimal(v))

    history = repo.get_history("CDI")
    assert len(history) == 3
    assert history[0].reference_date == date(2026, 6, 1)
    assert history[-1].reference_date == date(2026, 6, 3)


def test_get_history_filtra_por_start(session):
    repo = BenchmarkRepository(session)
    for i in range(5):
        repo.upsert("CDI", date(2026, 6, i + 1), Decimal("0.044"))

    history = repo.get_history("CDI", start=date(2026, 6, 3))
    assert len(history) == 3
    assert history[0].reference_date == date(2026, 6, 3)


def test_get_history_filtra_por_end(session):
    repo = BenchmarkRepository(session)
    for i in range(5):
        repo.upsert("CDI", date(2026, 6, i + 1), Decimal("0.044"))

    history = repo.get_history("CDI", end=date(2026, 6, 3))
    assert len(history) == 3
    assert history[-1].reference_date == date(2026, 6, 3)


def test_get_history_filtra_por_range(session):
    repo = BenchmarkRepository(session)
    for i in range(10):
        repo.upsert("CDI", date(2026, 6, i + 1), Decimal("0.044"))

    history = repo.get_history("CDI", start=date(2026, 6, 3), end=date(2026, 6, 7))
    assert len(history) == 5


def test_get_history_vazio(session):
    assert BenchmarkRepository(session).get_history("IBOV") == []


# ── exists ─────────────────────────────────────────────────────────────────────

def test_exists_verdadeiro(session):
    repo = BenchmarkRepository(session)
    repo.upsert("CDI", date(2026, 6, 1), Decimal("0.044"))
    assert repo.exists("CDI", date(2026, 6, 1)) is True


def test_exists_falso(session):
    assert BenchmarkRepository(session).exists("CDI", date(2026, 6, 1)) is False
