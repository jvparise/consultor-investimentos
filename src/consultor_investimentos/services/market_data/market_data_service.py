from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetTrackingType, Currency
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.exchange_rate_repository import ExchangeRateRepository
from consultor_investimentos.repositories.holding_repository import HoldingRepository
from consultor_investimentos.services.market_data.bcb_provider import BCBProvider
from consultor_investimentos.services.market_data.yahoo_provider import YahooProvider


@dataclass
class PriceUpdateResult:
    asset_id: int
    ticker: str
    asset_name: str
    asset_class: str
    tracking_type: str
    yahoo_ticker: str | None
    previous_price: Decimal | None
    new_price: Decimal | None
    price_date: date | None
    source: str
    status: Literal["updated", "skipped", "error"]
    error_message: str | None = None


@dataclass
class MarketUpdateSummary:
    updated: int
    skipped: int
    errors: int
    results: list[PriceUpdateResult]
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExchangeRateUpdateResult:
    currency: str
    previous_rate: Decimal | None
    new_rate: Decimal | None
    status: Literal["updated", "skipped", "error"]
    error_message: str | None = None


class MarketDataService:
    def __init__(
        self,
        session: Session,
        yahoo: YahooProvider | None = None,
        bcb: BCBProvider | None = None,
    ) -> None:
        self._session = session
        self._asset_repo = AssetRepository(session)
        self._holding_repo = HoldingRepository(session)
        self._fx_repo = ExchangeRateRepository(session)
        self._yahoo = yahoo or YahooProvider()
        self._bcb = bcb or BCBProvider()

    def update_asset_price(self, asset_id: int) -> PriceUpdateResult:
        """Atualiza o preço de um ativo via Yahoo Finance."""
        asset = self._asset_repo.get_by_id(asset_id)
        if asset is None:
            return PriceUpdateResult(
                asset_id=asset_id, ticker="?", asset_name="?",
                asset_class="?", tracking_type="?",
                yahoo_ticker=None, previous_price=None, new_price=None,
                price_date=None, source="YAHOO", status="error",
                error_message=f"Ativo id={asset_id} não encontrado.",
            )

        if asset.tracking_type != AssetTrackingType.QUANTITY_PRICE.value:
            return PriceUpdateResult(
                asset_id=asset_id, ticker=asset.ticker, asset_name=asset.name,
                asset_class=asset.asset_class, tracking_type=asset.tracking_type,
                yahoo_ticker=None, previous_price=None, new_price=None,
                price_date=None, source="YAHOO", status="skipped",
                error_message="Ativo VALUE_ONLY não é atualizado via Yahoo Finance.",
            )

        yahoo_ticker = self._yahoo.to_yahoo_ticker(asset.ticker, asset.asset_class, asset.currency)
        latest = self._holding_repo.get_latest(asset_id)
        previous_price = latest.price if latest else None

        new_price = self._yahoo.get_price(yahoo_ticker)

        if new_price is None:
            return PriceUpdateResult(
                asset_id=asset_id, ticker=asset.ticker, asset_name=asset.name,
                asset_class=asset.asset_class, tracking_type=asset.tracking_type,
                yahoo_ticker=yahoo_ticker, previous_price=previous_price, new_price=None,
                price_date=None, source="YAHOO", status="error",
                error_message=f"Preço não encontrado para '{yahoo_ticker}' no Yahoo Finance.",
            )

        today = date.today()
        self._holding_repo.upsert(asset_id=asset_id, price_date=today, price=new_price, source="YAHOO")

        return PriceUpdateResult(
            asset_id=asset_id, ticker=asset.ticker, asset_name=asset.name,
            asset_class=asset.asset_class, tracking_type=asset.tracking_type,
            yahoo_ticker=yahoo_ticker, previous_price=previous_price, new_price=new_price,
            price_date=today, source="YAHOO", status="updated",
        )

    def update_all_prices(self) -> MarketUpdateSummary:
        """Atualiza preços de todos os ativos ativos via Yahoo Finance."""
        assets = self._asset_repo.get_active()
        results = [self.update_asset_price(asset.id) for asset in assets]
        return MarketUpdateSummary(
            updated=sum(1 for r in results if r.status == "updated"),
            skipped=sum(1 for r in results if r.status == "skipped"),
            errors=sum(1 for r in results if r.status == "error"),
            results=results,
        )

    def update_exchange_rates(self) -> list[ExchangeRateUpdateResult]:
        """Atualiza cotações USD/BRL e EUR/BRL via PTAX (Banco Central)."""
        results = []
        for currency in (Currency.USD, Currency.EUR):
            existing = self._fx_repo.get(currency)
            previous = existing.rate if existing else None

            new_rate = self._bcb.get_ptax(currency.value)
            if new_rate is None:
                results.append(ExchangeRateUpdateResult(
                    currency=currency.value, previous_rate=previous, new_rate=None,
                    status="error",
                    error_message=f"Cotação {currency.value}/BRL não disponível no Banco Central.",
                ))
                continue

            self._fx_repo.upsert(currency, new_rate)
            results.append(ExchangeRateUpdateResult(
                currency=currency.value, previous_rate=previous, new_rate=new_rate,
                status="updated",
            ))
        return results

    def get_price_status(self) -> list[dict]:
        """Retorna status de preços de todos os ativos ativos para exibição."""
        assets = self._asset_repo.get_active()
        result = []
        for asset in assets:
            latest = self._holding_repo.get_latest(asset.id)
            yahoo_ticker = None
            if asset.tracking_type == AssetTrackingType.QUANTITY_PRICE.value:
                yahoo_ticker = self._yahoo.to_yahoo_ticker(
                    asset.ticker, asset.asset_class, asset.currency
                )
            result.append({
                "id": asset.id,
                "ticker": asset.ticker,
                "name": asset.name,
                "asset_class": asset.asset_class,
                "tracking_type": asset.tracking_type,
                "currency": asset.currency,
                "last_price": latest.price if latest else None,
                "last_date": latest.price_date if latest else None,
                "source": latest.source if latest else None,
                "yahoo_ticker": yahoo_ticker,
            })
        return result
