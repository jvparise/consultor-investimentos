"""Testes do TransactionService."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType, TransactionType
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.holding_repository import HoldingRepository
from consultor_investimentos.services.dto import TransactionDTO
from consultor_investimentos.services.transaction_service import TransactionService


@pytest.fixture
def vale3(session: Session):
    asset = AssetRepository(session).create(
        ticker="VALE3T",
        name="Vale S.A.",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("6200.00"),
        quantity=Decimal("100"),
        unit_price=Decimal("62.00"),
    )
    return asset


@pytest.fixture
def cdb(session: Session):
    asset = AssetRepository(session).create(
        ticker="CDB-TX",
        name="CDB Teste",
        asset_class=AssetClass.FIXED_INCOME,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 2),
        total_amount=Decimal("50000.00"),
    )
    return asset


def test_register_compra_quantity_price(session: Session, vale3) -> None:
    svc = TransactionService(session)
    svc.register(
        asset_id=vale3.id,
        transaction_type=TransactionType.BUY,
        tx_date=date(2024, 3, 1),
        total_amount=Decimal("3500.00"),
        quantity=Decimal("50"),
        unit_price=Decimal("70.00"),
    )

    txs = svc.list_by_asset(vale3.id)
    assert len(txs) == 2
    assert txs[0].transaction_type == TransactionType.BUY.value


def test_register_aporte_value_only_atualiza_preco(session: Session, cdb) -> None:
    svc = TransactionService(session)
    svc.register(
        asset_id=cdb.id,
        transaction_type=TransactionType.CONTRIBUTION,
        tx_date=date(2024, 6, 1),
        total_amount=Decimal("5000.00"),
        new_position_value=Decimal("56000.00"),
    )

    holding_repo = HoldingRepository(session)
    price = holding_repo.get_on_date(cdb.id, date(2024, 6, 1))
    assert price is not None
    assert price.price == Decimal("56000.00")


def test_register_sem_new_position_value_nao_cria_preco(session: Session, cdb) -> None:
    svc = TransactionService(session)
    svc.register(
        asset_id=cdb.id,
        transaction_type=TransactionType.CONTRIBUTION,
        tx_date=date(2024, 7, 1),
        total_amount=Decimal("3000.00"),
    )

    holding_repo = HoldingRepository(session)
    price = holding_repo.get_on_date(cdb.id, date(2024, 7, 1))
    assert price is None


def test_delete_transacao_comum(session: Session, vale3) -> None:
    contrib = ContributionRepository(session)
    tx = contrib.create(
        asset_id=vale3.id,
        transaction_type=TransactionType.BUY,
        date=date(2024, 4, 1),
        total_amount=Decimal("700.00"),
        quantity=Decimal("10"),
        unit_price=Decimal("70.00"),
    )

    svc = TransactionService(session)
    svc.delete(tx.id)

    txs = svc.list_by_asset(vale3.id)
    assert all(t.id != tx.id for t in txs)


def test_delete_initial_balance_levanta_value_error(session: Session, vale3) -> None:
    txs = ContributionRepository(session).get_by_asset(vale3.id)
    initial = next(t for t in txs if t.transaction_type == TransactionType.INITIAL_BALANCE.value)

    svc = TransactionService(session)
    with pytest.raises(ValueError):
        svc.delete(initial.id)


def test_list_by_asset_retorna_dtos(session: Session, vale3) -> None:
    svc = TransactionService(session)
    txs = svc.list_by_asset(vale3.id)

    assert all(isinstance(t, TransactionDTO) for t in txs)
    assert all(t.asset_ticker == "VALE3T" for t in txs)


def test_list_by_asset_can_delete_false_para_initial_balance(session: Session, vale3) -> None:
    svc = TransactionService(session)
    txs = svc.list_by_asset(vale3.id)

    initial = next(t for t in txs if t.transaction_type == TransactionType.INITIAL_BALANCE.value)
    assert initial.can_delete is False


def test_list_by_asset_mais_recentes_primeiro(session: Session, vale3) -> None:
    contrib = ContributionRepository(session)
    contrib.create(
        asset_id=vale3.id,
        transaction_type=TransactionType.BUY,
        date=date(2024, 6, 1),
        total_amount=Decimal("700.00"),
        quantity=Decimal("10"),
        unit_price=Decimal("70.00"),
    )

    svc = TransactionService(session)
    txs = svc.list_by_asset(vale3.id)

    dates = [t.date for t in txs]
    assert dates == sorted(dates, reverse=True)


def test_list_recent_retorna_dtos_periodo(session: Session, vale3) -> None:
    svc = TransactionService(session)
    txs = svc.list_recent(days=365)

    assert all(isinstance(t, TransactionDTO) for t in txs)


def test_list_by_asset_retorna_vazio_para_ativo_inexistente(session: Session) -> None:
    svc = TransactionService(session)
    txs = svc.list_by_asset(99999)
    assert txs == []


def test_initial_balance_quantity_price_auto_registra_preco(session: Session) -> None:
    asset = AssetRepository(session).create(
        ticker="AUTO3",
        name="Ativo auto-price QP",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )

    svc = TransactionService(session)
    svc.register(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        tx_date=date(2024, 1, 2),
        total_amount=Decimal("6200.00"),
        quantity=Decimal("100"),
        unit_price=Decimal("62.00"),
    )

    price = HoldingRepository(session).get_latest(asset.id)
    assert price is not None
    assert price.price == Decimal("62.00")
    assert price.price_date == date(2024, 1, 2)


def test_initial_balance_value_only_auto_registra_total_amount(session: Session) -> None:
    asset = AssetRepository(session).create(
        ticker="AUTO-VO",
        name="Ativo auto-price VO",
        asset_class=AssetClass.FIXED_INCOME,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )

    svc = TransactionService(session)
    svc.register(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        tx_date=date(2024, 1, 2),
        total_amount=Decimal("50000.00"),
    )

    price = HoldingRepository(session).get_latest(asset.id)
    assert price is not None
    assert price.price == Decimal("50000.00")
    assert price.price_date == date(2024, 1, 2)


def test_initial_balance_value_only_usa_new_position_value_se_informado(session: Session) -> None:
    asset = AssetRepository(session).create(
        ticker="AUTO-NP",
        name="Ativo auto-price VO com new_position_value",
        asset_class=AssetClass.FIXED_INCOME,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )

    svc = TransactionService(session)
    svc.register(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        tx_date=date(2024, 1, 2),
        total_amount=Decimal("5000.00"),
        new_position_value=Decimal("55000.00"),
    )

    price = HoldingRepository(session).get_latest(asset.id)
    assert price is not None
    assert price.price == Decimal("55000.00")


def test_sell_acima_da_quantidade_levanta_value_error(session: Session, vale3) -> None:
    """Vender mais do que o saldo disponível deve levantar ValueError no Service (P5)."""
    svc = TransactionService(session)
    with pytest.raises(ValueError, match="excede o saldo disponível"):
        svc.register(
            asset_id=vale3.id,
            transaction_type=TransactionType.SELL,
            tx_date=date(2024, 6, 1),
            total_amount=Decimal("10000.00"),
            quantity=Decimal("200"),
            unit_price=Decimal("50.00"),
        )


def test_sell_exato_quantidade_disponivel_nao_levanta_erro(session: Session, vale3) -> None:
    """Vender exatamente o saldo disponível deve ser permitido."""
    svc = TransactionService(session)
    svc.register(
        asset_id=vale3.id,
        transaction_type=TransactionType.SELL,
        tx_date=date(2024, 6, 1),
        total_amount=Decimal("6200.00"),
        quantity=Decimal("100"),
        unit_price=Decimal("62.00"),
    )
    txs = svc.list_by_asset(vale3.id)
    sell_txs = [t for t in txs if t.transaction_type == TransactionType.SELL.value]
    assert len(sell_txs) == 1


def test_sell_parcial_reduz_quantidade_disponivel(session: Session, vale3) -> None:
    """Vender parte das cotas: validação aceita, segunda venda verifica saldo restante."""
    svc = TransactionService(session)
    svc.register(
        asset_id=vale3.id,
        transaction_type=TransactionType.SELL,
        tx_date=date(2024, 6, 1),
        total_amount=Decimal("3100.00"),
        quantity=Decimal("50"),
        unit_price=Decimal("62.00"),
    )
    with pytest.raises(ValueError, match="excede o saldo disponível"):
        svc.register(
            asset_id=vale3.id,
            transaction_type=TransactionType.SELL,
            tx_date=date(2024, 6, 2),
            total_amount=Decimal("3100.00"),
            quantity=Decimal("60"),
            unit_price=Decimal("62.00"),
        )
