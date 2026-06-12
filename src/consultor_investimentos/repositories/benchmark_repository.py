from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_investimentos.database.models import BenchmarkHistory


class BenchmarkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, name: str, ref_date: date, value: Decimal) -> BenchmarkHistory:
        existing = self._get_on_date(name, ref_date)
        if existing is not None:
            existing.value = value
            self._session.flush()
            return existing
        record = BenchmarkHistory(
            benchmark_name=name,
            reference_date=ref_date,
            value=value,
        )
        self._session.add(record)
        self._session.flush()
        return record

    def get_latest(self, name: str) -> BenchmarkHistory | None:
        return self._session.execute(
            select(BenchmarkHistory)
            .where(BenchmarkHistory.benchmark_name == name)
            .order_by(BenchmarkHistory.reference_date.desc())
            .limit(1)
        ).scalar_one_or_none()

    def get_history(
        self,
        name: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[BenchmarkHistory]:
        stmt = (
            select(BenchmarkHistory)
            .where(BenchmarkHistory.benchmark_name == name)
            .order_by(BenchmarkHistory.reference_date.asc())
        )
        if start is not None:
            stmt = stmt.where(BenchmarkHistory.reference_date >= start)
        if end is not None:
            stmt = stmt.where(BenchmarkHistory.reference_date <= end)
        return list(self._session.execute(stmt).scalars().all())

    def exists(self, name: str, ref_date: date) -> bool:
        result = self._session.execute(
            select(BenchmarkHistory.id).where(
                BenchmarkHistory.benchmark_name == name,
                BenchmarkHistory.reference_date == ref_date,
            )
        ).scalar_one_or_none()
        return result is not None

    def _get_on_date(self, name: str, ref_date: date) -> BenchmarkHistory | None:
        return self._session.execute(
            select(BenchmarkHistory).where(
                BenchmarkHistory.benchmark_name == name,
                BenchmarkHistory.reference_date == ref_date,
            )
        ).scalar_one_or_none()
