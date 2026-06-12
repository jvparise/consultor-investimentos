"""Testes unitários para YahooProvider — sem internet (yfinance mockado)."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from consultor_investimentos.config import AssetClass, Currency
from consultor_investimentos.services.market_data.yahoo_provider import (
    YahooProvider,
    _to_yahoo_ticker,
)

# ── _to_yahoo_ticker ───────────────────────────────────────────────────────────

def test_ticker_brl_equity():
    assert _to_yahoo_ticker("PETR4", AssetClass.EQUITY.value, Currency.BRL.value) == "PETR4.SA"


def test_ticker_brl_etf():
    assert _to_yahoo_ticker("IVVB11", AssetClass.ETF.value, Currency.BRL.value) == "IVVB11.SA"


def test_ticker_brl_fii():
    assert _to_yahoo_ticker("HGLG11", AssetClass.FII_BRICK.value, Currency.BRL.value) == "HGLG11.SA"


def test_ticker_already_sa_unchanged():
    assert _to_yahoo_ticker("PETR4.SA", AssetClass.EQUITY.value, Currency.BRL.value) == "PETR4.SA"


def test_ticker_usd_unchanged():
    assert _to_yahoo_ticker("IVV", AssetClass.INTERNATIONAL.value, Currency.USD.value) == "IVV"


def test_ticker_usd_aapl_unchanged():
    assert _to_yahoo_ticker("AAPL", AssetClass.INTERNATIONAL.value, Currency.USD.value) == "AAPL"


def test_ticker_crypto_adds_usd():
    assert _to_yahoo_ticker("BTC", AssetClass.CRYPTO.value, Currency.BRL.value) == "BTC-USD"


def test_ticker_crypto_already_usd_unchanged():
    assert _to_yahoo_ticker("BTC-USD", AssetClass.CRYPTO.value, Currency.USD.value) == "BTC-USD"


def test_ticker_eth_crypto():
    assert _to_yahoo_ticker("ETH", AssetClass.CRYPTO.value, Currency.BRL.value) == "ETH-USD"


# ── YahooProvider.get_price ────────────────────────────────────────────────────

def _make_hist(price: float) -> pd.DataFrame:
    return pd.DataFrame({"Close": [price]}, index=[pd.Timestamp("2026-06-11")])


def test_get_price_ok():
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_hist(38.50)

    with patch("consultor_investimentos.services.market_data.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        price = YahooProvider().get_price("PETR4.SA")

    assert price == Decimal("38.5")


def test_get_price_multiple_days_takes_last():
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame(
        {"Close": [36.0, 37.0, 38.50]},
        index=[pd.Timestamp("2026-06-09"), pd.Timestamp("2026-06-10"), pd.Timestamp("2026-06-11")],
    )
    with patch("consultor_investimentos.services.market_data.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        price = YahooProvider().get_price("PETR4.SA")

    assert price == Decimal("38.5")


def test_get_price_returns_none_empty_hist():
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()

    with patch("consultor_investimentos.services.market_data.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        price = YahooProvider().get_price("UNKNOWN.SA")

    assert price is None


def test_get_price_returns_none_on_exception():
    with patch(
        "consultor_investimentos.services.market_data.yahoo_provider.yf.Ticker",
        side_effect=Exception("network error"),
    ):
        price = YahooProvider().get_price("PETR4.SA")

    assert price is None


def test_get_price_returns_none_when_zero():
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_hist(0.0)

    with patch("consultor_investimentos.services.market_data.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        price = YahooProvider().get_price("PETR4.SA")

    assert price is None


# ── Cache ──────────────────────────────────────────────────────────────────────

def test_cache_hit_skips_second_fetch():
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_hist(100.0)

    with patch(
        "consultor_investimentos.services.market_data.yahoo_provider.yf.Ticker",
        return_value=mock_ticker,
    ) as MockTicker:
        provider = YahooProvider()
        provider.get_price("PETR4.SA")
        provider.get_price("PETR4.SA")

    assert MockTicker.call_count == 1


def test_different_tickers_each_fetched():
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_hist(100.0)

    with patch(
        "consultor_investimentos.services.market_data.yahoo_provider.yf.Ticker",
        return_value=mock_ticker,
    ) as MockTicker:
        provider = YahooProvider()
        provider.get_price("PETR4.SA")
        provider.get_price("VALE3.SA")

    assert MockTicker.call_count == 2


def test_clear_cache_forces_refetch():
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_hist(100.0)

    with patch(
        "consultor_investimentos.services.market_data.yahoo_provider.yf.Ticker",
        return_value=mock_ticker,
    ) as MockTicker:
        provider = YahooProvider()
        provider.get_price("PETR4.SA")
        provider.clear_cache()
        provider.get_price("PETR4.SA")

    assert MockTicker.call_count == 2
