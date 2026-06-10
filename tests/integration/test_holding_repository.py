from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.database.models import Asset
from consultor_investimentos.repositories.holding_repository import HoldingRepository


def test_upsert_cria_novo_registro(session: Session, asset_qp: Asset) -> None:
    repo = HoldingRepository(session)
    record = repo.upsert(asset_qp.id, date(2026, 6, 9), Decimal("62.50"))

    assert record.id is not None
    assert record.asset_id == asset_qp.id
    assert record.price == Decimal("62.50")
    assert record.price_date == date(2026, 6, 9)
    assert record.source == "MANUAL"


def test_upsert_atualiza_registro_existente_na_mesma_data(session: Session, asset_qp: Asset) -> None:
    repo = HoldingRepository(session)
    repo.upsert(asset_qp.id, date(2026, 6, 9), Decimal("62.50"))
    updated = repo.upsert(asset_qp.id, date(2026, 6, 9), Decimal("65.00"))

    assert updated.price == Decimal("65.00")
    assert len(repo.get_history(asset_qp.id)) == 1


def test_upsert_price_zero_levanta_value_error(session: Session, asset_qp: Asset) -> None:
    repo = HoldingRepository(session)

    with pytest.raises(ValueError, match="maior que zero"):
        repo.upsert(asset_qp.id, date(2026, 6, 9), Decimal("0"))


def test_upsert_price_negativo_levanta_value_error(session: Session, asset_qp: Asset) -> None:
    repo = HoldingRepository(session)

    with pytest.raises(ValueError, match="maior que zero"):
        repo.upsert(asset_qp.id, date(2026, 6, 9), Decimal("-10"))


def test_get_latest_retorna_mais_recente(session: Session, asset_qp: Asset) -> None:
    repo = HoldingRepository(session)
    repo.upsert(asset_qp.id, date(2026, 1, 1), Decimal("55.00"))
    repo.upsert(asset_qp.id, date(2026, 6, 1), Decimal("62.50"))
    repo.upsert(asset_qp.id, date(2026, 3, 1), Decimal("58.00"))

    latest = repo.get_latest(asset_qp.id)

    assert latest is not None
    assert latest.price_date == date(2026, 6, 1)
    assert latest.price == Decimal("62.50")


def test_get_latest_retorna_none_para_ativo_sem_preco(session: Session, asset_qp: Asset) -> None:
    repo = HoldingRepository(session)
    assert repo.get_latest(asset_qp.id) is None


def test_get_on_date_retorna_preco_correto(session: Session, asset_qp: Asset) -> None:
    repo = HoldingRepository(session)
    repo.upsert(asset_qp.id, date(2026, 6, 9), Decimal("62.50"))

    record = repo.get_on_date(asset_qp.id, date(2026, 6, 9))

    assert record is not None
    assert record.price == Decimal("62.50")


def test_get_on_date_retorna_none_para_data_sem_registro(session: Session, asset_qp: Asset) -> None:
    repo = HoldingRepository(session)
    repo.upsert(asset_qp.id, date(2026, 6, 9), Decimal("62.50"))

    assert repo.get_on_date(asset_qp.id, date(2026, 6, 8)) is None


def test_get_history_retorna_ordenado_por_data(session: Session, asset_qp: Asset) -> None:
    repo = HoldingRepository(session)
    repo.upsert(asset_qp.id, date(2026, 3, 1), Decimal("58.00"))
    repo.upsert(asset_qp.id, date(2026, 1, 1), Decimal("55.00"))
    repo.upsert(asset_qp.id, date(2026, 6, 1), Decimal("62.50"))

    history = repo.get_history(asset_qp.id)

    dates = [h.price_date for h in history]
    assert dates == sorted(dates)


def test_get_latest_all_active_exclui_inativos(
    session: Session, asset_qp: Asset, asset_vo: Asset
) -> None:
    from consultor_investimentos.repositories.asset_repository import AssetRepository

    holding_repo = HoldingRepository(session)
    holding_repo.upsert(asset_qp.id, date(2026, 6, 9), Decimal("62.50"))
    holding_repo.upsert(asset_vo.id, date(2026, 6, 9), Decimal("45000.00"))

    asset_repo = AssetRepository(session)
    asset_repo.deactivate(asset_vo.id)

    result = holding_repo.get_latest_all_active()

    asset_ids = [r.asset_id for r in result]
    assert asset_qp.id in asset_ids
    assert asset_vo.id not in asset_ids


def test_get_latest_all_active_retorna_apenas_mais_recente_por_ativo(
    session: Session, asset_qp: Asset
) -> None:
    repo = HoldingRepository(session)
    repo.upsert(asset_qp.id, date(2026, 1, 1), Decimal("55.00"))
    repo.upsert(asset_qp.id, date(2026, 6, 9), Decimal("62.50"))

    result = repo.get_latest_all_active()

    assert len(result) == 1
    assert result[0].price == Decimal("62.50")
