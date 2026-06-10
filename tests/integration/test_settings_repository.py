from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.repositories.settings_repository import SettingsRepository


def test_get_or_create_cria_com_defaults_na_primeira_chamada(session: Session) -> None:
    repo = SettingsRepository(session)
    settings = repo.get_or_create()

    assert settings.id == 1
    assert settings.user_name == "Investidor"
    assert settings.monthly_contribution == Decimal("0")
    assert settings.monthly_expenses == Decimal("0")


def test_get_or_create_retorna_existente_na_segunda_chamada(session: Session) -> None:
    repo = SettingsRepository(session)
    first = repo.get_or_create()
    first.user_name = "João"
    session.flush()

    second = repo.get_or_create()
    assert second.id == first.id
    assert second.user_name == "João"


def test_update_altera_campos_individuais(session: Session) -> None:
    repo = SettingsRepository(session)
    repo.get_or_create()

    updated = repo.update({"user_name": "João", "monthly_contribution": Decimal("6000")})

    assert updated.user_name == "João"
    assert updated.monthly_contribution == Decimal("6000")


def test_update_ignora_chaves_desconhecidas(session: Session) -> None:
    repo = SettingsRepository(session)
    repo.get_or_create()

    updated = repo.update({"user_name": "João", "campo_inexistente": "valor"})
    assert updated.user_name == "João"


def test_update_percentuais_validos_somando_100(session: Session) -> None:
    repo = SettingsRepository(session)
    repo.get_or_create()

    updated = repo.update({
        "target_equity_pct": Decimal("40"),
        "target_fixed_pct": Decimal("30"),
        "target_fii_brick_pct": Decimal("20"),
        "target_intl_pct": Decimal("5"),
        "target_crypto_pct": Decimal("0"),
        "target_other_pct": Decimal("5"),
    })

    assert updated.target_equity_pct == Decimal("40")


def test_update_percentuais_zerados_aceito(session: Session) -> None:
    repo = SettingsRepository(session)
    repo.get_or_create()

    updated = repo.update({
        "target_equity_pct": Decimal("0"),
        "target_fixed_pct": Decimal("0"),
        "target_fii_brick_pct": Decimal("0"),
        "target_intl_pct": Decimal("0"),
        "target_crypto_pct": Decimal("0"),
        "target_other_pct": Decimal("0"),
    })

    assert updated.target_equity_pct == Decimal("0")


def test_update_percentuais_nao_somando_100_levanta_value_error(session: Session) -> None:
    repo = SettingsRepository(session)
    repo.get_or_create()

    with pytest.raises(ValueError, match="Soma dos percentuais"):
        repo.update({
            "target_equity_pct": Decimal("50"),
            "target_fixed_pct": Decimal("30"),
        })
