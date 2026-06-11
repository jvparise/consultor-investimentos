from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, Currency, SnapshotType, TransactionType
from consultor_investimentos.repositories import (
    AssetRepository,
    ContributionRepository,
    ExchangeRateRepository,
    HoldingRepository,
    SnapshotRepository,
)
from consultor_investimentos.utils.currency import convert_to_brl
from consultor_investimentos.services.dto import SnapshotPoint


class SnapshotService:
    def __init__(self, session: Session) -> None:
        self._snapshot_repo = SnapshotRepository(session)
        self._holding_repo = HoldingRepository(session)
        self._asset_repo = AssetRepository(session)
        self._contribution_repo = ContributionRepository(session)
        self._fx_repo = ExchangeRateRepository(session)

    def try_auto_snapshot(self) -> bool:
        """Tenta criar snapshot automático para hoje, se ainda não existir.

        Chamado na abertura do app. Retorna True se criado, False se já existia.
        """
        today = date.today()
        if self._snapshot_repo.exists_for_date(today):
            return False

        self._create_snapshot(today, SnapshotType.CALCULATED)
        return True

    def ensure_snapshot_for_today(self) -> None:
        """Garante que o snapshot de hoje reflete o estado atual do portfólio.

        Idempotente: sobrescreve qualquer snapshot existente para hoje com dados frescos.
        Chamado após BUY, SELL ou CONTRIBUTION para manter o histórico preciso.
        """
        self._create_snapshot(date.today(), SnapshotType.CALCULATED)

    def create_manual_snapshot(self, snapshot_date: date | None = None) -> None:
        """Cria snapshot manual. Sobrescreve um existente na mesma data."""
        target_date = snapshot_date or date.today()
        self._create_snapshot(target_date, SnapshotType.MANUAL)

    def get_history(
        self,
        start: date | None = None,
        end: date | None = None,
    ) -> list[SnapshotPoint]:
        snapshots = self._snapshot_repo.get_history(start=start, end=end)
        return [
            SnapshotPoint(
                snapshot_date=s.snapshot_date,
                total_value=s.total_value,
                snapshot_type=s.snapshot_type,
            )
            for s in snapshots
        ]

    def _create_snapshot(self, target_date: date, snapshot_type: SnapshotType) -> None:
        latest_prices = self._holding_repo.get_latest_all_active()
        if not latest_prices:
            return

        price_by_asset: dict[int, Decimal] = {
            ap.asset_id: ap.price for ap in latest_prices
        }

        rates = self._fx_repo.get_rates()
        rates[Currency.BRL] = Decimal("1")

        assets = self._asset_repo.get_active()
        by_class: dict[AssetClass, Decimal] = {}
        total_value = Decimal("0")
        all_have_prices = True

        for asset in assets:
            unit_price = price_by_asset.get(asset.id)
            if unit_price is None:
                all_have_prices = False
                continue

            currency = Currency(asset.currency)
            price_brl = convert_to_brl(unit_price, currency, rates)

            tracking_type = AssetTrackingType(asset.tracking_type)
            if tracking_type == AssetTrackingType.VALUE_ONLY:
                position_value = price_brl
            else:
                qty = self._current_quantity(asset.id)
                if qty <= 0:
                    continue
                position_value = (qty * price_brl).quantize(Decimal("0.01"))

            asset_class = AssetClass(asset.asset_class)
            by_class[asset_class] = by_class.get(asset_class, Decimal("0")) + position_value
            total_value += position_value

        if not all_have_prices and snapshot_type == SnapshotType.CALCULATED:
            snapshot_type = SnapshotType.INCOMPLETE

        details = [
            {
                "asset_class": ac.value,
                "total_value": value.quantize(Decimal("0.01")),
                "percentage": (
                    (value / total_value * 100).quantize(Decimal("0.01"))
                    if total_value > 0
                    else Decimal("0")
                ),
            }
            for ac, value in by_class.items()
        ]

        self._snapshot_repo.upsert(
            snapshot_date=target_date,
            total_value=total_value.quantize(Decimal("0.01")),
            snapshot_type=snapshot_type,
            details=details,
        )

    def _current_quantity(self, asset_id: int) -> Decimal:
        """Quantidade líquida atual: compras + saldo_inicial - vendas."""
        all_txs = self._contribution_repo.get_by_asset(asset_id)
        qty = Decimal("0")
        for tx in all_txs:
            tx_type = TransactionType(tx.transaction_type)
            if tx_type in (TransactionType.INITIAL_BALANCE, TransactionType.BUY):
                qty += tx.quantity or Decimal("0")
            elif tx_type == TransactionType.SELL:
                qty -= tx.quantity or Decimal("0")
        return qty
