from datetime import date, datetime, timedelta
from decimal import Decimal

import yfinance as yf

from consultor_investimentos.config import AssetClass, Currency

_TTL = timedelta(minutes=15)


def _to_yahoo_ticker(ticker: str, asset_class: str, currency: str) -> str:
    """Converte ticker interno para formato Yahoo Finance."""
    if asset_class == AssetClass.CRYPTO.value:
        if "-" not in ticker:
            return f"{ticker}-USD"
        return ticker
    if currency == Currency.BRL.value:
        if not ticker.endswith(".SA"):
            return f"{ticker}.SA"
        return ticker
    return ticker


class YahooProvider:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[Decimal, datetime]] = {}

    def _get_cached(self, key: str) -> Decimal | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, fetched_at = entry
        if datetime.now() - fetched_at > _TTL:
            del self._cache[key]
            return None
        return value

    def _set_cached(self, key: str, value: Decimal) -> None:
        self._cache[key] = (value, datetime.now())

    def get_price(self, yahoo_ticker: str) -> Decimal | None:
        """Retorna o último preço de fechamento disponível. Nunca lança exceção."""
        cached = self._get_cached(yahoo_ticker)
        if cached is not None:
            return cached
        try:
            ticker = yf.Ticker(yahoo_ticker)
            hist = ticker.history(period="5d")
            if hist is None or hist.empty:
                return None
            price = Decimal(str(hist["Close"].iloc[-1]))
            if price <= 0:
                return None
            self._set_cached(yahoo_ticker, price)
            return price
        except Exception:
            return None

    def to_yahoo_ticker(self, ticker: str, asset_class: str, currency: str) -> str:
        return _to_yahoo_ticker(ticker, asset_class, currency)

    def get_history(
        self, yahoo_ticker: str, start: date, end: date
    ) -> list[tuple[date, Decimal]]:
        """Busca histórico de fechamento para um intervalo de datas. Nunca lança exceção."""
        try:
            ticker = yf.Ticker(yahoo_ticker)
            end_exclusive = end + timedelta(days=1)
            hist = ticker.history(start=start.isoformat(), end=end_exclusive.isoformat())
            if hist is None or hist.empty:
                return []
            result = []
            for ts, row in hist.iterrows():
                d = ts.date() if hasattr(ts, "date") else ts.to_pydatetime().date()
                result.append((d, Decimal(str(row["Close"]))))
            return result
        except Exception:
            return []

    def clear_cache(self) -> None:
        self._cache.clear()
