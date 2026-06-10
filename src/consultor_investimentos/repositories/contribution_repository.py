from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_investimentos.config import (
    ALLOWED_TRANSACTION_TYPES,
    AssetTrackingType,
    TransactionType,
)
from consultor_investimentos.database.models import Asset, Transaction

_COST_BASIS_TYPES = [
    TransactionType.INITIAL_BALANCE.value,
    TransactionType.BUY.value,
    TransactionType.CONTRIBUTION.value,
]

_REQUIRES_QTY_AND_PRICE = {TransactionType.BUY, TransactionType.SELL}


class ContributionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, id: int) -> Transaction | None:
        return self._session.get(Transaction, id)

    def get_by_asset(self, asset_id: int) -> list[Transaction]:
        return list(
            self._session.execute(
                select(Transaction)
                .where(Transaction.asset_id == asset_id)
                .order_by(Transaction.date.asc())
            ).scalars().all()
        )

    def get_buys_and_initial(self, asset_id: int) -> list[Transaction]:
        """Retorna INITIAL_BALANCE e BUY para cálculo de preço médio ponderado."""
        types = [TransactionType.INITIAL_BALANCE.value, TransactionType.BUY.value]
        return list(
            self._session.execute(
                select(Transaction)
                .where(
                    Transaction.asset_id == asset_id,
                    Transaction.transaction_type.in_(types),
                )
                .order_by(Transaction.date.asc())
            ).scalars().all()
        )

    def get_cost_basis_transactions(self, asset_id: int) -> list[Transaction]:
        """Retorna transações que compõem o custo de aquisição da posição.

        Inclui INITIAL_BALANCE, BUY e CONTRIBUTION.
        Exclui SELL, WITHDRAWAL, DIVIDEND e INTEREST.
        Usado para calcular total_invested no cálculo de rentabilidade.
        """
        return list(
            self._session.execute(
                select(Transaction)
                .where(
                    Transaction.asset_id == asset_id,
                    Transaction.transaction_type.in_(_COST_BASIS_TYPES),
                )
                .order_by(Transaction.date.asc())
            ).scalars().all()
        )

    def get_by_date_range(
        self,
        start: date,
        end: date,
        asset_id: int | None = None,
    ) -> list[Transaction]:
        stmt = select(Transaction).where(
            Transaction.date >= start,
            Transaction.date <= end,
        )
        if asset_id is not None:
            stmt = stmt.where(Transaction.asset_id == asset_id)
        return list(
            self._session.execute(stmt.order_by(Transaction.date.asc())).scalars().all()
        )

    def create(
        self,
        asset_id: int,
        transaction_type: TransactionType,
        date: date,
        total_amount: Decimal,
        quantity: Decimal | None = None,
        unit_price: Decimal | None = None,
        fees: Decimal = Decimal("0"),
        notes: str | None = None,
    ) -> Transaction:
        asset = self._session.get(Asset, asset_id)
        if asset is None:
            raise ValueError(f"Ativo com id={asset_id} não encontrado.")

        tracking_type = AssetTrackingType(asset.tracking_type)
        allowed = ALLOWED_TRANSACTION_TYPES[tracking_type]
        if transaction_type not in allowed:
            raise ValueError(
                f"Transação '{transaction_type.value}' não permitida para ativo "
                f"do tipo '{tracking_type.value}'. "
                f"Permitidos: {[t.value for t in allowed]}"
            )

        if (
            tracking_type == AssetTrackingType.QUANTITY_PRICE
            and transaction_type in _REQUIRES_QTY_AND_PRICE
            and (quantity is None or unit_price is None)
        ):
            raise ValueError(
                f"'{transaction_type.value}' para ativo QUANTITY_PRICE "
                f"exige 'quantity' e 'unit_price'."
            )

        if transaction_type != TransactionType.WITHDRAWAL and total_amount <= Decimal("0"):
            raise ValueError(
                f"total_amount deve ser maior que zero. Recebido: {total_amount}"
            )

        tx = Transaction(
            asset_id=asset_id,
            transaction_type=transaction_type.value,
            date=date,
            total_amount=total_amount,
            quantity=quantity,
            unit_price=unit_price,
            fees=fees,
            notes=notes,
        )
        self._session.add(tx)
        self._session.flush()
        return tx

    def delete(self, id: int) -> None:
        tx = self.get_by_id(id)
        if tx is None:
            raise ValueError(f"Transação com id={id} não encontrada.")
        if tx.transaction_type == TransactionType.INITIAL_BALANCE.value:
            raise ValueError(
                "Não é possível excluir o Saldo Inicial de um ativo. "
                "Para remover o ativo do sistema, utilize 'Desativar Ativo'."
            )
        self._session.delete(tx)
        self._session.flush()
