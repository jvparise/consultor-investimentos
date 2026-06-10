from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from consultor_investimentos.config import TransactionType
from consultor_investimentos.repositories import (
    AssetRepository,
    ContributionRepository,
    HoldingRepository,
)
from consultor_investimentos.services.dto import TransactionDTO

_SNAPSHOT_TRIGGERING_TYPES = {
    TransactionType.BUY,
    TransactionType.SELL,
    TransactionType.CONTRIBUTION,
}


class TransactionService:
    def __init__(self, session: Session) -> None:
        self._contrib_repo = ContributionRepository(session)
        self._holding_repo = HoldingRepository(session)
        self._asset_repo = AssetRepository(session)

    def register(
        self,
        asset_id: int,
        transaction_type: TransactionType,
        tx_date: date,
        total_amount: Decimal,
        quantity: Decimal | None = None,
        unit_price: Decimal | None = None,
        fees: Decimal = Decimal("0"),
        notes: str | None = None,
        new_position_value: Decimal | None = None,
    ) -> None:
        """Registra transação e, para VALUE_ONLY, atualiza o valor da posição.

        new_position_value: novo valor total da posição (apenas VALUE_ONLY).
        Quando informado, faz upsert em AssetPrice na mesma data da transação.

        Raises:
            ValueError: se SELL exceder a quantidade disponível em carteira.
        """
        if transaction_type == TransactionType.SELL:
            current_qty = self._get_current_quantity(asset_id)
            sell_qty = quantity or Decimal("0")
            if sell_qty > current_qty:
                raise ValueError(
                    f"Quantidade vendida ({sell_qty}) excede o saldo disponível "
                    f"({current_qty} cotas)."
                )

        self._contrib_repo.create(
            asset_id=asset_id,
            transaction_type=transaction_type,
            date=tx_date,
            total_amount=total_amount,
            quantity=quantity,
            unit_price=unit_price,
            fees=fees,
            notes=notes,
        )

        if new_position_value is not None:
            self._holding_repo.upsert(
                asset_id=asset_id,
                price_date=tx_date,
                price=new_position_value,
            )

        if transaction_type == TransactionType.INITIAL_BALANCE:
            asset = self._asset_repo.get_by_id(asset_id)
            if asset is not None:
                from consultor_investimentos.config import AssetTrackingType
                tracking = AssetTrackingType(asset.tracking_type)
                if tracking == AssetTrackingType.QUANTITY_PRICE and unit_price is not None:
                    self._holding_repo.upsert(asset_id=asset_id, price_date=tx_date, price=unit_price)
                elif tracking == AssetTrackingType.VALUE_ONLY:
                    price_value = new_position_value if new_position_value is not None else total_amount
                    self._holding_repo.upsert(asset_id=asset_id, price_date=tx_date, price=price_value)

    @property
    def should_trigger_snapshot(self) -> set[TransactionType]:
        """Tipos de transação que exigem atualização do snapshot diário."""
        return _SNAPSHOT_TRIGGERING_TYPES

    def delete(self, transaction_id: int) -> None:
        self._contrib_repo.delete(transaction_id)

    def list_by_asset(self, asset_id: int) -> list[TransactionDTO]:
        """Todas as transações de um ativo, mais recentes primeiro."""
        asset = self._asset_repo.get_by_id(asset_id)
        if asset is None:
            return []
        txs = self._contrib_repo.get_by_asset(asset_id)
        return [self._to_dto(tx, asset.ticker) for tx in reversed(txs)]

    def list_recent(self, days: int = 90) -> list[TransactionDTO]:
        """Transações de todos os ativos nos últimos N dias, mais recentes primeiro."""
        start = date.today() - timedelta(days=days)
        txs = self._contrib_repo.get_by_date_range(start=start, end=date.today())
        asset_map = {a.id: a.ticker for a in self._asset_repo.get_all()}
        result = [self._to_dto(tx, asset_map.get(tx.asset_id, "?")) for tx in txs]
        return sorted(result, key=lambda t: t.date, reverse=True)

    def _get_current_quantity(self, asset_id: int) -> Decimal:
        """Quantidade líquida atual: compras + saldo_inicial − vendas."""
        all_txs = self._contrib_repo.get_by_asset(asset_id)
        qty = Decimal("0")
        for tx in all_txs:
            tx_type = TransactionType(tx.transaction_type)
            if tx_type in (TransactionType.INITIAL_BALANCE, TransactionType.BUY):
                qty += tx.quantity or Decimal("0")
            elif tx_type == TransactionType.SELL:
                qty -= tx.quantity or Decimal("0")
        return qty

    @staticmethod
    def _to_dto(tx: object, ticker: str) -> TransactionDTO:
        return TransactionDTO(
            id=tx.id,
            asset_id=tx.asset_id,
            asset_ticker=ticker,
            transaction_type=tx.transaction_type,
            date=tx.date,
            quantity=tx.quantity,
            unit_price=tx.unit_price,
            total_amount=tx.total_amount,
            fees=tx.fees,
            notes=tx.notes,
            can_delete=tx.transaction_type != TransactionType.INITIAL_BALANCE.value,
        )
