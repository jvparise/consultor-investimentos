from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_investimentos.config import Currency
from consultor_investimentos.database.models import ExchangeRate


class ExchangeRateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, currency: Currency) -> ExchangeRate | None:
        return self._session.execute(
            select(ExchangeRate).where(ExchangeRate.currency == currency.value)
        ).scalar_one_or_none()

    def get_all(self) -> list[ExchangeRate]:
        return list(
            self._session.execute(select(ExchangeRate)).scalars().all()
        )

    def get_rates(self) -> dict[Currency, Decimal]:
        """Retorna mapa de moeda → cotação em BRL. BRL não consta (rate=1 implícito)."""
        rows = self.get_all()
        return {Currency(r.currency): r.rate for r in rows}

    def upsert(self, currency: Currency, rate: Decimal) -> ExchangeRate:
        if rate <= Decimal("0"):
            raise ValueError(f"Cotação deve ser maior que zero. Recebido: {rate}")
        existing = self.get(currency)
        if existing is not None:
            existing.rate = rate
            existing.updated_at = datetime.now()
            self._session.flush()
            return existing
        record = ExchangeRate(currency=currency.value, rate=rate)
        self._session.add(record)
        self._session.flush()
        return record
