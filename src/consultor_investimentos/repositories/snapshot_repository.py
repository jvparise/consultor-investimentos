from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from consultor_investimentos.config import SnapshotType
from consultor_investimentos.database.models import PortfolioSnapshot, PortfolioSnapshotDetail


class SnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest(self) -> PortfolioSnapshot | None:
        return self._session.execute(
            select(PortfolioSnapshot)
            .options(joinedload(PortfolioSnapshot.details))
            .order_by(PortfolioSnapshot.snapshot_date.desc())
            .limit(1)
        ).unique().scalar_one_or_none()

    def get_by_date(self, target_date: date) -> PortfolioSnapshot | None:
        return self._session.execute(
            select(PortfolioSnapshot)
            .options(joinedload(PortfolioSnapshot.details))
            .where(PortfolioSnapshot.snapshot_date == target_date)
        ).unique().scalar_one_or_none()

    def get_history(
        self,
        start: date | None = None,
        end: date | None = None,
    ) -> list[PortfolioSnapshot]:
        stmt = (
            select(PortfolioSnapshot)
            .options(joinedload(PortfolioSnapshot.details))
            .order_by(PortfolioSnapshot.snapshot_date.asc())
        )
        if start is not None:
            stmt = stmt.where(PortfolioSnapshot.snapshot_date >= start)
        if end is not None:
            stmt = stmt.where(PortfolioSnapshot.snapshot_date <= end)
        return list(self._session.execute(stmt).unique().scalars().all())

    def exists_for_date(self, target_date: date) -> bool:
        result = self._session.execute(
            select(PortfolioSnapshot.id).where(
                PortfolioSnapshot.snapshot_date == target_date
            )
        ).scalar_one_or_none()
        return result is not None

    def upsert(
        self,
        snapshot_date: date,
        total_value: Decimal,
        snapshot_type: SnapshotType,
        details: list[dict],
    ) -> PortfolioSnapshot:
        """Cria ou substitui snapshot de uma data. Details antigos são descartados.

        Args:
            details: lista de dicts com chaves 'asset_class', 'total_value', 'percentage'.
        """
        existing = self.get_by_date(snapshot_date)

        if existing is not None:
            existing.total_value = total_value
            existing.snapshot_type = snapshot_type.value
            for detail in list(existing.details):
                self._session.delete(detail)
            self._session.flush()
            # Expira a coleção details para forçar reload após o delete
            self._session.expire(existing, ["details"])
            snapshot = existing
        else:
            snapshot = PortfolioSnapshot(
                snapshot_date=snapshot_date,
                total_value=total_value,
                snapshot_type=snapshot_type.value,
            )
            self._session.add(snapshot)
            self._session.flush()

        for d in details:
            self._session.add(
                PortfolioSnapshotDetail(
                    snapshot_id=snapshot.id,
                    asset_class=d["asset_class"],
                    total_value=d["total_value"],
                    percentage=d["percentage"],
                )
            )
        self._session.flush()
        return snapshot
