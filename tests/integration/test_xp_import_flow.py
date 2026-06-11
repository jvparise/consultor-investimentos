"""Testes de integração: XPParser → ImportService (validate + commit + snapshot).

Usa engines SQLite isoladas com estado commitado, simulando o comportamento de
produção (equivalente ao get_db() da aplicação).
"""
from __future__ import annotations

import io
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Generator

import openpyxl
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType, TransactionType
from consultor_investimentos.database import models  # noqa: F401 — registra tabelas
from consultor_investimentos.database.connection import Base
from consultor_investimentos.importers.csv_parser import compute_file_hash
from consultor_investimentos.importers.xp_parser import XPParser
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.import_log_repository import ImportLogRepository
from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository
from consultor_investimentos.services.import_service import ImportService
from consultor_investimentos.services.snapshot_service import SnapshotService

# ── Infra de teste ────────────────────────────────────────────────────────────

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


def _make_qp_asset(engine, ticker: str = "VALE3", qty: str = "100", price: str = "65.50") -> int:
    """Cria ativo QP com INITIAL_BALANCE + preço registrado (simula TransactionService)."""
    from consultor_investimentos.repositories.holding_repository import HoldingRepository

    with _db(engine) as session:
        asset = AssetRepository(session).create(
            ticker=ticker,
            name=f"Ativo {ticker}",
            asset_class=AssetClass.EQUITY,
            income_type=IncomeType.VARIABLE,
            tracking_type=AssetTrackingType.QUANTITY_PRICE,
        )
        ContributionRepository(session).create(
            asset_id=asset.id,
            transaction_type=TransactionType.INITIAL_BALANCE,
            date=date(2024, 1, 2),
            total_amount=Decimal(qty) * Decimal(price),
            quantity=Decimal(qty),
            unit_price=Decimal(price),
        )
        # Registra preço inicial para que ensure_snapshot_for_today() encontre o ativo
        HoldingRepository(session).upsert(
            asset_id=asset.id,
            price_date=date(2024, 1, 2),
            price=Decimal(price),
        )
        return asset.id


def _xp_csv(*rows: str) -> bytes:
    hdr = "Data;Movimentação;Ativo;Quantidade;Preço;Valor Financeiro;Observação\n"
    return (hdr + "\n".join(rows)).encode("utf-8")


def _xp_xlsx(*rows: tuple) -> bytes:
    hdrs = ("Data", "Movimentação", "Ativo", "Quantidade", "Preço", "Valor Financeiro", "Observação")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(hdrs))
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Testes de validate ────────────────────────────────────────────────────────

def test_xp_csv_validate_ok(fresh_engine) -> None:
    _make_qp_asset(fresh_engine, "VALE3", qty="100", price="65.50")
    raw = _xp_csv("01/02/2024;Compra;VALE3;50;65,50;3275,00;")

    txs, errors = XPParser().parse(raw)
    assert errors == []

    with _db(fresh_engine) as session:
        result = ImportService(session).validate(txs, file_hash=compute_file_hash(raw))

    assert result.is_duplicate is False
    assert result.error_rows == 0
    assert result.valid_rows == 1


def test_xp_xlsx_validate_ok(fresh_engine) -> None:
    _make_qp_asset(fresh_engine, "ITUB4", qty="100", price="32.00")
    raw = _xp_xlsx(("01/03/2024", "Compra", "ITUB4", 50, 32.0, 1600.0, ""))

    txs, errors = XPParser().parse(raw)
    assert errors == []

    with _db(fresh_engine) as session:
        result = ImportService(session).validate(txs, file_hash=compute_file_hash(raw))

    assert result.valid_rows == 1


def test_xp_validate_ticker_nao_encontrado(fresh_engine) -> None:
    raw = _xp_csv("01/02/2024;Compra;INEXISTENTE;10;50,00;500,00;")
    txs, _ = XPParser().parse(raw)

    with _db(fresh_engine) as session:
        result = ImportService(session).validate(txs)

    assert result.error_rows == 1
    assert "não encontrado" in result.rows[0].message


# ── Testes de commit ──────────────────────────────────────────────────────────

def test_xp_commit_persiste_transacao(fresh_engine) -> None:
    asset_id = _make_qp_asset(fresh_engine, "PETR4", qty="100", price="35.00")
    raw = _xp_csv("01/02/2024;Compra;PETR4;50;35,00;1750,00;")
    txs, _ = XPParser().parse(raw)

    with _db(fresh_engine) as session:
        result = ImportService(session).commit(txs, file_hash=compute_file_hash(raw), file_name="xp_extrato.csv")

    assert result.valid_rows == 1

    # Acessa atributos DENTRO da sessão para evitar DetachedInstanceError
    with _db(fresh_engine) as session:
        all_txs = ContributionRepository(session).get_by_asset(asset_id)
        types = {TransactionType(t.transaction_type) for t in all_txs}
    assert TransactionType.BUY in types


def test_xp_commit_dividendo(fresh_engine) -> None:
    asset_id = _make_qp_asset(fresh_engine, "BBAS3")
    raw = _xp_csv("15/03/2024;Dividendo;BBAS3;;;250,00;Dividendo marco")
    txs, _ = XPParser().parse(raw)

    with _db(fresh_engine) as session:
        ImportService(session).commit(txs)

    with _db(fresh_engine) as session:
        all_txs = ContributionRepository(session).get_by_asset(asset_id)
        types = {TransactionType(t.transaction_type) for t in all_txs}
    assert TransactionType.DIVIDEND in types


