from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.repositories.goal_repository import GoalRepository


def test_create_goal(session: Session) -> None:
    repo = GoalRepository(session)
    goal = repo.create(name="Meta 1 — R$ 500k", target_value=Decimal("500000"))

    assert goal.id is not None
    assert goal.name == "Meta 1 — R$ 500k"
    assert goal.target_value == Decimal("500000")
    assert goal.is_active is True
    assert goal.order_index == 1


def test_create_atribui_order_index_sequencial(session: Session) -> None:
    repo = GoalRepository(session)
    g1 = repo.create(name="Meta 1", target_value=Decimal("500000"))
    g2 = repo.create(name="Meta 2", target_value=Decimal("1000000"))

    assert g1.order_index == 1
    assert g2.order_index == 2


def test_create_target_value_zero_levanta_value_error(session: Session) -> None:
    repo = GoalRepository(session)

    with pytest.raises(ValueError, match="maior que zero"):
        repo.create(name="Meta inválida", target_value=Decimal("0"))


def test_create_com_target_date(session: Session) -> None:
    repo = GoalRepository(session)
    goal = repo.create(
        name="Meta com prazo",
        target_value=Decimal("500000"),
        target_date=date(2027, 12, 31),
    )

    assert goal.target_date == date(2027, 12, 31)


def test_get_active_retorna_apenas_ativos_ordenados(session: Session) -> None:
    repo = GoalRepository(session)
    g1 = repo.create(name="Meta 1", target_value=Decimal("500000"))
    g2 = repo.create(name="Meta 2", target_value=Decimal("1000000"))
    repo.deactivate(g1.id)

    result = repo.get_active()

    assert len(result) == 1
    assert result[0].name == "Meta 2"


def test_get_all_inclui_inativos(session: Session) -> None:
    repo = GoalRepository(session)
    g1 = repo.create(name="Meta 1", target_value=Decimal("500000"))
    g2 = repo.create(name="Meta 2", target_value=Decimal("1000000"))
    repo.deactivate(g1.id)

    result = repo.get_all()

    assert len(result) == 2


def test_update_campos(session: Session) -> None:
    repo = GoalRepository(session)
    goal = repo.create(name="Meta antiga", target_value=Decimal("500000"))

    updated = repo.update(
        goal.id,
        name="Meta atualizada",
        target_value=Decimal("600000"),
        description="Nova descrição",
    )

    assert updated.name == "Meta atualizada"
    assert updated.target_value == Decimal("600000")
    assert updated.description == "Nova descrição"


def test_update_id_inexistente_levanta_value_error(session: Session) -> None:
    repo = GoalRepository(session)

    with pytest.raises(ValueError, match="não encontrada"):
        repo.update(9999, name="Qualquer")


def test_update_target_value_zero_levanta_value_error(session: Session) -> None:
    repo = GoalRepository(session)
    goal = repo.create(name="Meta", target_value=Decimal("500000"))

    with pytest.raises(ValueError, match="maior que zero"):
        repo.update(goal.id, target_value=Decimal("0"))


def test_deactivate_preserva_registro(session: Session) -> None:
    repo = GoalRepository(session)
    goal = repo.create(name="Meta", target_value=Decimal("500000"))

    repo.deactivate(goal.id)

    found = repo.get_by_id(goal.id)
    assert found is not None
    assert found.is_active is False


def test_deactivate_ja_inativa_levanta_value_error(session: Session) -> None:
    repo = GoalRepository(session)
    goal = repo.create(name="Meta", target_value=Decimal("500000"))
    repo.deactivate(goal.id)

    with pytest.raises(ValueError, match="já está inativa"):
        repo.deactivate(goal.id)


def test_reorder_atualiza_order_index(session: Session) -> None:
    repo = GoalRepository(session)
    g1 = repo.create(name="Meta 1", target_value=Decimal("500000"))
    g2 = repo.create(name="Meta 2", target_value=Decimal("1000000"))
    g3 = repo.create(name="Meta 3", target_value=Decimal("2000000"))

    repo.reorder([g3.id, g1.id, g2.id])

    assert repo.get_by_id(g3.id).order_index == 1
    assert repo.get_by_id(g1.id).order_index == 2
    assert repo.get_by_id(g2.id).order_index == 3


def test_get_active_ordenado_por_order_index_apos_reorder(session: Session) -> None:
    repo = GoalRepository(session)
    g1 = repo.create(name="Meta A", target_value=Decimal("500000"))
    g2 = repo.create(name="Meta B", target_value=Decimal("1000000"))

    repo.reorder([g2.id, g1.id])
    result = repo.get_active()

    assert result[0].name == "Meta B"
    assert result[1].name == "Meta A"
