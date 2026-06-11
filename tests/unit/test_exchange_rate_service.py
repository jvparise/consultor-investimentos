"""Testes para ExchangeRateService e utils/currency.py."""
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import Currency
from consultor_investimentos.services.exchange_rate_service import ExchangeRateService
from consultor_investimentos.utils.currency import convert_to_brl


# ── ExchangeRateService ──────────────────────────────────────────────────────


def test_set_and_get_usd_rate(session: Session) -> None:
    svc = ExchangeRateService(session)
    svc.set_rate(Currency.USD, Decimal("5.70"))
    rate = svc.get_rate(Currency.USD)
    assert rate == Decimal("5.70")


def test_set_and_get_eur_rate(session: Session) -> None:
    svc = ExchangeRateService(session)
    svc.set_rate(Currency.EUR, Decimal("6.20"))
    rate = svc.get_rate(Currency.EUR)
    assert rate == Decimal("6.20")


def test_update_existing_rate(session: Session) -> None:
    svc = ExchangeRateService(session)
    svc.set_rate(Currency.USD, Decimal("5.50"))
    svc.set_rate(Currency.USD, Decimal("5.75"))
    rate = svc.get_rate(Currency.USD)
    assert rate == Decimal("5.75")


def test_brl_rate_always_one(session: Session) -> None:
    svc = ExchangeRateService(session)
    assert svc.get_rate(Currency.BRL) == Decimal("1")


def test_cannot_set_brl_rate(session: Session) -> None:
    svc = ExchangeRateService(session)
    with pytest.raises(ValueError, match="BRL"):
        svc.set_rate(Currency.BRL, Decimal("1"))


def test_invalid_rate_raises(session: Session) -> None:
    svc = ExchangeRateService(session)
    with pytest.raises(ValueError, match="zero"):
        svc.set_rate(Currency.USD, Decimal("0"))


def test_negative_rate_raises(session: Session) -> None:
    svc = ExchangeRateService(session)
    with pytest.raises(ValueError):
        svc.set_rate(Currency.USD, Decimal("-1"))


def test_get_all_rates_includes_brl(session: Session) -> None:
    svc = ExchangeRateService(session)
    svc.set_rate(Currency.USD, Decimal("5.70"))
    rates = svc.get_all_rates()
    assert Currency.BRL in rates
    assert rates[Currency.BRL] == Decimal("1")
    assert rates[Currency.USD] == Decimal("5.70")


def test_get_rate_returns_none_when_not_set(session: Session) -> None:
    svc = ExchangeRateService(session)
    # EUR não foi cadastrado nesta sessão de teste isolada
    rate = svc.get_rate(Currency.EUR)
    assert rate is None


# ── convert_to_brl ────────────────────────────────────────────────────────────


def test_convert_brl_returns_original() -> None:
    rates: dict[Currency, Decimal] = {Currency.BRL: Decimal("1")}
    result = convert_to_brl(Decimal("1000"), Currency.BRL, rates)
    assert result == Decimal("1000")


def test_convert_usd_to_brl() -> None:
    rates = {Currency.BRL: Decimal("1"), Currency.USD: Decimal("5.70")}
    result = convert_to_brl(Decimal("100"), Currency.USD, rates)
    assert result == Decimal("570.000000")


def test_convert_eur_to_brl() -> None:
    rates = {Currency.BRL: Decimal("1"), Currency.EUR: Decimal("6.20")}
    result = convert_to_brl(Decimal("50"), Currency.EUR, rates)
    assert result == Decimal("310.000000")


def test_convert_missing_rate_falls_back_to_one() -> None:
    rates: dict[Currency, Decimal] = {Currency.BRL: Decimal("1")}
    result = convert_to_brl(Decimal("200"), Currency.USD, rates)
    assert result == Decimal("200.000000")
