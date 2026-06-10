"""Hardening do sistema de importação — cenários adversariais e casos extremos."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType, TransactionType
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository
from consultor_investimentos.services.dto import ImportTransaction
from consultor_investimentos.services.import_service import ImportService
from consultor_investimentos.services.snapshot_service import SnapshotService


# ── Helpers ──────────────────────────────────────────────────────────────────────

def _make_tx(
    ticker: str,
    tx_type: TransactionType,
    tx_date: date,
    total: str,
    qty: str | None = None,
    price: str | None = None,
    row: int = 2,
    new_pos: str | None = None,
) -> ImportTransaction:
    return ImportTransaction(
        ticker=ticker,
        transaction_type=tx_type,
        tx_date=tx_date,
        total_amount=Decimal(total),
        quantity=Decimal(qty) if qty else None,
        unit_price=Decimal(price) if price else None,
        new_position_value=Decimal(new_pos) if new_pos else None,
        row_number=row,
    )


@pytest.fixture
def qp(session: Session):
    """Ativo QP com 100 cotas a R$ 50,00."""
    asset = AssetRepository(session).create(
        ticker="SANB11",
        name="Santander Brasil",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("5000.00"),
        quantity=Decimal("100"),
        unit_price=Decimal("50.00"),
    )
    return asset


@pytest.fixture
def qp2(session: Session):
    """Segundo ativo QP com 50 cotas a R$ 40,00."""
    asset = AssetRepository(session).create(
        ticker="TAEE11",
        name="Taesa",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("2000.00"),
        quantity=Decimal("50"),
        unit_price=Decimal("40.00"),
    )
    return asset


# ── Saldo exato (boundary) ────────────────────────────────────────────────────────

def test_sell_exatamente_igual_saldo_e_valido(session: Session, qp) -> None:
    """SELL de exatamente o saldo disponível deve ser aceito (condição: ≤, não <)."""
    svc = ImportService(session)
    tx = _make_tx("SANB11", TransactionType.SELL, date(2024, 3, 1), "5000.00", qty="100", price="50.00")
    result = svc.validate([tx])

    assert result.error_rows == 0
    assert result.rows[0].status == "ok"


def test_sell_um_acima_do_saldo_invalido(session: Session, qp) -> None:
    """SELL de saldo + 1 cota deve falhar com mensagem de saldo excedido."""
    svc = ImportService(session)
    tx = _make_tx("SANB11", TransactionType.SELL, date(2024, 3, 1), "5050.00", qty="101", price="50.00")
    result = svc.validate([tx])

    assert result.error_rows == 1
    assert "excede saldo" in result.rows[0].message


# ── Running qty progressiva ───────────────────────────────────────────────────────

def test_running_qty_decrementada_progressivamente(session: Session, qp) -> None:
    """Sequência de SELLs que esgota saldo gradualmente — último excede e falha."""
    svc = ImportService(session)
    # Saldo base: 100. BUY +50 = 150. SELL 50×3 = zera. SELL 1 extra → falha.
    txs = [
        _make_tx("SANB11", TransactionType.BUY,  date(2024, 2, 1), "2500.00", qty="50", price="50.00", row=2),
        _make_tx("SANB11", TransactionType.SELL, date(2024, 3, 1), "2500.00", qty="50", price="50.00", row=3),
        _make_tx("SANB11", TransactionType.SELL, date(2024, 4, 1), "2500.00", qty="50", price="50.00", row=4),
        _make_tx("SANB11", TransactionType.SELL, date(2024, 5, 1), "2500.00", qty="50", price="50.00", row=5),
        _make_tx("SANB11", TransactionType.SELL, date(2024, 6, 1),  "50.00",  qty="1",  price="50.00", row=6),
    ]
    result = svc.validate(txs)

    assert result.valid_rows == 4
    assert result.error_rows == 1
    last = next(r for r in result.rows if r.row_number == 6)
    assert last.status == "error"
    assert "excede saldo" in last.message


def test_running_qty_zerada_por_sell_total(session: Session, qp) -> None:
    """SELL que zera o saldo é válido; running_qty fica em 0."""
    svc = ImportService(session)
    sell_total = _make_tx("SANB11", TransactionType.SELL, date(2024, 3, 1), "5000.00", qty="100", price="50.00")
    result = svc.validate([sell_total])

    assert result.valid_rows == 1
    assert result.error_rows == 0


# ── Multi-ticker — independência de saldo ─────────────────────────────────────────

def test_dois_tickers_running_qty_independentes(session: Session, qp, qp2) -> None:
    """Erro de saldo em TAEE11 não deve contaminar a validação de SANB11."""
    svc = ImportService(session)
    txs = [
        # SANB11: saldo 100 + BUY 50 = 150. SELL 100 → OK (50 restantes).
        _make_tx("SANB11", TransactionType.BUY,  date(2024, 2, 1), "2500.00", qty="50",  price="50.00", row=2),
        _make_tx("SANB11", TransactionType.SELL, date(2024, 3, 1), "5000.00", qty="100", price="50.00", row=3),
        # TAEE11: saldo 50. SELL 100 → inválido.
        _make_tx("TAEE11", TransactionType.SELL, date(2024, 3, 2), "4000.00", qty="100", price="40.00", row=4),
    ]
    result = svc.validate(txs)

    sanb_rows = [r for r in result.rows if r.ticker == "SANB11"]
    taee_rows = [r for r in result.rows if r.ticker == "TAEE11"]

    assert all(r.status == "ok"    for r in sanb_rows)
    assert all(r.status == "error" for r in taee_rows)
    assert result.valid_rows == 2
    assert result.error_rows == 1


def test_operacoes_mesmo_ticker_datas_distintas_ordem_csv_irrelevante(session: Session, qp) -> None:
    """validate() ordena por data independente da ordem no CSV."""
    svc = ImportService(session)
    # No CSV: SELL (março) antes de BUY (fevereiro) — validate() deve corrigir.
    sell = _make_tx("SANB11", TransactionType.SELL, date(2024, 3, 1), "2500.00", qty="50", price="50.00", row=3)
    buy  = _make_tx("SANB11", TransactionType.BUY,  date(2024, 2, 1), "2500.00", qty="50", price="50.00", row=2)
    result = svc.validate([sell, buy])  # ordem invertida na lista

    # BUY (fev) é processado antes do SELL (mar): 100+50=150 >= 50 → válido
    assert result.error_rows == 0
    assert result.valid_rows == 2


# ── Integridade do commit ────────────────────────────────────────────────────────

def test_commit_n_linhas_persiste_exatamente_n_transacoes(session: Session, qp) -> None:
    """3 BUYs no batch → exatamente 3 novas transações além do INITIAL_BALANCE."""
    svc = ImportService(session)
    txs = [
        _make_tx("SANB11", TransactionType.BUY, date(2024, 2, 1), "1000.00", qty="20", price="50.00", row=2),
        _make_tx("SANB11", TransactionType.BUY, date(2024, 3, 1), "1000.00", qty="20", price="50.00", row=3),
        _make_tx("SANB11", TransactionType.BUY, date(2024, 4, 1), "1000.00", qty="20", price="50.00", row=4),
    ]
    result = svc.commit(txs)

    assert result.valid_rows == 3
    all_txs = ContributionRepository(session).get_by_asset(qp.id)
    assert len(all_txs) == 4  # INITIAL_BALANCE + 3 BUYs


def test_commit_lote_vazio_retorna_resultado_zerado(session: Session) -> None:
    """commit([]) deve retornar ImportResult vazio sem erros ou exceções."""
    result = ImportService(session).commit([])

    assert result.total_rows == 0
    assert result.valid_rows == 0
    assert result.error_rows == 0
    assert result.rows == []


def test_commit_registra_transacoes_em_ordem_cronologica(session: Session, qp) -> None:
    """As transações devem ser persistidas em ordem de data, independente da ordem no batch."""
    svc = ImportService(session)
    txs = [
        _make_tx("SANB11", TransactionType.BUY, date(2024, 4, 1), "1000.00", qty="10", price="100.00", row=4),
        _make_tx("SANB11", TransactionType.BUY, date(2024, 2, 1), "1000.00", qty="20", price="50.00",  row=2),
        _make_tx("SANB11", TransactionType.BUY, date(2024, 3, 1), "1000.00", qty="15", price="66.00",  row=3),
    ]
    svc.commit(txs)

    txs_db = ContributionRepository(session).get_by_asset(qp.id)
    # Após INITIAL_BALANCE, os 3 BUYs devem estar em ordem crescente de data
    buy_txs = [t for t in txs_db if TransactionType(t.transaction_type) == TransactionType.BUY]
    datas = [t.date for t in buy_txs]
    assert datas == sorted(datas)


# ── validate() é read-only ───────────────────────────────────────────────────────

def test_validate_nao_escreve_no_banco(session: Session, qp) -> None:
    """validate() com transações válidas não deve criar nada no banco."""
    contrib_repo = ContributionRepository(session)
    count_antes = len(contrib_repo.get_by_asset(qp.id))

    svc = ImportService(session)
    tx = _make_tx("SANB11", TransactionType.BUY, date(2024, 3, 1), "1000.00", qty="20", price="50.00")
    svc.validate([tx])

    count_depois = len(contrib_repo.get_by_asset(qp.id))
    assert count_depois == count_antes


def test_validate_com_erro_nao_escreve_no_banco(session: Session, qp) -> None:
    """validate() com linha inválida (ticker inexistente) não deve tocar o banco."""
    contrib_repo = ContributionRepository(session)
    count_antes = len(contrib_repo.get_by_asset(qp.id))

    svc = ImportService(session)
    tx = _make_tx("NAOEXISTE", TransactionType.BUY, date(2024, 3, 1), "1000.00", qty="10", price="100.00")
    result = svc.validate([tx])

    assert result.error_rows == 1
    assert len(contrib_repo.get_by_asset(qp.id)) == count_antes


# ── Snapshot ────────────────────────────────────────────────────────────────────

def test_snapshot_reflete_valor_apos_commit(session: Session) -> None:
    """Snapshot gerado após commit deve ter total_value igual ao valor da posição."""
    asset = AssetRepository(session).create(
        ticker="ENGI11",
        name="Engie Brasil",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    # INITIAL_BALANCE registra o preço automaticamente via TransactionService
    svc = ImportService(session)
    tx = _make_tx("ENGI11", TransactionType.INITIAL_BALANCE, date(2024, 1, 2), "8000.00", qty="100", price="80.00")
    svc.commit([tx])

    SnapshotService(session).ensure_snapshot_for_today()

    snap = SnapshotRepository(session).get_latest()
    assert snap is not None
    assert snap.total_value == Decimal("8000.00")


def test_snapshot_idempotente_nao_duplica(session: Session) -> None:
    """ensure_snapshot_for_today() chamado N vezes não cria duplicatas."""
    asset = AssetRepository(session).create(
        ticker="ENGI11X",
        name="Engie X",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    svc = ImportService(session)
    tx = _make_tx("ENGI11X", TransactionType.INITIAL_BALANCE, date(2024, 1, 2), "5000.00", qty="100", price="50.00")
    svc.commit([tx])

    snap_svc = SnapshotService(session)
    snap_svc.ensure_snapshot_for_today()
    snap_svc.ensure_snapshot_for_today()  # segunda chamada: upsert, não duplica

    snap = SnapshotRepository(session).get_latest()
    assert snap is not None
    assert snap.total_value == Decimal("5000.00")


def test_snapshot_nao_criado_sem_preco(session: Session) -> None:
    """Sem preço cadastrado, ensure_snapshot_for_today() retorna sem criar snapshot."""
    AssetRepository(session).create(
        ticker="SEM-PRECO",
        name="Ativo sem preço",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    # Sem preço (sem INITIAL_BALANCE e sem AssetPrice manual)
    SnapshotService(session).ensure_snapshot_for_today()

    snap = SnapshotRepository(session).get_latest()
    assert snap is None


# ── Idempotência — ciclo falha → retry ───────────────────────────────────────────

def test_idempotencia_falha_nao_bloqueia_reimportacao(session: Session, qp) -> None:
    """Se commit() falha, não gera audit log — mesmo hash permite nova tentativa."""
    from consultor_investimentos.repositories.import_log_repository import ImportLogRepository

    svc = ImportService(session)
    file_hash = "hash-retry-unit"

    # Primeira tentativa falha (SELL sem saldo)
    tx_invalido = _make_tx("SANB11", TransactionType.SELL, date(2024, 3, 1), "50000.00", qty="999", price="50.00")
    with pytest.raises(ValueError):
        svc.commit([tx_invalido], file_hash=file_hash)

    # Nenhum audit log de sucesso foi criado
    assert ImportLogRepository(session).has_successful_import(file_hash) is False

    # Validate com mesmo hash não deve bloquear (nenhum sucesso prévio)
    tx_valido = _make_tx("SANB11", TransactionType.BUY, date(2024, 3, 1), "1000.00", qty="20", price="50.00")
    result = svc.validate([tx_valido], file_hash=file_hash)
    assert result.is_duplicate is False
