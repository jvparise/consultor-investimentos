import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType
from consultor_investimentos.repositories.asset_repository import AssetRepository


def _make_asset(session: Session, ticker: str = "VALE3") -> object:
    repo = AssetRepository(session)
    return repo.create(
        ticker=ticker,
        name=f"Ativo {ticker}",
        asset_class=AssetClass.EQUITY,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )


def test_reactivate_muda_is_active_para_true(session: Session) -> None:
    repo = AssetRepository(session)
    asset = _make_asset(session, "VALE3")
    repo.deactivate(asset.id)

    repo.reactivate(asset.id)

    found = repo.get_by_id(asset.id)
    assert found is not None
    assert found.is_active is True


def test_reactivate_reaparece_em_get_active(session: Session) -> None:
    repo = AssetRepository(session)
    asset = _make_asset(session, "VALE3")
    repo.deactivate(asset.id)

    assert asset.ticker not in [a.ticker for a in repo.get_active()]

    repo.reactivate(asset.id)

    assert asset.ticker in [a.ticker for a in repo.get_active()]


def test_reactivate_some_de_get_inactive(session: Session) -> None:
    repo = AssetRepository(session)
    asset = _make_asset(session, "VALE3")
    repo.deactivate(asset.id)

    assert asset.ticker in [a.ticker for a in repo.get_inactive()]

    repo.reactivate(asset.id)

    assert asset.ticker not in [a.ticker for a in repo.get_inactive()]


def test_reactivate_preserva_historico(session: Session) -> None:
    repo = AssetRepository(session)
    asset = _make_asset(session, "PETR4")
    original_id = asset.id
    repo.deactivate(asset.id)
    repo.reactivate(asset.id)

    found = repo.get_by_id(original_id)
    assert found is not None
    assert found.ticker == "PETR4"
    assert found.name == "Ativo PETR4"


def test_reactivate_id_inexistente_levanta_value_error(session: Session) -> None:
    repo = AssetRepository(session)

    with pytest.raises(ValueError, match="não encontrado"):
        repo.reactivate(9999)


def test_reactivate_ja_ativo_levanta_value_error(session: Session) -> None:
    repo = AssetRepository(session)
    asset = _make_asset(session, "VALE3")

    with pytest.raises(ValueError, match="já está ativo"):
        repo.reactivate(asset.id)


def test_reactivate_nao_duplica_ticker(session: Session) -> None:
    repo = AssetRepository(session)
    asset = _make_asset(session, "VALE3")
    repo.deactivate(asset.id)
    repo.reactivate(asset.id)

    all_assets = repo.get_all()
    tickers = [a.ticker for a in all_assets]
    assert tickers.count("VALE3") == 1
