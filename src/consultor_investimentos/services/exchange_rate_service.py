from decimal import Decimal

from sqlalchemy.orm import Session

from consultor_investimentos.config import Currency
from consultor_investimentos.repositories.exchange_rate_repository import ExchangeRateRepository


class ExchangeRateService:
    def __init__(self, session: Session) -> None:
        self._repo = ExchangeRateRepository(session)

    def get_rate(self, currency: Currency) -> Decimal | None:
        if currency == Currency.BRL:
            return Decimal("1")
        record = self._repo.get(currency)
        return record.rate if record else None

    def set_rate(self, currency: Currency, rate: Decimal) -> None:
        if currency == Currency.BRL:
            raise ValueError("A cotação do BRL não pode ser alterada (é sempre 1).")
        if rate <= Decimal("0"):
            raise ValueError(f"Cotação deve ser maior que zero. Recebido: {rate}")
        self._repo.upsert(currency=currency, rate=rate)

    def get_all_rates(self) -> dict[Currency, Decimal]:
        """Retorna cotações de todas as moedas, incluindo BRL=1."""
        rates = self._repo.get_rates()
        rates[Currency.BRL] = Decimal("1")
        return rates
