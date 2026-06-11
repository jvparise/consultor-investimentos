from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, Currency, IncomeType
from consultor_investimentos.database.models import Asset


class AssetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, id: int) -> Asset | None:
        return self._session.get(Asset, id)

    def get_by_ticker(self, ticker: str) -> Asset | None:
        return self._session.execute(
            select(Asset).where(Asset.ticker == ticker.upper().strip())
        ).scalar_one_or_none()

    def get_active(self) -> list[Asset]:
        return list(
            self._session.execute(
                select(Asset)
                .where(Asset.is_active == True)  # noqa: E712
                .order_by(Asset.ticker)
            ).scalars().all()
        )

    def get_all(self) -> list[Asset]:
        return list(
            self._session.execute(
                select(Asset).order_by(Asset.ticker)
            ).scalars().all()
        )

    def get_active_by_class(self, asset_class: AssetClass) -> list[Asset]:
        return list(
            self._session.execute(
                select(Asset)
                .where(Asset.is_active == True, Asset.asset_class == asset_class.value)  # noqa: E712
                .order_by(Asset.ticker)
            ).scalars().all()
        )

    def create(
        self,
        ticker: str,
        name: str,
        asset_class: AssetClass,
        income_type: IncomeType,
        tracking_type: AssetTrackingType,
        currency: Currency = Currency.BRL,
        notes: str | None = None,
    ) -> Asset:
        ticker = ticker.upper().strip()
        existing = self.get_by_ticker(ticker)
        if existing is not None:
            status = "ativo" if existing.is_active else "inativo"
            raise ValueError(
                f"Ativo com ticker '{ticker}' já existe ({status}). "
                f"Reative-o em vez de criar um novo."
            )

        asset = Asset(
            ticker=ticker,
            name=name.strip(),
            asset_class=asset_class.value,
            income_type=income_type.value,
            tracking_type=tracking_type.value,
            currency=currency.value,
            notes=notes,
        )
        self._session.add(asset)
        self._session.flush()
        return asset

    def update(
        self,
        id: int,
        name: str | None = None,
        notes: str | None = None,
        asset_class: AssetClass | None = None,
        currency: Currency | None = None,
    ) -> Asset:
        asset = self.get_by_id(id)
        if asset is None:
            raise ValueError(f"Ativo com id={id} não encontrado.")

        if name is not None:
            asset.name = name.strip()
        if notes is not None:
            asset.notes = notes
        if asset_class is not None:
            asset.asset_class = asset_class.value
        if currency is not None:
            asset.currency = currency.value

        self._session.flush()
        return asset

    def deactivate(self, id: int) -> None:
        asset = self.get_by_id(id)
        if asset is None:
            raise ValueError(f"Ativo com id={id} não encontrado.")
        if not asset.is_active:
            raise ValueError(
                f"Ativo '{asset.ticker}' já está inativo."
            )
        asset.is_active = False
        self._session.flush()

    def reactivate(self, id: int) -> None:
        asset = self.get_by_id(id)
        if asset is None:
            raise ValueError(f"Ativo com id={id} não encontrado.")
        if asset.is_active:
            raise ValueError(f"Ativo '{asset.ticker}' já está ativo.")
        asset.is_active = True
        self._session.flush()

    def get_inactive(self) -> list[Asset]:
        return list(
            self._session.execute(
                select(Asset)
                .where(Asset.is_active == False)  # noqa: E712
                .order_by(Asset.ticker)
            ).scalars().all()
        )
