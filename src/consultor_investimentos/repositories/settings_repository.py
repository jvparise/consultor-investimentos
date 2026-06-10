from decimal import Decimal

from sqlalchemy.orm import Session

from consultor_investimentos.database.models import UserSettings

_PCT_FIELDS = [
    "target_equity_pct",
    "target_fixed_pct",
    "target_etf_pct",
    "target_fii_brick_pct",
    "target_fii_paper_pct",
    "target_intl_pct",
    "target_crypto_pct",
    "target_other_pct",
]

_ALLOWED_FIELDS = {
    "user_name",
    "monthly_contribution",
    "monthly_expenses",
    "risk_profile",
    *_PCT_FIELDS,
}


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self) -> UserSettings:
        settings = self._session.get(UserSettings, 1)
        if settings is None:
            settings = UserSettings(id=1)
            self._session.add(settings)
            self._session.flush()
        return settings

    def update(self, data: dict) -> UserSettings:
        settings = self.get_or_create()

        for key, value in data.items():
            if key in _ALLOWED_FIELDS:
                setattr(settings, key, value)

        total_pct = sum(
            Decimal(str(getattr(settings, f) or 0)) for f in _PCT_FIELDS
        )
        if total_pct not in (Decimal("0"), Decimal("100")):
            raise ValueError(
                f"Soma dos percentuais de alocação deve ser 0 (não configurado) "
                f"ou 100. Atual: {total_pct}"
            )

        self._session.flush()
        return settings
