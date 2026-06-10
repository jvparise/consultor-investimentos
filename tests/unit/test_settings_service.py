"""Testes do SettingsService."""
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.services.settings_service import SettingsService
from consultor_investimentos.services.dto import SettingsDTO


def test_get_settings_retorna_dto(session: Session) -> None:
    svc = SettingsService(session)
    dto = svc.get_settings()

    assert isinstance(dto, SettingsDTO)
    assert dto.user_name == "Investidor"
    assert dto.monthly_contribution == Decimal("0")


def test_get_settings_retorna_dados_atualizados(session: Session) -> None:
    svc = SettingsService(session)
    svc.update_settings({
        "user_name": "João Parise",
        "monthly_contribution": Decimal("6000"),
        "monthly_expenses": Decimal("2000"),
    })

    dto = svc.get_settings()
    assert dto.user_name == "João Parise"
    assert dto.monthly_contribution == Decimal("6000")
    assert dto.monthly_expenses == Decimal("2000")


def test_update_settings_alocacao_valida(session: Session) -> None:
    svc = SettingsService(session)
    svc.update_settings({
        "target_equity_pct": Decimal("60"),
        "target_fixed_pct": Decimal("40"),
    })
    dto = svc.get_settings()
    assert dto.target_equity_pct == Decimal("60")
    assert dto.target_fixed_pct == Decimal("40")


def test_update_settings_alocacao_invalida_levanta_value_error(session: Session) -> None:
    svc = SettingsService(session)
    with pytest.raises(ValueError, match="100"):
        svc.update_settings({
            "target_equity_pct": Decimal("60"),
            "target_fixed_pct": Decimal("30"),
        })


def test_get_settings_nao_retorna_orm(session: Session) -> None:
    svc = SettingsService(session)
    dto = svc.get_settings()
    from consultor_investimentos.database.models import UserSettings
    assert not isinstance(dto, UserSettings)


def test_get_target_pct(session: Session) -> None:
    from consultor_investimentos.config import AssetClass
    svc = SettingsService(session)
    svc.update_settings({
        "target_equity_pct": Decimal("70"),
        "target_fixed_pct": Decimal("30"),
    })
    dto = svc.get_settings()
    assert svc.get_target_pct(dto, AssetClass.EQUITY) == 70.0
    assert svc.get_target_pct(dto, AssetClass.FIXED_INCOME) == 30.0
    assert svc.get_target_pct(dto, AssetClass.FII_BRICK) == 0.0


def test_update_asset_altera_nome(session: Session) -> None:
    from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType
    from consultor_investimentos.repositories.asset_repository import AssetRepository

    asset = AssetRepository(session).create(
        ticker="ITSA4",
        name="Itaúsa Original",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )

    svc = SettingsService(session)
    svc.update_asset(asset.id, name="Itaúsa Atualizada")

    updated = AssetRepository(session).get_by_id(asset.id)
    assert updated.name == "Itaúsa Atualizada"


def test_update_asset_altera_notes(session: Session) -> None:
    from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType
    from consultor_investimentos.repositories.asset_repository import AssetRepository

    asset = AssetRepository(session).create(
        ticker="WEGE3",
        name="WEG S.A.",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )

    svc = SettingsService(session)
    svc.update_asset(asset.id, notes="Posição de longo prazo")

    updated = AssetRepository(session).get_by_id(asset.id)
    assert updated.notes == "Posição de longo prazo"


