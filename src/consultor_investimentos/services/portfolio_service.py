from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, Currency, TransactionType
from consultor_investimentos.repositories import (
    AssetRepository,
    ContributionRepository,
    ExchangeRateRepository,
    HoldingRepository,
)
from consultor_investimentos.services.dto import AllocationData, PortfolioSummary, Position
from consultor_investimentos.utils.currency import convert_to_brl


class PortfolioService:
    def __init__(self, session: Session) -> None:
        self._asset_repo = AssetRepository(session)
        self._contribution_repo = ContributionRepository(session)
        self._holding_repo = HoldingRepository(session)
        self._fx_repo = ExchangeRateRepository(session)

    def _get_rates(self) -> dict[Currency, Decimal]:
        rates = self._fx_repo.get_rates()
        rates[Currency.BRL] = Decimal("1")
        return rates

    def get_all_positions(self) -> list[Position]:
        assets = self._asset_repo.get_active()
        rates = self._get_rates()
        return [p for a in assets if (p := self._build_position(a, rates)) is not None]

    def get_position(self, asset_id: int) -> Position | None:
        asset = self._asset_repo.get_by_id(asset_id)
        if asset is None or not asset.is_active:
            return None
        rates = self._get_rates()
        return self._build_position(asset, rates)

    def get_portfolio_summary(self) -> PortfolioSummary:
        all_active = self._asset_repo.get_active()
        rates = self._get_rates()
        positions: list[Position] = []
        unpriced_tickers: list[str] = []

        for asset in all_active:
            position = self._build_position(asset, rates)
            if position is not None:
                positions.append(position)
            else:
                unpriced_tickers.append(asset.ticker)

        total_value = sum((p.current_value for p in positions), Decimal("0"))
        total_cost = sum((p.total_cost for p in positions), Decimal("0"))
        absolute_return = total_value - total_cost
        pct_return = (
            (absolute_return / total_cost * 100).quantize(Decimal("0.01"))
            if total_cost > 0
            else Decimal("0")
        )

        for p in positions:
            p.portfolio_pct = (
                (p.current_value / total_value * 100).quantize(Decimal("0.01"))
                if total_value > 0
                else Decimal("0")
            )

        allocation = self.get_allocation_by_class(positions, total_value)

        return PortfolioSummary(
            total_value=total_value,
            total_cost=total_cost,
            absolute_return=absolute_return,
            pct_return=pct_return,
            positions=positions,
            allocation=allocation,
            unpriced_tickers=unpriced_tickers,
        )

    def get_active_asset_options(self) -> list[dict]:
        """Retorna lista mínima de ativos ativos para seletores de UI."""
        return [
            {
                "id": a.id,
                "ticker": a.ticker,
                "name": a.name,
                "tracking_type": a.tracking_type,
                "asset_class": a.asset_class,
                "currency": a.currency,
            }
            for a in self._asset_repo.get_active()
        ]

    def update_asset_price(self, asset_id: int, price_date: date, price: Decimal) -> None:
        self._holding_repo.upsert(asset_id=asset_id, price_date=price_date, price=price)

    def get_value_only_assets_for_update(self, period_start: date | None = None) -> list[dict]:
        """Retorna ativos VALUE_ONLY ativos com último preço e base do período."""
        today = date.today()
        if period_start is None:
            period_start = date(today.year, today.month, 1)
        assets = self._asset_repo.get_active()
        result = []
        for asset in assets:
            if asset.tracking_type != AssetTrackingType.VALUE_ONLY.value:
                continue
            latest = self._holding_repo.get_latest(asset.id)
            base = self._holding_repo.get_period_base(asset.id, period_start, today)
            result.append({
                "id": asset.id,
                "ticker": asset.ticker,
                "name": asset.name,
                "asset_class": asset.asset_class,
                "currency": asset.currency,
                "last_price": latest.price if latest else None,
                "last_date": latest.price_date if latest else None,
                "month_base_price": base.price if base else None,
                "month_base_date": base.price_date if base else None,
            })
        return result

    def bulk_update_prices(self, updates: list[tuple[int, date, Decimal]]) -> int:
        """Atualiza preços em batch. Retorna quantidade de registros salvos."""
        count = 0
        for asset_id, price_date, price in updates:
            self._holding_repo.upsert(asset_id=asset_id, price_date=price_date, price=price)
            count += 1
        return count

    @staticmethod
    def get_allocation_by_class(
        positions: list[Position],
        total_value: Decimal,
    ) -> list[AllocationData]:
        by_class: dict[AssetClass, Decimal] = {}
        for p in positions:
            by_class[p.asset_class] = by_class.get(p.asset_class, Decimal("0")) + p.current_value

        result = []
        for asset_class, value in by_class.items():
            pct = (
                (value / total_value * 100).quantize(Decimal("0.01"))
                if total_value > 0
                else Decimal("0")
            )
            result.append(AllocationData(asset_class=asset_class, total_value=value, percentage=pct))

        result.sort(key=lambda a: a.total_value, reverse=True)
        return result

    def _build_position(self, asset: object, rates: dict[Currency, Decimal]) -> Position | None:
        tracking_type = AssetTrackingType(asset.tracking_type)
        currency = Currency(asset.currency)
        latest_price = self._holding_repo.get_latest(asset.id)

        if latest_price is None:
            return None

        total_cost = self._calculate_total_cost(asset.id)

        # Preço em moeda nativa → converte para BRL
        native_price = latest_price.price
        price_brl = convert_to_brl(native_price, currency, rates)

        if tracking_type == AssetTrackingType.QUANTITY_PRICE:
            quantity, average_price = self._calculate_quantity_and_avg_price(asset.id)
            current_value = (quantity * price_brl).quantize(Decimal("0.01"))
        else:
            quantity = None
            average_price = None
            current_value = price_brl.quantize(Decimal("0.01"))

        absolute_return = current_value - total_cost
        pct_return = (
            (absolute_return / total_cost * 100).quantize(Decimal("0.01"))
            if total_cost > 0
            else Decimal("0")
        )

        return Position(
            asset_id=asset.id,
            ticker=asset.ticker,
            name=asset.name,
            asset_class=AssetClass(asset.asset_class),
            tracking_type=asset.tracking_type,
            currency=currency,
            quantity=quantity,
            average_price=average_price,
            current_price=native_price,
            current_price_brl=price_brl,
            current_value=current_value,
            total_cost=total_cost,
            absolute_return=absolute_return,
            pct_return=pct_return,
            portfolio_pct=Decimal("0"),
            price_date=latest_price.price_date,
            notes=asset.notes,
        )

    def _calculate_total_cost(self, asset_id: int) -> Decimal:
        """Soma de INITIAL_BALANCE + BUY + CONTRIBUTION (custo de aquisição em BRL)."""
        transactions = self._contribution_repo.get_cost_basis_transactions(asset_id)
        return sum((t.total_amount for t in transactions), Decimal("0"))

    def _calculate_quantity_and_avg_price(
        self, asset_id: int
    ) -> tuple[Decimal, Decimal | None]:
        """Preço médio ponderado móvel (PVPM) em moeda nativa do ativo."""
        all_txs = self._contribution_repo.get_by_asset(asset_id)

        total_bought_qty = Decimal("0")
        total_sold_qty = Decimal("0")
        weighted_cost = Decimal("0")

        for tx in all_txs:
            tx_type = TransactionType(tx.transaction_type)
            qty = tx.quantity or Decimal("0")

            if tx_type in (TransactionType.INITIAL_BALANCE, TransactionType.BUY):
                price = tx.unit_price or Decimal("0")
                weighted_cost += qty * price
                total_bought_qty += qty
            elif tx_type == TransactionType.SELL:
                total_sold_qty += qty

        current_qty = total_bought_qty - total_sold_qty

        if current_qty <= 0:
            return Decimal("0"), None

        avg_price = (
            (weighted_cost / total_bought_qty).quantize(Decimal("0.000001"))
            if total_bought_qty > 0
            else None
        )

        return current_qty.quantize(Decimal("0.000001")), avg_price
