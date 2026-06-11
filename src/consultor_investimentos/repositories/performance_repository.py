"""Consultas de dados para o Relatório Mensal de Performance."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_investimentos.config import TransactionType
from consultor_investimentos.database.models import Asset, AssetPrice, Transaction

_INCOME_TYPES = [TransactionType.DIVIDEND.value, TransactionType.INTEREST.value]


class PerformanceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_price_up_to(self, asset_id: int, max_date: date) -> AssetPrice | None:
        """Último registro de preço com price_date <= max_date."""
        return self._session.execute(
            select(AssetPrice)
            .where(
                AssetPrice.asset_id == asset_id,
                AssetPrice.price_date <= max_date,
            )
            .order_by(AssetPrice.price_date.desc())
            .limit(1)
        ).scalar_one_or_none()

    def get_income_in_period(
        self, asset_id: int, start: date, end: date
    ) -> list[Transaction]:
        """Transações de DIVIDENDO e JUROS/CUPOM dentro do período (inclusive)."""
        return list(
            self._session.execute(
                select(Transaction)
                .where(
                    Transaction.asset_id == asset_id,
                    Transaction.transaction_type.in_(_INCOME_TYPES),
                    Transaction.date >= start,
                    Transaction.date <= end,
                )
                .order_by(Transaction.date.asc())
            ).scalars().all()
        )

    def get_active_assets(self) -> list[Asset]:
        """Retorna todos os ativos ativos."""
        return list(
            self._session.execute(
                select(Asset).where(Asset.is_active == True)  # noqa: E712
            ).scalars().all()
        )
