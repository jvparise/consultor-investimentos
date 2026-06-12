from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from consultor_investimentos.database.models import Asset, AssetPrice


class HoldingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest(self, asset_id: int) -> AssetPrice | None:
        return self._session.execute(
            select(AssetPrice)
            .where(AssetPrice.asset_id == asset_id)
            .order_by(AssetPrice.price_date.desc())
            .limit(1)
        ).scalar_one_or_none()

    def get_period_base(self, asset_id: int, period_start: date, ref_date: date) -> AssetPrice | None:
        """Retorna o primeiro registro dentro do período ou o último antes dele."""
        first_in_period = self._session.execute(
            select(AssetPrice)
            .where(
                AssetPrice.asset_id == asset_id,
                AssetPrice.price_date >= period_start,
                AssetPrice.price_date <= ref_date,
            )
            .order_by(AssetPrice.price_date.asc())
            .limit(1)
        ).scalar_one_or_none()
        if first_in_period is not None:
            return first_in_period
        return self._session.execute(
            select(AssetPrice)
            .where(
                AssetPrice.asset_id == asset_id,
                AssetPrice.price_date < period_start,
            )
            .order_by(AssetPrice.price_date.desc())
            .limit(1)
        ).scalar_one_or_none()

    def get_on_date(self, asset_id: int, target_date: date) -> AssetPrice | None:
        return self._session.execute(
            select(AssetPrice).where(
                AssetPrice.asset_id == asset_id,
                AssetPrice.price_date == target_date,
            )
        ).scalar_one_or_none()

    def get_latest_all_active(self) -> list[AssetPrice]:
        """Retorna o registro mais recente de cada ativo ativo.

        Usado pelo SnapshotService para calcular o patrimônio total.
        """
        subq = (
            select(
                AssetPrice.asset_id,
                func.max(AssetPrice.price_date).label("max_date"),
            )
            .join(Asset, Asset.id == AssetPrice.asset_id)
            .where(Asset.is_active == True)  # noqa: E712
            .group_by(AssetPrice.asset_id)
            .subquery()
        )
        return list(
            self._session.execute(
                select(AssetPrice).join(
                    subq,
                    (AssetPrice.asset_id == subq.c.asset_id)
                    & (AssetPrice.price_date == subq.c.max_date),
                )
            ).scalars().all()
        )

    def get_history(self, asset_id: int) -> list[AssetPrice]:
        return list(
            self._session.execute(
                select(AssetPrice)
                .where(AssetPrice.asset_id == asset_id)
                .order_by(AssetPrice.price_date.asc())
            ).scalars().all()
        )

    def upsert(
        self,
        asset_id: int,
        price_date: date,
        price: Decimal,
        source: str = "MANUAL",
    ) -> AssetPrice:
        if price <= Decimal("0"):
            raise ValueError(
                f"Preço/valor deve ser maior que zero. Recebido: {price}"
            )

        existing = self.get_on_date(asset_id, price_date)
        if existing is not None:
            existing.price = price
            existing.source = source
            self._session.flush()
            return existing

        record = AssetPrice(
            asset_id=asset_id,
            price_date=price_date,
            price=price,
            source=source,
        )
        self._session.add(record)
        self._session.flush()
        return record
