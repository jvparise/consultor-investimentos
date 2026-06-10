"""Testes do parser de valores monetários BR."""
from decimal import Decimal

import pytest

from consultor_investimentos.utils.brl import fmt_brl_input, parse_brl


# ── Entradas válidas ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("1.000,00",    Decimal("1000.00")),
    ("1000,00",     Decimal("1000.00")),
    ("1000.00",     Decimal("1000.00")),
    ("500",         Decimal("500")),
    ("0,50",        Decimal("0.50")),
    ("0.50",        Decimal("0.50")),
    ("R$ 1.234,56", Decimal("1234.56")),
    ("R$1.234,56",  Decimal("1234.56")),
    ("  1000,00  ", Decimal("1000.00")),
    ("1.000.000,00", Decimal("1000000.00")),
    ("0,01",        Decimal("0.01")),
    ("100",         Decimal("100")),
])
def test_parse_brl_validos(text: str, expected: Decimal) -> None:
    assert parse_brl(text) == expected


# ── Entradas inválidas ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "abc",
    "R$ banana",
    "1,2,3",
    "1.2.3",
    "",
    "   ",
    "R$",
    "--100",
    "1 000,00",
])
def test_parse_brl_invalidos(text: str) -> None:
    with pytest.raises(ValueError):
        parse_brl(text)


# ── fmt_brl_input ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value, expected", [
    (Decimal("1000.00"),    "1.000,00"),
    (Decimal("500000.50"),  "500.000,50"),
    (Decimal("0.01"),       "0,01"),
    (Decimal("0"),          ""),
    (None,                  ""),
])
def test_fmt_brl_input(value: Decimal | None, expected: str) -> None:
    assert fmt_brl_input(value) == expected


def test_parse_brl_tipo_invalido() -> None:
    with pytest.raises(ValueError):
        parse_brl(1000)  # type: ignore
