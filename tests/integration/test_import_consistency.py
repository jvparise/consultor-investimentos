"""Testes de consistência do sistema de importação — camada de integração.

Estes testes usam engines isoladas com estado commitado entre operações,
simulando exatamente o comportamento do get_db() em produção.
"""
import hashlib
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType, TransactionType
from consultor_investimentos.database import models  # noqa: F401 — registra todos os modelos
from consultor_investimentos.database.connection import Base
from consultor_investimentos.importers.csv_parser import compute_file_hash, parse_csv
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.import_log_repository import ImportLogRepository
from consultor_investimentos.services.dto import ImportTransaction
from consultor_investimentos.services.import_service import ImportService
from consultor_investimentos.services.snapshot_service import SnapshotService


# ── Infraestrutura de teste ───────────────────────────────────────────────────────

@pytest.fixture
def fresh_engine():
    """Engine SQLite em memória isolada por teste — simula ambiente de produção."""
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(_engine, "connect")
    def set_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(_engine)
    yield _engine
    _engine.dispose()


@contextmanager
def _db(engine) -> Generator[Session, None, None]:
    """Simula get_db(): commit no final, rollback automático em exceção."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _setup_qp_asset(engine, ticker: str = "BBDC4", qty: str = "100", price: str = "100.00") -> int:
    """Cria ativo QP com INITIAL_BALANCE e persiste (commit). Retorna asset.id."""
    with _db(engine) as session:
        asset = AssetRepository(session).create(
            ticker=ticker,
            name=f"Asset {ticker}",
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
        return asset.id


def _make_tx(
    ticker: str,
    tx_type: TransactionType,
    tx_date: date,
    total: str,
    qty: str | None = None,
    price: str | None = None,
    row: int = 2,
) -> ImportTransaction:
    return ImportTransaction(
        ticker=ticker,
        transaction_type=tx_type,
        tx_date=tx_date,
        total_amount=Decimal(total),
        quantity=Decimal(qty) if qty else None,
        unit_price=Decimal(price) if price else None,
        row_number=row,
    )


# ── Atomicidade (all-or-nothing) ──────────────────────────────────────────────────

def test_rollback_atomico_sem_transacao_parcial(fresh_engine) -> None:
    """Batch com linha inválida: nenhuma transação deve sobreviver ao rollback."""
    asset_id = _setup_qp_asset(fresh_engine, ticker="BBDC4", qty="100", price="100.00")

    # Batch: BUY válido (linha 2) + SELL inválido — vender 999 com saldo 100+50=150 (linha 3)
    tx1 = _make_tx("BBDC4", TransactionType.BUY,  date(2024, 2, 1), "5000.00", qty="50",  price="100.00", row=2)
    tx2 = _make_tx("BBDC4", TransactionType.SELL, date(2024, 3, 1), "99900.00", qty="999", price="100.00", row=3)

    with pytest.raises(ValueError):
        with _db(fresh_engine) as session:
            ImportService(session).commit([tx1, tx2])

    # Nova sessão independente: somente o INITIAL_BALANCE original deve existir
    with _db(fresh_engine) as session:
        txs = ContributionRepository(session).get_by_asset(asset_id)
        assert len(txs) == 1
        assert TransactionType(txs[0].transaction_type) == TransactionType.INITIAL_BALANCE


def test_rollback_atomico_ticker_inexistente_no_meio(fresh_engine) -> None:
    """Ticker inexistente no meio do batch: nenhuma linha anterior deve ser commitada."""
    asset_id = _setup_qp_asset(fresh_engine, ticker="VALE3", qty="100", price="50.00")

    tx1 = _make_tx("VALE3",     TransactionType.BUY, date(2024, 2, 1), "1000.00", qty="20", price="50.00", row=2)
    tx2 = _make_tx("NAOEXISTE", TransactionType.BUY, date(2024, 3, 1), "1000.00", qty="10", price="100.00", row=3)

    with pytest.raises(ValueError, match="não encontrado"):
        with _db(fresh_engine) as session:
            ImportService(session).commit([tx1, tx2])

    with _db(fresh_engine) as session:
        txs = ContributionRepository(session).get_by_asset(asset_id)
        assert len(txs) == 1  # Somente INITIAL_BALANCE


def test_audit_log_rollbackado_junto_com_import(fresh_engine) -> None:
    """Se commit() falha, o audit log NÃO deve ter sido persistido."""
    _setup_qp_asset(fresh_engine, ticker="PETR4", qty="100", price="35.00")

    tx = _make_tx("PETR4", TransactionType.SELL, date(2024, 3, 1), "99000.00", qty="999", price="35.00")
    file_hash = "hash-rollback-audit"

    with pytest.raises(ValueError):
        with _db(fresh_engine) as session:
            ImportService(session).commit([tx], file_hash=file_hash)

    with _db(fresh_engine) as session:
        assert ImportLogRepository(session).has_successful_import(file_hash) is False


# ── Idempotência — ciclo completo com estado commitado ───────────────────────────

def test_segundo_import_mesmo_hash_bloqueado_apos_sucesso(fresh_engine) -> None:
    """Após importação bem-sucedida, o mesmo hash deve bloquear nova tentativa."""
    _setup_qp_asset(fresh_engine, ticker="ITSA4", qty="100", price="10.00")
    file_hash = "hash-idempotencia-completo"
    tx = _make_tx("ITSA4", TransactionType.BUY, date(2024, 2, 1), "500.00", qty="50", price="10.00")

    # Primeira importação: sucesso → audit log criado
    with _db(fresh_engine) as session:
        result = ImportService(session).commit([tx], file_hash=file_hash)
    assert result.valid_rows == 1

    # Segunda tentativa: validate com mesmo hash deve retornar is_duplicate=True
    with _db(fresh_engine) as session:
        result2 = ImportService(session).validate([tx], file_hash=file_hash)

    assert result2.is_duplicate is True
    assert result2.error_rows == 1
    assert "já foi importado" in result2.rows[0].message


def test_reimportacao_apos_falha_e_permitida_e_depois_bloqueada(fresh_engine) -> None:
    """Ciclo completo: falha → retry liberado → sucesso → nova tentativa bloqueada."""
    _setup_qp_asset(fresh_engine, ticker="ABEV3", qty="100", price="15.00")
    file_hash = "hash-retry-completo"
    tx_invalido = _make_tx("ABEV3", TransactionType.SELL, date(2024, 2, 1), "99000.00", qty="9999", price="15.00")
    tx_valido   = _make_tx("ABEV3", TransactionType.BUY,  date(2024, 2, 1), "750.00",   qty="50",   price="15.00")

    # Primeira tentativa: falha
    with pytest.raises(ValueError):
        with _db(fresh_engine) as session:
            ImportService(session).commit([tx_invalido], file_hash=file_hash)

    # Hash ainda não está no log → validate não bloqueia
    with _db(fresh_engine) as session:
        result = ImportService(session).validate([tx_valido], file_hash=file_hash)
    assert result.is_duplicate is False

    # Segunda tentativa: sucesso
    with _db(fresh_engine) as session:
        ImportService(session).commit([tx_valido], file_hash=file_hash)

    # Terceira tentativa: agora deve ser bloqueada
    with _db(fresh_engine) as session:
        result3 = ImportService(session).validate([tx_valido], file_hash=file_hash)
    assert result3.is_duplicate is True


def test_hashes_diferentes_importacoes_independentes(fresh_engine) -> None:
    """Dois arquivos com hashes distintos não interferem entre si."""
    _setup_qp_asset(fresh_engine, ticker="WEGE3", qty="100", price="40.00")
    tx1 = _make_tx("WEGE3", TransactionType.BUY, date(2024, 2, 1), "2000.00", qty="50", price="40.00", row=2)
    tx2 = _make_tx("WEGE3", TransactionType.BUY, date(2024, 3, 1), "2000.00", qty="50", price="40.00", row=3)

    with _db(fresh_engine) as session:
        ImportService(session).commit([tx1], file_hash="hash-arquivo-A")

    with _db(fresh_engine) as session:
        result = ImportService(session).validate([tx2], file_hash="hash-arquivo-B")

    assert result.is_duplicate is False
    assert result.error_rows == 0


# ── Snapshot transacional ────────────────────────────────────────────────────────

def test_snapshot_nao_criado_se_import_falhar(fresh_engine) -> None:
    """Se o import falha, o snapshot NÃO deve ser criado."""
    _setup_qp_asset(fresh_engine, ticker="MULT3", qty="100", price="25.00")
    tx_invalido = _make_tx("MULT3", TransactionType.SELL, date(2024, 3, 1), "99000.00", qty="999", price="25.00")

    with pytest.raises(ValueError):
        with _db(fresh_engine) as session:
            ImportService(session).commit([tx_invalido])
            SnapshotService(session).ensure_snapshot_for_today()

    from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository
    with _db(fresh_engine) as session:
        snap = SnapshotRepository(session).get_latest()
    assert snap is None


def test_snapshot_criado_apenas_uma_vez_por_import(fresh_engine) -> None:
    """ensure_snapshot_for_today() dentro do mesmo with get_db() gera 1 snapshot.

    Usa ImportService.commit() para o INITIAL_BALANCE, que aciona
    TransactionService.register() e registra o preço automaticamente em asset_prices.
    """
    from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository

    # Cria o ativo (sem transações)
    with _db(fresh_engine) as session:
        AssetRepository(session).create(
            ticker="ELET3",
            name="Eletrobras",
            asset_class=AssetClass.EQUITY,
            income_type=IncomeType.VARIABLE,
            tracking_type=AssetTrackingType.QUANTITY_PRICE,
        )

    # INITIAL_BALANCE via ImportService → TransactionService auto-registra o preço
    initial = _make_tx("ELET3", TransactionType.INITIAL_BALANCE, date(2024, 1, 2), "4500.00", qty="100", price="45.00")
    with _db(fresh_engine) as session:
        ImportService(session).commit([initial])

    # BUY + snapshot no mesmo contexto transacional
    tx = _make_tx("ELET3", TransactionType.BUY, date(2024, 2, 1), "450.00", qty="10", price="45.00")
    with _db(fresh_engine) as session:
        ImportService(session).commit([tx])
        SnapshotService(session).ensure_snapshot_for_today()

    with _db(fresh_engine) as session:
        snap = SnapshotRepository(session).get_latest()
        assert snap is not None
        # (100 inicial + 10 BUY) × R$ 45,00 = R$ 4.950,00
        assert snap.total_value == Decimal("4950.00")


# ── Hash e encoding ───────────────────────────────────────────────────────────────

def test_hash_sha256_deterministico() -> None:
    """O mesmo conteúdo sempre produz exatamente o mesmo hash."""
    content = b"ticker,tipo,data,valor_total\nVALE3,COMPRA,2024-01-15,1000.00\n"
    h1 = compute_file_hash(content)
    h2 = compute_file_hash(content)

    assert h1 == h2
    assert h1 == hashlib.sha256(content).hexdigest()
    assert len(h1) == 64  # SHA256 = 64 hex chars


def test_encoding_diferente_gera_hash_diferente() -> None:
    """Mesmo texto em UTF-8 e Latin-1 gera bytes diferentes → hashes diferentes."""
    texto_com_acento = "VALE3,COMPRA,2024-01-15,ação"
    bytes_utf8   = texto_com_acento.encode("utf-8")
    bytes_latin1 = texto_com_acento.encode("latin-1")

    assert bytes_utf8 != bytes_latin1
    assert compute_file_hash(bytes_utf8) != compute_file_hash(bytes_latin1)


def test_ascii_puro_mesmo_hash_em_qualquer_encoding() -> None:
    """Texto ASCII puro tem bytes idênticos em UTF-8 e Latin-1 — mesmo hash."""
    texto_ascii = "VALE3,COMPRA,2024-01-15,1000.00"
    assert compute_file_hash(texto_ascii.encode("utf-8")) == compute_file_hash(texto_ascii.encode("latin-1"))


# ── Parser com encoding real ──────────────────────────────────────────────────────

def test_parse_csv_encoding_latin1_funciona() -> None:
    """Arquivo CSV codificado em Latin-1 com caractere especial é parseado corretamente."""
    header  = "ticker,tipo,data,valor_total,quantidade,preco_unitario,taxas,notas,novo_valor_posicao\n"
    row     = "VALE3,COMPRA,2024-01-15,6550.00,100,65.50,,Compra de ação,\n"
    content = (header + row).encode("latin-1")

    txs, errors = parse_csv(content, encoding="latin-1")

    assert errors == []
    assert len(txs) == 1
    assert txs[0].ticker == "VALE3"


def test_parse_csv_encoding_errado_retorna_erro_controlado() -> None:
    """Arquivo Latin-1 lido como UTF-8 deve retornar erro de decodificação, não exceção."""
    texto_com_acento = "VALE3,COMPRA,2024-01-15,ação"
    content_latin1   = texto_com_acento.encode("latin-1")

    # Tenta ler como UTF-8 → erro esperado
    txs, errors = parse_csv(content_latin1, encoding="utf-8")

    assert txs == []
    assert len(errors) > 0


# ── Fluxo completo end-to-end ─────────────────────────────────────────────────────

def test_fluxo_completo_parse_validate_commit(fresh_engine) -> None:
    """Fluxo de ponta a ponta: bytes CSV → parse → validate → commit → snapshot."""
    _setup_qp_asset(fresh_engine, ticker="BBSE3", qty="50", price="30.00")

    csv_bytes = (
        "ticker,tipo,data,valor_total,quantidade,preco_unitario,taxas,notas,novo_valor_posicao\n"
        "BBSE3,COMPRA,2024-02-01,1500.00,50,30.00,,,\n"
    ).encode("utf-8")

    file_hash = compute_file_hash(csv_bytes)
    txs, errors = parse_csv(csv_bytes)
    assert errors == []

    with _db(fresh_engine) as session:
        preview = ImportService(session).validate(txs, file_hash=file_hash)
    assert preview.error_rows == 0
    assert preview.is_duplicate is False

    with _db(fresh_engine) as session:
        result = ImportService(session).commit(txs, file_hash=file_hash, file_name="teste.csv")
        SnapshotService(session).ensure_snapshot_for_today()

    assert result.valid_rows == 1

    # Audit log criado com nome do arquivo
    with _db(fresh_engine) as session:
        log_repo = ImportLogRepository(session)
        assert log_repo.has_successful_import(file_hash) is True
