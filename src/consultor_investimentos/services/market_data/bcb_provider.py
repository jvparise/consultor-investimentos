from datetime import date, datetime, timedelta
from decimal import Decimal

import httpx
from httpx import HTTPError

_PTAX_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoMoedaDia(moeda=@moeda,dataCotacao=@dataCotacao)"
)
_SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados/ultimos/1?formato=json"

_TTL = timedelta(minutes=15)

_CDI_CODE = 12
_SELIC_CODE = 11
_IPCA_CODE = 433


class BCBProvider:
    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout
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

    def get_ptax(self, currency: str) -> Decimal | None:
        """Retorna a cotação de venda PTAX para USD ou EUR. Nunca lança exceção."""
        cache_key = f"ptax_{currency}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Tenta hoje e os últimos 5 dias (fins de semana e feriados não têm PTAX)
        for days_back in range(6):
            target = date.today() - timedelta(days=days_back)
            date_str = target.strftime("%m-%d-%Y")
            params = {
                "@moeda": f"'{currency}'",
                "@dataCotacao": f"'{date_str}'",
                "$top": "1",
                "$format": "json",
            }
            try:
                resp = httpx.get(_PTAX_URL, params=params, timeout=self._timeout)
                resp.raise_for_status()
                data = resp.json().get("value", [])
                if data:
                    rate = Decimal(str(data[0]["cotacaoVenda"]))
                    if rate > 0:
                        self._set_cached(cache_key, rate)
                        return rate
            except Exception:
                continue
        return None

    def _get_sgs(self, code: int, cache_key: str) -> Decimal | None:
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        try:
            url = _SGS_URL.format(code=code)
            resp = httpx.get(url, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            if data:
                raw = str(data[0]["valor"]).replace(",", ".")
                value = Decimal(raw)
                self._set_cached(cache_key, value)
                return value
        except Exception:
            pass
        return None

    def get_cdi(self) -> Decimal | None:
        return self._get_sgs(_CDI_CODE, "cdi")

    def get_selic(self) -> Decimal | None:
        return self._get_sgs(_SELIC_CODE, "selic")

    def get_ipca(self) -> Decimal | None:
        return self._get_sgs(_IPCA_CODE, "ipca")

    def get_series_range(
        self, code: int, start: date, end: date
    ) -> list[tuple[date, Decimal]]:
        """Busca série histórica do SGS para um intervalo de datas. Nunca lança exceção."""
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
        params = {
            "formato": "json",
            "dataInicial": start.strftime("%d/%m/%Y"),
            "dataFinal": end.strftime("%d/%m/%Y"),
        }
        try:
            resp = httpx.get(url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            result = []
            for item in data:
                d = datetime.strptime(item["data"], "%d/%m/%Y").date()
                raw = str(item["valor"]).replace(",", ".")
                result.append((d, Decimal(raw)))
            return result
        except Exception:
            return []

    def clear_cache(self) -> None:
        self._cache.clear()
