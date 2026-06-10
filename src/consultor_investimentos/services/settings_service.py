from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType
from consultor_investimentos.repositories import AssetRepository
from consultor_investimentos.repositories.settings_repository import SettingsRepository
from consultor_investimentos.services.dto import SettingsDTO


_CLASS_TO_FIELD: dict[AssetClass, str] = {
    AssetClass.EQUITY: "target_equity_pct",
    AssetClass.FIXED_INCOME: "target_fixed_pct",
    AssetClass.FII: "target_fii_pct",
    AssetClass.INTERNATIONAL: "target_intl_pct",
    AssetClass.CRYPTO: "target_crypto_pct",
    AssetClass.OTHER: "target_other_pct",
}


class SettingsService:
    def __init__(self, session: Session) -> None:
        self._repo = SettingsRepository(session)
        self._asset_repo = AssetRepository(session)

    def get_settings(self) -> SettingsDTO:
        orm = self._repo.get_or_create()
        return SettingsDTO(
            user_name=orm.user_name,
            monthly_contribution=orm.monthly_contribution,
            monthly_expenses=orm.monthly_expenses,
            risk_profile=orm.risk_profile,
            target_equity_pct=orm.target_equity_pct,
            target_fixed_pct=orm.target_fixed_pct,
            target_fii_pct=orm.target_fii_pct,
            target_intl_pct=orm.target_intl_pct,
            target_crypto_pct=orm.target_crypto_pct,
            target_other_pct=orm.target_other_pct,
        )

    def update_settings(self, data: dict) -> None:
        self._repo.update(data)

    def get_target_pct(self, settings: SettingsDTO, asset_class: AssetClass) -> float:
        field = _CLASS_TO_FIELD.get(asset_class)
        if field is None:
            return 0.0
        return float(getattr(settings, field))

    def create_asset(
        self,
        ticker: str,
        name: str,
        asset_class: AssetClass,
        tracking_type: AssetTrackingType,
        notes: str | None = None,
    ) -> int:
        if asset_class == AssetClass.CASH and tracking_type != AssetTrackingType.VALUE_ONLY:
            raise ValueError(
                "Ativos da classe 'Caixa / Liquidez' devem usar rastreamento 'Valor Total'."
            )
        income_type = (
            IncomeType.VARIABLE if tracking_type == AssetTrackingType.QUANTITY_PRICE
            else IncomeType.FIXED
        )
        asset = self._asset_repo.create(
            ticker=ticker,
            name=name,
            asset_class=asset_class,
            income_type=income_type,
            tracking_type=tracking_type,
            notes=notes,
        )
        return asset.id

    def get_active_assets(self) -> list[dict]:
        assets = self._asset_repo.get_active()
        return [
            {
                "id": a.id,
                "ticker": a.ticker,
                "name": a.name,
                "asset_class": a.asset_class,
                "tracking_type": a.tracking_type,
                "notes": a.notes or "",
            }
            for a in assets
        ]

    def update_asset(self, asset_id: int, name: str | None = None, notes: str | None = None) -> None:
        self._asset_repo.update(id=asset_id, name=name, notes=notes)

    def deactivate_asset(self, asset_id: int) -> None:
        self._asset_repo.deactivate(id=asset_id)

    def reactivate_asset(self, asset_id: int) -> None:
        self._asset_repo.reactivate(id=asset_id)

    def get_inactive_assets(self) -> list[dict]:
        assets = self._asset_repo.get_inactive()
        return [
            {
                "id": a.id,
                "ticker": a.ticker,
                "name": a.name,
                "asset_class": a.asset_class,
            }
            for a in assets
        ]
