from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import TransactionType
from consultor_investimentos.database.models import Asset
from consultor_investimentos.repositories.contribution_repository import ContributionRepository

_DATE = date(2024, 1, 2)


def test_create_initial_balance_quantity_price(session: Session, asset_qp: Asset) -> None:
    repo = ContributionRepository(session)
    tx = repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=_DATE,
        total_amount=Decimal("4960.00"),
        quantity=Decimal("80"),
        unit_price=Decimal("62.00"),
    )

    assert tx.id is not None
    assert tx.transaction_type == TransactionType.INITIAL_BALANCE.value
    assert tx.quantity == Decimal("80")
    assert tx.unit_price == Decimal("62.00")
    assert tx.total_amount == Decimal("4960.00")


def test_create_initial_balance_value_only(session: Session, asset_vo: Asset) -> None:
    repo = ContributionRepository(session)
    tx = repo.create(
        asset_id=asset_vo.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=_DATE,
        total_amount=Decimal("45000.00"),
    )

    assert tx.quantity is None
    assert tx.unit_price is None
    assert tx.total_amount == Decimal("45000.00")


def test_create_buy_quantity_price(session: Session, asset_qp: Asset) -> None:
    repo = ContributionRepository(session)
    tx = repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.BUY,
        date=_DATE,
        total_amount=Decimal("620.00"),
        quantity=Decimal("10"),
        unit_price=Decimal("62.00"),
    )

    assert tx.transaction_type == TransactionType.BUY.value


def test_create_buy_em_value_only_levanta_value_error(session: Session, asset_vo: Asset) -> None:
    repo = ContributionRepository(session)

    with pytest.raises(ValueError, match="não permitida"):
        repo.create(
            asset_id=asset_vo.id,
            transaction_type=TransactionType.BUY,
            date=_DATE,
            total_amount=Decimal("5000.00"),
            quantity=Decimal("100"),
            unit_price=Decimal("50.00"),
        )


def test_create_contribution_em_quantity_price_levanta_value_error(session: Session, asset_qp: Asset) -> None:
    repo = ContributionRepository(session)

    with pytest.raises(ValueError, match="não permitida"):
        repo.create(
            asset_id=asset_qp.id,
            transaction_type=TransactionType.CONTRIBUTION,
            date=_DATE,
            total_amount=Decimal("5000.00"),
        )


def test_create_buy_sem_quantity_levanta_value_error(session: Session, asset_qp: Asset) -> None:
    repo = ContributionRepository(session)

    with pytest.raises(ValueError, match="exige 'quantity' e 'unit_price'"):
        repo.create(
            asset_id=asset_qp.id,
            transaction_type=TransactionType.BUY,
            date=_DATE,
            total_amount=Decimal("620.00"),
        )


def test_create_total_amount_zero_levanta_value_error(session: Session, asset_qp: Asset) -> None:
    repo = ContributionRepository(session)

    with pytest.raises(ValueError, match="maior que zero"):
        repo.create(
            asset_id=asset_qp.id,
            transaction_type=TransactionType.BUY,
            date=_DATE,
            total_amount=Decimal("0"),
            quantity=Decimal("10"),
            unit_price=Decimal("0"),
        )


def test_create_contribution_value_only(session: Session, asset_vo: Asset) -> None:
    repo = ContributionRepository(session)
    tx = repo.create(
        asset_id=asset_vo.id,
        transaction_type=TransactionType.CONTRIBUTION,
        date=_DATE,
        total_amount=Decimal("5000.00"),
    )

    assert tx.transaction_type == TransactionType.CONTRIBUTION.value
    assert tx.quantity is None


def test_create_dividend_aceito_para_ambos_os_tipos(
    session: Session, asset_qp: Asset, asset_vo: Asset
) -> None:
    repo = ContributionRepository(session)
    tx_qp = repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.DIVIDEND,
        date=_DATE,
        total_amount=Decimal("120.00"),
    )
    tx_vo = repo.create(
        asset_id=asset_vo.id,
        transaction_type=TransactionType.DIVIDEND,
        date=_DATE,
        total_amount=Decimal("80.00"),
    )

    assert tx_qp.transaction_type == TransactionType.DIVIDEND.value
    assert tx_vo.transaction_type == TransactionType.DIVIDEND.value


def test_get_by_asset_retorna_ordenado_por_data(session: Session, asset_qp: Asset) -> None:
    repo = ContributionRepository(session)
    repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 1),
        total_amount=Decimal("4960.00"),
        quantity=Decimal("80"),
        unit_price=Decimal("62.00"),
    )
    repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.BUY,
        date=date(2024, 6, 1),
        total_amount=Decimal("650.00"),
        quantity=Decimal("10"),
        unit_price=Decimal("65.00"),
    )

    txs = repo.get_by_asset(asset_qp.id)

    assert len(txs) == 2
    assert txs[0].date < txs[1].date


def test_get_buys_and_initial_exclui_dividendos(session: Session, asset_qp: Asset) -> None:
    repo = ContributionRepository(session)
    repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=_DATE,
        total_amount=Decimal("4960.00"),
        quantity=Decimal("80"),
        unit_price=Decimal("62.00"),
    )
    repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.DIVIDEND,
        date=date(2024, 3, 1),
        total_amount=Decimal("120.00"),
    )

    result = repo.get_buys_and_initial(asset_qp.id)

    types = [tx.transaction_type for tx in result]
    assert TransactionType.INITIAL_BALANCE.value in types
    assert TransactionType.DIVIDEND.value not in types


def test_get_cost_basis_exclui_sell_e_dividend(session: Session, asset_qp: Asset) -> None:
    repo = ContributionRepository(session)
    repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2024, 1, 1),
        total_amount=Decimal("4960.00"),
        quantity=Decimal("80"),
        unit_price=Decimal("62.00"),
    )
    repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.SELL,
        date=date(2024, 6, 1),
        total_amount=Decimal("680.00"),
        quantity=Decimal("10"),
        unit_price=Decimal("68.00"),
    )
    repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.DIVIDEND,
        date=date(2024, 3, 1),
        total_amount=Decimal("120.00"),
    )

    result = repo.get_cost_basis_transactions(asset_qp.id)

    types = {tx.transaction_type for tx in result}
    assert TransactionType.INITIAL_BALANCE.value in types
    assert TransactionType.SELL.value not in types
    assert TransactionType.DIVIDEND.value not in types


def test_delete_remove_transacao_comum(session: Session, asset_qp: Asset) -> None:
    repo = ContributionRepository(session)
    repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=_DATE,
        total_amount=Decimal("4960.00"),
        quantity=Decimal("80"),
        unit_price=Decimal("62.00"),
    )
    buy = repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.BUY,
        date=date(2024, 6, 1),
        total_amount=Decimal("650.00"),
        quantity=Decimal("10"),
        unit_price=Decimal("65.00"),
    )

    repo.delete(buy.id)

    assert repo.get_by_id(buy.id) is None


def test_delete_initial_balance_levanta_value_error(session: Session, asset_qp: Asset) -> None:
    repo = ContributionRepository(session)
    tx = repo.create(
        asset_id=asset_qp.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=_DATE,
        total_amount=Decimal("4960.00"),
        quantity=Decimal("80"),
        unit_price=Decimal("62.00"),
    )

    with pytest.raises(ValueError, match="Saldo Inicial"):
        repo.delete(tx.id)


def test_delete_id_inexistente_levanta_value_error(session: Session) -> None:
    repo = ContributionRepository(session)

    with pytest.raises(ValueError, match="não encontrada"):
        repo.delete(9999)
