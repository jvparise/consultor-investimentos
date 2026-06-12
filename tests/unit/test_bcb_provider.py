"""Testes unitários para BCBProvider — sem internet (httpx mockado)."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from consultor_investimentos.services.market_data.bcb_provider import BCBProvider


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ptax_response(sell_rate: float) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = {
        "value": [{"cotacaoCompra": sell_rate - 0.01, "cotacaoVenda": sell_rate}]
    }
    mock.raise_for_status.return_value = None
    return mock


def _empty_ptax_response() -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = {"value": []}
    mock.raise_for_status.return_value = None
    return mock


def _sgs_response(value: str) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = [{"data": "12/06/2026", "valor": value}]
    mock.raise_for_status.return_value = None
    return mock


# ── PTAX ───────────────────────────────────────────────────────────────────────

def test_get_ptax_usd():
    with patch("httpx.get", return_value=_ptax_response(5.71)):
        rate = BCBProvider().get_ptax("USD")
    assert rate == Decimal("5.71")


def test_get_ptax_eur():
    with patch("httpx.get", return_value=_ptax_response(6.12)):
        rate = BCBProvider().get_ptax("EUR")
    assert rate == Decimal("6.12")


def test_get_ptax_uses_cotacao_venda():
    mock = MagicMock()
    mock.json.return_value = {
        "value": [{"cotacaoCompra": 5.68, "cotacaoVenda": 5.71}]
    }
    mock.raise_for_status.return_value = None
    with patch("httpx.get", return_value=mock):
        rate = BCBProvider().get_ptax("USD")
    assert rate == Decimal("5.71")


def test_get_ptax_retries_when_empty():
    """Quando API retorna lista vazia (fim de semana), tenta dias anteriores."""
    with patch("httpx.get", side_effect=[_empty_ptax_response(), _ptax_response(5.71)]):
        rate = BCBProvider().get_ptax("USD")
    assert rate == Decimal("5.71")


def test_get_ptax_returns_none_when_all_empty():
    with patch("httpx.get", return_value=_empty_ptax_response()):
        rate = BCBProvider().get_ptax("USD")
    assert rate is None


def test_get_ptax_returns_none_on_exception():
    with patch("httpx.get", side_effect=Exception("timeout")):
        rate = BCBProvider().get_ptax("USD")
    assert rate is None


def test_get_ptax_returns_none_on_http_error():
    mock = MagicMock()
    mock.raise_for_status.side_effect = Exception("404")
    with patch("httpx.get", return_value=mock):
        rate = BCBProvider().get_ptax("USD")
    assert rate is None


# ── SGS (CDI / SELIC / IPCA) ──────────────────────────────────────────────────

def test_get_cdi():
    with patch("httpx.get", return_value=_sgs_response("0.0438")):
        rate = BCBProvider().get_cdi()
    assert rate == Decimal("0.0438")


def test_get_selic():
    with patch("httpx.get", return_value=_sgs_response("10.75")):
        rate = BCBProvider().get_selic()
    assert rate == Decimal("10.75")


def test_get_ipca():
    with patch("httpx.get", return_value=_sgs_response("0.44")):
        rate = BCBProvider().get_ipca()
    assert rate == Decimal("0.44")


def test_get_cdi_valor_com_virgula():
    """BCB pode retornar valor com vírgula como decimal."""
    with patch("httpx.get", return_value=_sgs_response("0,0438")):
        rate = BCBProvider().get_cdi()
    assert rate == Decimal("0.0438")


def test_get_cdi_returns_none_on_exception():
    with patch("httpx.get", side_effect=Exception("network error")):
        rate = BCBProvider().get_cdi()
    assert rate is None


def test_get_selic_returns_none_empty_response():
    mock = MagicMock()
    mock.json.return_value = []
    mock.raise_for_status.return_value = None
    with patch("httpx.get", return_value=mock):
        rate = BCBProvider().get_selic()
    assert rate is None


# ── Cache ──────────────────────────────────────────────────────────────────────

def test_cache_hit_ptax():
    with patch("httpx.get", return_value=_ptax_response(5.71)) as mock_get:
        provider = BCBProvider()
        provider.get_ptax("USD")
        provider.get_ptax("USD")
    # Apenas uma chamada real (segunda vem do cache)
    assert mock_get.call_count == 1


def test_cache_separado_por_moeda():
    with patch("httpx.get", return_value=_ptax_response(5.71)) as mock_get:
        provider = BCBProvider()
        provider.get_ptax("USD")
        provider.get_ptax("EUR")
    assert mock_get.call_count == 2


def test_clear_cache_forces_refetch():
    with patch("httpx.get", return_value=_ptax_response(5.71)) as mock_get:
        provider = BCBProvider()
        provider.get_ptax("USD")
        provider.clear_cache()
        provider.get_ptax("USD")
    assert mock_get.call_count == 2
