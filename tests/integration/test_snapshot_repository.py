from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, SnapshotType
from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository

_DETAILS = [
    {"asset_class": AssetClass.EQUITY.value, "total_value": Decimal("100000"), "percentage": Decimal("50.00")},
    {"asset_class": AssetClass.FIXED_INCOME.value, "total_value": Decimal("100000"), "percentage": Decimal("50.00")},
]


def test_upsert_cria_snapshot_com_details(session: Session) -> None:
    repo = SnapshotRepository(session)
    snapshot = repo.upsert(
        snapshot_date=date(2026, 6, 9),
        total_value=Decimal("200000"),
        snapshot_type=SnapshotType.CALCULATED,
        details=_DETAILS,
    )

    assert snapshot.id is not None
    assert snapshot.total_value == Decimal("200000")
    assert snapshot.snapshot_type == SnapshotType.CALCULATED.value
    assert len(snapshot.details) == 2


def test_upsert_substitui_snapshot_existente_na_mesma_data(session: Session) -> None:
    repo = SnapshotRepository(session)
    repo.upsert(
        snapshot_date=date(2026, 6, 9),
        total_value=Decimal("200000"),
        snapshot_type=SnapshotType.CALCULATED,
        details=_DETAILS,
    )

    updated = repo.upsert(
        snapshot_date=date(2026, 6, 9),
        total_value=Decimal("210000"),
        snapshot_type=SnapshotType.MANUAL,
        details=[_DETAILS[0]],
    )

    assert updated.total_value == Decimal("210000")
    assert updated.snapshot_type == SnapshotType.MANUAL.value
    assert len(updated.details) == 1


def test_upsert_nao_duplica_snapshot(session: Session) -> None:
    repo = SnapshotRepository(session)
    repo.upsert(date(2026, 6, 9), Decimal("200000"), SnapshotType.CALCULATED, _DETAILS)
    repo.upsert(date(2026, 6, 9), Decimal("210000"), SnapshotType.MANUAL, _DETAILS)

    history = repo.get_history()
    assert len(history) == 1


def test_get_latest_retorna_mais_recente(session: Session) -> None:
    repo = SnapshotRepository(session)
    repo.upsert(date(2026, 1, 1), Decimal("190000"), SnapshotType.CALCULATED, _DETAILS)
    repo.upsert(date(2026, 6, 9), Decimal("210000"), SnapshotType.CALCULATED, _DETAILS)
    repo.upsert(date(2026, 3, 1), Decimal("200000"), SnapshotType.CALCULATED, _DETAILS)

    latest = repo.get_latest()

    assert latest is not None
    assert latest.snapshot_date == date(2026, 6, 9)
    assert latest.total_value == Decimal("210000")


def test_get_latest_retorna_none_sem_snapshots(session: Session) -> None:
    repo = SnapshotRepository(session)
    assert repo.get_latest() is None


def test_get_history_ordenado_por_data_asc(session: Session) -> None:
    repo = SnapshotRepository(session)
    repo.upsert(date(2026, 6, 1), Decimal("210000"), SnapshotType.CALCULATED, _DETAILS)
    repo.upsert(date(2026, 1, 1), Decimal("190000"), SnapshotType.CALCULATED, _DETAILS)
    repo.upsert(date(2026, 3, 1), Decimal("200000"), SnapshotType.CALCULATED, _DETAILS)

    history = repo.get_history()

    dates = [s.snapshot_date for s in history]
    assert dates == sorted(dates)


def test_get_history_com_filtro_de_periodo(session: Session) -> None:
    repo = SnapshotRepository(session)
    repo.upsert(date(2025, 12, 31), Decimal("180000"), SnapshotType.CALCULATED, _DETAILS)
    repo.upsert(date(2026, 3, 1), Decimal("200000"), SnapshotType.CALCULATED, _DETAILS)
    repo.upsert(date(2026, 6, 9), Decimal("210000"), SnapshotType.CALCULATED, _DETAILS)

    result = repo.get_history(start=date(2026, 1, 1), end=date(2026, 12, 31))

    assert len(result) == 2
    assert all(s.snapshot_date >= date(2026, 1, 1) for s in result)


def test_exists_for_date_retorna_true(session: Session) -> None:
    repo = SnapshotRepository(session)
    repo.upsert(date(2026, 6, 9), Decimal("210000"), SnapshotType.CALCULATED, _DETAILS)

    assert repo.exists_for_date(date(2026, 6, 9)) is True


def test_exists_for_date_retorna_false(session: Session) -> None:
    repo = SnapshotRepository(session)
    assert repo.exists_for_date(date(2026, 6, 9)) is False


def test_details_carregados_junto_com_snapshot(session: Session) -> None:
    repo = SnapshotRepository(session)
    repo.upsert(date(2026, 6, 9), Decimal("200000"), SnapshotType.CALCULATED, _DETAILS)

    snapshot = repo.get_by_date(date(2026, 6, 9))

    assert snapshot is not None
    assert len(snapshot.details) == 2
    classes = {d.asset_class for d in snapshot.details}
    assert AssetClass.EQUITY.value in classes
    assert AssetClass.FIXED_INCOME.value in classes


def test_snapshot_tipo_incomplete(session: Session) -> None:
    repo = SnapshotRepository(session)
    snapshot = repo.upsert(
        snapshot_date=date(2026, 6, 9),
        total_value=Decimal("150000"),
        snapshot_type=SnapshotType.INCOMPLETE,
        details=[_DETAILS[0]],
    )

    assert snapshot.snapshot_type == SnapshotType.INCOMPLETE.value