# ── Snapshot ──────────────────────────────────────────────────────────────────

def test_snapshot_criado_apos_xp_import(fresh_engine) -> None:
    """Snapshot é criado após commit XP (mesmo caminho que CSV InvestorIA)."""
    _make_qp_asset(fresh_engine, "WEGE3", qty="50", price="40.00")
    raw = _xp_csv("01/02/2024;Compra;WEGE3;25;40,00;1000,00;")
    txs, _ = XPParser().parse(raw)

    with _db(fresh_engine) as session:
        ImportService(session).commit(txs)
        SnapshotService(session).ensure_snapshot_for_today()

    with _db(fresh_engine) as session:
        snap = SnapshotRepository(session).get_latest()
        assert snap is not None
        assert snap.total_value > Decimal("0")


# ── Audit log ─────────────────────────────────────────────────────────────────

def test_audit_log_criado_apos_xp_commit(fresh_engine) -> None:
    _make_qp_asset(fresh_engine, "ELET3")
    raw = _xp_csv("01/02/2024;Compra;ELET3;10;45,00;450,00;")
    txs, _ = XPParser().parse(raw)
    file_hash = compute_file_hash(raw)

    with _db(fresh_engine) as session:
        ImportService(session).commit(txs, file_hash=file_hash, file_name="xp.csv")

    with _db(fresh_engine) as session:
        assert ImportLogRepository(session).has_successful_import(file_hash) is True


# ── Idempotência ──────────────────────────────────────────────────────────────

def test_idempotencia_xp_bloqueada_apos_sucesso(fresh_engine) -> None:
    _make_qp_asset(fresh_engine, "ABEV3")
    raw = _xp_csv("01/02/2024;Compra;ABEV3;20;15,00;300,00;")
    txs, _ = XPParser().parse(raw)
    file_hash = compute_file_hash(raw)

    with _db(fresh_engine) as session:
        ImportService(session).commit(txs, file_hash=file_hash)

    with _db(fresh_engine) as session:
        result = ImportService(session).validate(txs, file_hash=file_hash)

    assert result.is_duplicate is True
    assert "já foi importado" in result.rows[0].message


def test_reimportacao_bloqueada_xlsx(fresh_engine) -> None:
    _make_qp_asset(fresh_engine, "ITSA4")
    raw = _xp_xlsx(("01/02/2024", "Compra", "ITSA4", 30, 10.0, 300.0, ""))
    txs, _ = XPParser().parse(raw)
    file_hash = compute_file_hash(raw)

    with _db(fresh_engine) as session:
        ImportService(session).commit(txs, file_hash=file_hash)

    with _db(fresh_engine) as session:
        result2 = ImportService(session).validate(txs, file_hash=file_hash)

    assert result2.is_duplicate is True


def test_reimportacao_permitida_apos_falha(fresh_engine) -> None:
    """Falha não registra audit log → mesmo hash pode ser reimportado."""
    _make_qp_asset(fresh_engine, "BBDC4", qty="10", price="20.00")
    raw = _xp_csv("01/02/2024;Venda;BBDC4;999;20,00;19980,00;")  # excede saldo → falha
    txs, _ = XPParser().parse(raw)
    file_hash = compute_file_hash(raw)

    with pytest.raises(Exception):
        with _db(fresh_engine) as session:
            ImportService(session).commit(txs, file_hash=file_hash)

    # Deve poder validar novamente sem bloqueio
    raw_ok = _xp_csv("01/02/2024;Compra;BBDC4;5;20,00;100,00;")
    txs_ok, _ = XPParser().parse(raw_ok)
    with _db(fresh_engine) as session:
        result = ImportService(session).validate(txs_ok, file_hash=compute_file_hash(raw_ok))

    assert result.is_duplicate is False


# ── Fluxo completo end-to-end ─────────────────────────────────────────────────

def test_fluxo_completo_xp_csv(fresh_engine) -> None:
    """Bytes XP CSV → parse → validate → commit → snapshot → audit log."""
    _make_qp_asset(fresh_engine, "BBSE3", qty="50", price="30.00")

    raw = _xp_csv(
        "01/02/2024;Compra;BBSE3;20;30,00;600,00;Compra XP",
        "15/02/2024;Dividendo;BBSE3;;;50,00;Dividendo fev",
    )
    file_hash = compute_file_hash(raw)

    txs, errors = XPParser().parse(raw)
    assert errors == []
    assert len(txs) == 2

    with _db(fresh_engine) as session:
        preview = ImportService(session).validate(txs, file_hash=file_hash)
    assert preview.error_rows == 0

    with _db(fresh_engine) as session:
        result = ImportService(session).commit(txs, file_hash=file_hash, file_name="xp.csv")
        SnapshotService(session).ensure_snapshot_for_today()

    assert result.valid_rows == 2

    with _db(fresh_engine) as session:
        assert ImportLogRepository(session).has_successful_import(file_hash) is True
        snap = SnapshotRepository(session).get_latest()
        assert snap is not None