def test_deactivate_asset_torna_inativo(session: Session) -> None:
    from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType
    from consultor_investimentos.repositories.asset_repository import AssetRepository

    asset = AssetRepository(session).create(
        ticker="DEAC3",
        name="Ativo para desativar",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    assert asset.is_active is True

    svc = SettingsService(session)
    svc.deactivate_asset(asset.id)

    updated = AssetRepository(session).get_by_id(asset.id)
    assert updated.is_active is False


def test_deactivate_asset_nao_aparece_em_get_active(session: Session) -> None:
    from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType
    from consultor_investimentos.repositories.asset_repository import AssetRepository

    asset = AssetRepository(session).create(
        ticker="GONE3",
        name="Ativo removido",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )

    svc = SettingsService(session)
    svc.deactivate_asset(asset.id)

    active_tickers = [a.ticker for a in AssetRepository(session).get_active()]
    assert "GONE3" not in active_tickers


# ── create_asset ──────────────────────────────────────────────────────────────

def test_create_asset_retorna_asset_id_int(session: Session) -> None:
    from consultor_investimentos.config import AssetClass, AssetTrackingType

    asset_id = SettingsService(session).create_asset(
        ticker="VALE3",
        name="Vale S.A.",
        asset_class=AssetClass.EQUITY,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    assert isinstance(asset_id, int)
    assert asset_id > 0


def test_create_asset_persiste_no_banco(session: Session) -> None:
    from consultor_investimentos.config import AssetClass, AssetTrackingType
    from consultor_investimentos.repositories.asset_repository import AssetRepository

    asset_id = SettingsService(session).create_asset(
        ticker="WEGE3",
        name="WEG S.A.",
        asset_class=AssetClass.EQUITY,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    asset = AssetRepository(session).get_by_id(asset_id)
    assert asset is not None
    assert asset.ticker == "WEGE3"
    assert asset.name == "WEG S.A."


def test_create_asset_infere_income_type_variable_para_qp(session: Session) -> None:
    """D7: QUANTITY_PRICE → income_type = VARIABLE."""
    from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType
    from consultor_investimentos.repositories.asset_repository import AssetRepository

    asset_id = SettingsService(session).create_asset(
        ticker="PETR4",
        name="Petrobras",
        asset_class=AssetClass.EQUITY,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    asset = AssetRepository(session).get_by_id(asset_id)
    assert asset.income_type == IncomeType.VARIABLE.value


def test_create_asset_infere_income_type_fixed_para_vo(session: Session) -> None:
    """D7: VALUE_ONLY → income_type = FIXED."""
    from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType
    from consultor_investimentos.repositories.asset_repository import AssetRepository

    asset_id = SettingsService(session).create_asset(
        ticker="TESOURO-SELIC",
        name="Tesouro Selic 2027",
        asset_class=AssetClass.FIXED_INCOME,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )
    asset = AssetRepository(session).get_by_id(asset_id)
    assert asset.income_type == IncomeType.FIXED.value


def test_create_asset_cash_com_value_only_funciona(session: Session) -> None:
    """D9: CASH + VALUE_ONLY é permitido."""
    from consultor_investimentos.config import AssetClass, AssetTrackingType

    asset_id = SettingsService(session).create_asset(
        ticker="NUBANK",
        name="Nubank Conta",
        asset_class=AssetClass.CASH,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )
    assert isinstance(asset_id, int)


def test_create_asset_cash_com_qp_levanta_value_error(session: Session) -> None:
    """D9: CASH + QUANTITY_PRICE é proibido."""
    from consultor_investimentos.config import AssetClass, AssetTrackingType

    with pytest.raises(ValueError, match="Caixa"):
        SettingsService(session).create_asset(
            ticker="CASHQP",
            name="Caixa inválido",
            asset_class=AssetClass.CASH,
            tracking_type=AssetTrackingType.QUANTITY_PRICE,
        )


def test_create_asset_ticker_duplicado_levanta_value_error(session: Session) -> None:
    """D8: ticker duplicado é rejeitado."""
    from consultor_investimentos.config import AssetClass, AssetTrackingType

    svc = SettingsService(session)
    svc.create_asset(
        ticker="MGLU3",
        name="Magazine Luiza",
        asset_class=AssetClass.EQUITY,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    with pytest.raises(ValueError, match="MGLU3"):
        svc.create_asset(
            ticker="MGLU3",
            name="Duplicado",
            asset_class=AssetClass.EQUITY,
            tracking_type=AssetTrackingType.QUANTITY_PRICE,
        )


def test_create_asset_ticker_normalizado_maiusculo(session: Session) -> None:
    from consultor_investimentos.config import AssetClass, AssetTrackingType
    from consultor_investimentos.repositories.asset_repository import AssetRepository

    asset_id = SettingsService(session).create_asset(
        ticker="bcff11",
        name="BTG Pactual Fundo",
        asset_class=AssetClass.FII_BRICK,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    asset = AssetRepository(session).get_by_id(asset_id)
    assert asset.ticker == "BCFF11"


def test_get_active_assets_retorna_lista_de_dicts(session: Session) -> None:
    from consultor_investimentos.config import AssetClass, AssetTrackingType

    svc = SettingsService(session)
    svc.create_asset(ticker="XPML11", name="XP Malls", asset_class=AssetClass.FII_BRICK, tracking_type=AssetTrackingType.QUANTITY_PRICE)
    svc.create_asset(ticker="HGLG11", name="CSHG Logística", asset_class=AssetClass.FII_BRICK, tracking_type=AssetTrackingType.QUANTITY_PRICE)

    assets = svc.get_active_assets()
    assert len(assets) == 2
    assert all(isinstance(a, dict) for a in assets)
    assert all("id" in a and "ticker" in a and "name" in a for a in assets)
