import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType
from consultor_investimentos.database.models import Asset
from consultor_investimentos.repositories.asset_repository import AssetRepository


def _make_asset(session: Session, ticker: str = "VALE3", tracking_type: AssetTrackingType = AssetTrackingType.QUANTITY_PRICE) -> Asset:
    repo = AssetRepository(session)
    return repo.create(
        ticker=ticker,
        name=f"Ativo {ticker}",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=tracking_type,
    )


def test_create_quantity_price(session: Session) -> None:
    asset = _make_asset(session, "VALE3", AssetTrackingType.QUANTITY_PRICE)

    assert asset.id is not None
    assert asset.ticker == "VALE3"
    assert asset.tracking_type == AssetTrackingType.QUANTITY_PRICE.value
    assert asset.is_active is True


def test_create_value_only(session: Session) -> None:
    repo = AssetRepository(session)
    asset = repo.create(
        ticker="CDB-NUBANK",
        name="CDB Nubank",
        asset_class=AssetClass.FIXED_INCOME,
        income_type=IncomeType.FIXED,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )

    assert asset.tracking_type == AssetTrackingType.VALUE_ONLY.value


def test_create_normaliza_ticker_para_maiusculo(session: Session) -> None:
    repo = AssetRepository(session)
    asset = repo.create(
        ticker="vale3",
        name="Vale",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )

    assert asset.ticker == "VALE3"


def test_create_ticker_duplicado_levanta_value_error(session: Session) -> None:
    _make_asset(session, "VALE3")

    with pytest.raises(ValueError, match="já existe"):
        _make_asset(session, "VALE3")


def test_create_ticker_duplicado_inativo_levanta_value_error(session: Session) -> None:
    repo = AssetRepository(session)
    asset = _make_asset(session, "VALE3")
    repo.deactivate(asset.id)

    with pytest.raises(ValueError, match="inativo"):
        _make_asset(session, "VALE3")


def test_get_by_id_retorna_ativo(session: Session) -> None:
    repo = AssetRepository(session)
    created = _make_asset(session, "VALE3")

    found = repo.get_by_id(created.id)

    assert found is not None
    assert found.ticker == "VALE3"


def test_get_by_id_retorna_none_para_inexistente(session: Session) -> None:
    repo = AssetRepository(session)
    assert repo.get_by_id(9999) is None


def test_get_by_ticker(session: Session) -> None:
    repo = AssetRepository(session)
    _make_asset(session, "VALE3")

    found = repo.get_by_ticker("VALE3")
    assert found is not None
    assert found.ticker == "VALE3"


def test_get_active_nao_retorna_inativos(session: Session) -> None:
    repo = AssetRepository(session)
    active = _make_asset(session, "VALE3")
    inactive = _make_asset(session, "PETR4")
    repo.deactivate(inactive.id)

    result = repo.get_active()

    tickers = [a.ticker for a in result]
    assert "VALE3" in tickers
    assert "PETR4" not in tickers


def test_get_all_inclui_inativos(session: Session) -> None:
    repo = AssetRepository(session)
    active = _make_asset(session, "VALE3")
    inactive = _make_asset(session, "PETR4")
    repo.deactivate(inactive.id)

    result = repo.get_all()

    tickers = [a.ticker for a in result]
    assert "VALE3" in tickers
    assert "PETR4" in tickers


def test_get_active_by_class(session: Session) -> None:
    repo = AssetRepository(session)
    _make_asset(session, "VALE3")
    repo.create(
        ticker="MXRF11",
        name="Maxi Renda FII",
        asset_class=AssetClass.FII,
        income_type=IncomeType.HYBRID,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )

    equities = repo.get_active_by_class(AssetClass.EQUITY)
    fiis = repo.get_active_by_class(AssetClass.FII)

    assert len(equities) == 1
    assert equities[0].ticker == "VALE3"
    assert len(fiis) == 1
    assert fiis[0].ticker == "MXRF11"


def test_update_nome_e_notas(session: Session) -> None:
    repo = AssetRepository(session)
    asset = _make_asset(session, "VALE3")

    updated = repo.update(asset.id, name="Vale S.A. Novo Nome", notes="Mineração")

    assert updated.name == "Vale S.A. Novo Nome"
    assert updated.notes == "Mineração"
    assert updated.ticker == "VALE3"


def test_update_id_inexistente_levanta_value_error(session: Session) -> None:
    repo = AssetRepository(session)

    with pytest.raises(ValueError, match="não encontrado"):
        repo.update(9999, name="Qualquer")


def test_deactivate_muda_is_active_para_false(session: Session) -> None:
    repo = AssetRepository(session)
    asset = _make_asset(session, "VALE3")

    repo.deactivate(asset.id)

    found = repo.get_by_id(asset.id)
    assert found is not None
    assert found.is_active is False


def test_deactivate_id_inexistente_levanta_value_error(session: Session) -> None:
    repo = AssetRepository(session)

    with pytest.raises(ValueError, match="não encontrado"):
        repo.deactivate(9999)


def test_deactivate_ja_inativo_levanta_value_error(session: Session) -> None:
    repo = AssetRepository(session)
    asset = _make_asset(session, "VALE3")
    repo.deactivate(asset.id)

    with pytest.raises(ValueError, match="já está inativo"):
        repo.deactivate(asset.id)
