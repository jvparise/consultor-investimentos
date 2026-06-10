"""Testes do ImportService."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType, TransactionType
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.holding_repository import HoldingRepository
from consultor_investimentos.repositories.import_log_repository import ImportLogRepository
from consultor_investimentos.services.dto import ImportTransaction
from consultor_investimentos.services.import_service import ImportService


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def qp_asset(session: Session):
    """Ativo QUANTITY_PRICE com INITIAL_BALANCE (80 cotas a R$ 62,00)."""
    repo = AssetRepository(session)
    asset = repo.create(
        ticker="ITUB4",
        name="Itaú Unibanco",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("4960.00"),
        quantity=Decimal("80"),
        unit_price=Decimal("62.00"),
    )
    return asset


@pytest.fixture
def vo_asset(session: Session):
    """Ativo VALUE_ONLY sem INITIAL_BALANCE."""
    repo = AssetRepository(session)
    return repo.create(
        ticker="LCI-BTG",
        name="LCI BTG",
        asset_class=AssetClass.FIXED_INCOME,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )


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


# ── validate() ──────────────────────────────────────────────────────────────────

def test_validate_ticker_nao_encontrado(session: Session) -> None:
    svc = ImportService(session)
    tx = _make_tx("INEXISTENTE", TransactionType.BUY, date(2024, 3, 1), "1000.00", qty="10", price="100.00")
    result = svc.validate([tx])

    assert result.error_rows == 1
    assert "não encontrado" in result.rows[0].message


def test_validate_tipo_nao_permitido_qp(session: Session, qp_asset) -> None:
    """CONTRIBUTION não é permitido para QUANTITY_PRICE."""
    svc = ImportService(session)
    tx = _make_tx("ITUB4", TransactionType.CONTRIBUTION, date(2024, 3, 1), "1000.00")
    result = svc.validate([tx])

    assert result.error_rows == 1
    assert "não permitido" in result.rows[0].message


def test_validate_tipo_nao_permitido_vo(session: Session, vo_asset) -> None:
    """BUY não é permitido para VALUE_ONLY."""
    svc = ImportService(session)
    tx = _make_tx("LCI-BTG", TransactionType.BUY, date(2024, 3, 1), "1000.00", qty="1", price="1000.00")
    result = svc.validate([tx])

    assert result.error_rows == 1
    assert "não permitido" in result.rows[0].message


def test_validate_sell_excede_qty(session: Session, qp_asset) -> None:
    """SELL de 200 unidades com apenas 80 disponíveis."""
    svc = ImportService(session)
    tx = _make_tx("ITUB4", TransactionType.SELL, date(2024, 3, 1), "12000.00", qty="200", price="60.00")
    result = svc.validate([tx])

    assert result.error_rows == 1
    assert "excede saldo" in result.rows[0].message


def test_validate_sell_valido_apos_buy_running_qty(session: Session, qp_asset) -> None:
    """BUY + SELL dentro do mesmo lote: running_qty atualiza entre as linhas."""
    svc = ImportService(session)
    buy = _make_tx("ITUB4", TransactionType.BUY, date(2024, 2, 1), "5000.00", qty="100", price="50.00", row=2)
    # Após BUY: 80 (existente) + 100 = 180. SELL de 150 é válido.
    sell = _make_tx("ITUB4", TransactionType.SELL, date(2024, 3, 1), "9000.00", qty="150", price="60.00", row=3)
    result = svc.validate([buy, sell])

    assert result.error_rows == 0
    assert result.valid_rows == 2


def test_validate_sell_invalido_sem_saldo_inicial(session: Session) -> None:
    """SELL sem nenhuma compra anterior no batch — qty é 0."""
    repo = AssetRepository(session)
    asset = repo.create(
        ticker="BBAS3",
        name="Banco do Brasil",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    svc = ImportService(session)
    tx = _make_tx("BBAS3", TransactionType.SELL, date(2024, 3, 1), "1000.00", qty="10", price="100.00")
    result = svc.validate([tx])

    assert result.error_rows == 1


def test_validate_ordem_cronologica(session: Session, qp_asset) -> None:
    """Transações fora de ordem são reordenadas antes da validação."""
    svc = ImportService(session)
    # SELL antes do BUY na lista, mas datas fazem BUY ser processado primeiro
    sell = _make_tx("ITUB4", TransactionType.SELL, date(2024, 3, 1), "3000.00", qty="50", price="60.00", row=3)
    buy = _make_tx("ITUB4", TransactionType.BUY, date(2024, 2, 1), "5000.00", qty="100", price="50.00", row=2)
    result = svc.validate([sell, buy])

    # BUY (fev) processado antes do SELL (mar): 80+100=180 >= 50 → válido
    assert result.error_rows == 0


# ── commit() ────────────────────────────────────────────────────────────────────

def test_commit_persiste_transacao(session: Session, qp_asset) -> None:
    svc = ImportService(session)
    tx = _make_tx("ITUB4", TransactionType.BUY, date(2024, 3, 1), "3000.00", qty="50", price="60.00")
    result = svc.commit([tx])

    assert result.error_rows == 0
    assert result.valid_rows == 1

    txs_db = ContributionRepository(session).get_by_asset(qp_asset.id)
    # INITIAL_BALANCE + BUY = 2 transações
    assert len(txs_db) == 2
    types = {TransactionType(t.transaction_type) for t in txs_db}
    assert TransactionType.BUY in types


def test_commit_propaga_excecao_em_sell_invalido(session: Session, qp_asset) -> None:
    """commit() deve propagar ValueError quando SELL excede o saldo disponível."""
    svc = ImportService(session)
    # 80 disponíveis, tentando vender 200
    tx = _make_tx("ITUB4", TransactionType.SELL, date(2024, 3, 1), "12000.00", qty="200", price="60.00")

    with pytest.raises(ValueError, match="excede"):
        svc.commit([tx])


def test_commit_preco_auto_registrado_saldo_inicial(session: Session) -> None:
    """Após commit de INITIAL_BALANCE em QP, price deve estar em asset_prices."""
    repo = AssetRepository(session)
    asset = repo.create(
        ticker="PETR4",
        name="Petrobras",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    svc = ImportService(session)
    tx = _make_tx(
        "PETR4",
        TransactionType.INITIAL_BALANCE,
        date(2024, 1, 5),
        "4000.00",
        qty="100",
        price="40.00",
    )
    svc.commit([tx])

    price = HoldingRepository(session).get_on_date(asset.id, date(2024, 1, 5))
    assert price is not None
    assert price.price == Decimal("40.00")


def test_commit_vo_preco_registrado_apos_saldo_inicial(session: Session) -> None:
    """INITIAL_BALANCE em VALUE_ONLY deve registrar total_amount como preço."""
    repo = AssetRepository(session)
    asset = repo.create(
        ticker="CDB-BB",
        name="CDB Banco do Brasil",
        asset_class=AssetClass.FIXED_INCOME,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )
    svc = ImportService(session)
    tx = _make_tx("CDB-BB", TransactionType.INITIAL_BALANCE, date(2024, 1, 5), "30000.00")
    svc.commit([tx])

    price = HoldingRepository(session).get_on_date(asset.id, date(2024, 1, 5))
    assert price is not None
    assert price.price == Decimal("30000.00")


# ── Idempotência ─────────────────────────────────────────────────────────────────

def test_validate_bloqueia_arquivo_duplicado(session: Session, qp_asset) -> None:
    """validate() retorna is_duplicate=True se hash já foi importado com sucesso."""
    svc = ImportService(session)
    tx = _make_tx("ITUB4", TransactionType.BUY, date(2024, 3, 1), "3000.00", qty="50", price="60.00")

    # Primeiro commit registra o hash
    svc.commit([tx], file_hash="abc123")

    # Segunda chamada de validate com mesmo hash deve detectar duplicata
    result = svc.validate([tx], file_hash="abc123")

    assert result.is_duplicate is True
    assert result.error_rows == 1
    assert result.valid_rows == 0
    assert "já foi importado" in result.rows[0].message


def test_validate_hash_diferente_nao_bloqueia(session: Session, qp_asset) -> None:
    """Hashes diferentes são tratados como importações distintas."""
    svc = ImportService(session)
    tx = _make_tx("ITUB4", TransactionType.BUY, date(2024, 3, 1), "3000.00", qty="50", price="60.00")
    svc.commit([tx], file_hash="hash-A")

    tx2 = _make_tx("ITUB4", TransactionType.BUY, date(2024, 4, 1), "2000.00", qty="30", price="66.00")
    result = svc.validate([tx2], file_hash="hash-B")

    assert result.is_duplicate is False
    assert result.error_rows == 0


def test_validate_sem_hash_nao_verifica_duplicata(session: Session, qp_asset) -> None:
    """validate() sem file_hash ignora a verificação de idempotência."""
    svc = ImportService(session)
    tx = _make_tx("ITUB4", TransactionType.BUY, date(2024, 3, 1), "3000.00", qty="50", price="60.00")
    svc.commit([tx], file_hash="xyz")

    # Sem hash: validação financeira normal, não detecta duplicata
    result = svc.validate([tx])
    assert result.is_duplicate is False


# ── Audit log ───────────────────────────────────────────────────────────────────

def test_commit_com_hash_cria_audit_log(session: Session, qp_asset) -> None:
    """commit() com file_hash deve criar registro em import_logs."""
    svc = ImportService(session)
    tx = _make_tx("ITUB4", TransactionType.BUY, date(2024, 3, 1), "3000.00", qty="50", price="60.00")
    svc.commit([tx], file_hash="audit-hash-001", file_name="meu_arquivo.csv")

    log_repo = ImportLogRepository(session)
    assert log_repo.has_successful_import("audit-hash-001") is True


def test_commit_sem_hash_nao_cria_audit_log(session: Session, qp_asset) -> None:
    """commit() sem file_hash não deve criar entrada em import_logs."""
    svc = ImportService(session)
    tx = _make_tx("ITUB4", TransactionType.BUY, date(2024, 3, 1), "3000.00", qty="50", price="60.00")
    svc.commit([tx])

    log_repo = ImportLogRepository(session)
    assert log_repo.has_successful_import("qualquer-hash") is False


def test_commit_falha_nao_cria_audit_log(session: Session, qp_asset) -> None:
    """Se commit() falha (exceção), audit log NÃO deve ter sido persistido."""
    svc = ImportService(session)
    # 80 disponíveis, tentando vender 200 — vai lançar exceção
    tx = _make_tx("ITUB4", TransactionType.SELL, date(2024, 3, 1), "12000.00", qty="200", price="60.00")

    with pytest.raises(ValueError):
        svc.commit([tx], file_hash="hash-falha")

    log_repo = ImportLogRepository(session)
    assert log_repo.has_successful_import("hash-falha") is False
