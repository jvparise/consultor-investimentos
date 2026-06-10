"""Testes de integração do GoalService."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import ProjectionScenario
from consultor_investimentos.repositories.goal_repository import GoalRepository
from consultor_investimentos.services.goal_service import GoalService


@pytest.fixture
def meta_500k(session: Session):
    return GoalRepository(session).create(
        name="Meta 1 — R$ 500k",
        target_value=Decimal("500000"),
    )


@pytest.fixture
def meta_1M_com_prazo(session: Session):
    return GoalRepository(session).create(
        name="Meta 2 — R$ 1M",
        target_value=Decimal("1000000"),
        target_date=date(2035, 12, 31),
    )


def test_get_goal_progress_basico(session: Session, meta_500k) -> None:
    svc = GoalService(session)
    progress = svc.get_goal_progress(
        goal_id=meta_500k.id,
        current_portfolio_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
    )

    assert progress is not None
    assert progress.goal_id == meta_500k.id
    assert progress.goal_name == "Meta 1 — R$ 500k"
    assert progress.goal_target_value == Decimal("500000")
    assert progress.current_value == Decimal("210000")
    assert progress.remaining_value == Decimal("290000")


def test_goal_progress_pct_complete(session: Session, meta_500k) -> None:
    svc = GoalService(session)
    progress = svc.get_goal_progress(
        goal_id=meta_500k.id,
        current_portfolio_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
    )

    assert progress is not None
    # 210000 / 500000 * 100 = 42.00%
    assert progress.pct_complete == Decimal("42.00")


def test_goal_progress_nao_atingida(session: Session, meta_500k) -> None:
    svc = GoalService(session)
    progress = svc.get_goal_progress(
        goal_id=meta_500k.id,
        current_portfolio_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
    )

    assert progress is not None
    assert progress.is_achieved is False


def test_goal_progress_atingida(session: Session, meta_500k) -> None:
    svc = GoalService(session)
    progress = svc.get_goal_progress(
        goal_id=meta_500k.id,
        current_portfolio_value=Decimal("600000"),
        monthly_contribution=Decimal("0"),
    )

    assert progress is not None
    assert progress.is_achieved is True
    assert progress.pct_complete == Decimal("100.00")
    assert progress.remaining_value == Decimal("0")


def test_goal_progress_contem_todos_cenarios(session: Session, meta_500k) -> None:
    svc = GoalService(session)
    progress = svc.get_goal_progress(
        goal_id=meta_500k.id,
        current_portfolio_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
    )

    assert progress is not None
    assert set(progress.projections.keys()) == {
        ProjectionScenario.CONSERVATIVE,
        ProjectionScenario.MODERATE,
        ProjectionScenario.AGGRESSIVE,
    }


def test_goal_progress_cenario_moderado_34_meses(session: Session, meta_500k) -> None:
    """HP-12C: PV=210k, PMT=6k, FV=500k, 10% a.a. → 34 meses (ADR-015)."""
    svc = GoalService(session)
    progress = svc.get_goal_progress(
        goal_id=meta_500k.id,
        current_portfolio_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
    )

    assert progress is not None
    assert progress.projections[ProjectionScenario.MODERATE].months_to_goal == 34


def test_on_track_sem_prazo_e_sempre_true(session: Session, meta_500k) -> None:
    svc = GoalService(session)
    progress = svc.get_goal_progress(
        goal_id=meta_500k.id,
        current_portfolio_value=Decimal("1000"),
        monthly_contribution=Decimal("100"),
    )

    assert progress is not None
    assert progress.goal_target_date is None
    assert progress.on_track is True


def test_on_track_com_prazo_suficiente(session: Session, meta_1M_com_prazo) -> None:
    """Meta de R$1M até 2035 — cenário moderado: 76 meses ≈ 2032. Prazo suficiente."""
    svc = GoalService(session)
    progress = svc.get_goal_progress(
        goal_id=meta_1M_com_prazo.id,
        current_portfolio_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
    )

    assert progress is not None
    assert progress.on_track is True


def test_on_track_com_prazo_insuficiente(session: Session) -> None:
    """Meta de R$500k até amanhã — obviamente fora do prazo."""
    tomorrow = date.today().replace(day=date.today().day)
    from datetime import timedelta
    near_future = date.today() + timedelta(days=1)

    goal = GoalRepository(session).create(
        name="Meta impossível",
        target_value=Decimal("500000"),
        target_date=near_future,
    )

    svc = GoalService(session)
    progress = svc.get_goal_progress(
        goal_id=goal.id,
        current_portfolio_value=Decimal("1000"),
        monthly_contribution=Decimal("100"),
    )

    assert progress is not None
    assert progress.on_track is False


def test_get_all_goals_progress(session: Session, meta_500k, meta_1M_com_prazo) -> None:
    svc = GoalService(session)
    all_progress = svc.get_all_goals_progress(
        current_portfolio_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
    )

    assert len(all_progress) == 2
    names = {p.goal_name for p in all_progress}
    assert "Meta 1 — R$ 500k" in names
    assert "Meta 2 — R$ 1M" in names


def test_get_goal_progress_retorna_none_para_inexistente(session: Session) -> None:
    svc = GoalService(session)
    result = svc.get_goal_progress(
        goal_id=9999,
        current_portfolio_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
    )
    assert result is None


# ── Testes dos novos métodos de escrita ───────────────────────────────────────

def test_create_goal_sem_data(session: Session) -> None:
    GoalService(session).create_goal(name="Reserva", target_value=Decimal("30000"))
    goals = GoalRepository(session).get_active()
    assert any(g.name == "Reserva" for g in goals)


def test_create_goal_com_data(session: Session) -> None:
    GoalService(session).create_goal(
        name="Imóvel",
        target_value=Decimal("500000"),
        target_date=date(2028, 6, 1),
    )
    goals = GoalRepository(session).get_active()
    goal = next(g for g in goals if g.name == "Imóvel")
    assert goal.target_date == date(2028, 6, 1)


def test_create_goal_nome_vazio_levanta_value_error(session: Session) -> None:
    with pytest.raises(ValueError, match="vazio"):
        GoalService(session).create_goal(name="  ", target_value=Decimal("100000"))


def test_create_goal_valor_zero_levanta_value_error(session: Session) -> None:
    with pytest.raises(ValueError, match="maior que zero"):
        GoalService(session).create_goal(name="Meta inválida", target_value=Decimal("0"))


def test_update_goal_altera_nome(session: Session, meta_500k) -> None:
    GoalService(session).update_goal(meta_500k.id, name="Meta Renomeada")
    updated = GoalRepository(session).get_by_id(meta_500k.id)
    assert updated.name == "Meta Renomeada"


def test_update_goal_altera_valor(session: Session, meta_500k) -> None:
    GoalService(session).update_goal(meta_500k.id, target_value=Decimal("750000"))
    updated = GoalRepository(session).get_by_id(meta_500k.id)
    assert updated.target_value == Decimal("750000")


def test_update_goal_define_data(session: Session, meta_500k) -> None:
    GoalService(session).update_goal(meta_500k.id, target_date=date(2030, 1, 1))
    updated = GoalRepository(session).get_by_id(meta_500k.id)
    assert updated.target_date == date(2030, 1, 1)


def test_update_goal_limpa_target_date(session: Session, meta_1M_com_prazo) -> None:
    """Meta criada com data → update_goal(..., target_date=None) → data é None."""
    assert meta_1M_com_prazo.target_date is not None

    GoalService(session).update_goal(meta_1M_com_prazo.id, target_date=None)

    updated = GoalRepository(session).get_by_id(meta_1M_com_prazo.id)
    assert updated.target_date is None


def test_update_goal_sem_target_date_nao_altera_data(session: Session, meta_1M_com_prazo) -> None:
    """Não passar target_date mantém a data original inalterada."""
    data_original = meta_1M_com_prazo.target_date
    GoalService(session).update_goal(meta_1M_com_prazo.id, name="Novo Nome")
    updated = GoalRepository(session).get_by_id(meta_1M_com_prazo.id)
    assert updated.target_date == data_original


def test_update_goal_meta_inexistente_levanta_value_error(session: Session) -> None:
    with pytest.raises(ValueError, match="não encontrada"):
        GoalService(session).update_goal(9999, name="X")


def test_update_goal_meta_inativa_levanta_value_error(session: Session, meta_500k) -> None:
    GoalRepository(session).deactivate(meta_500k.id)
    with pytest.raises(ValueError, match="desativada"):
        GoalService(session).update_goal(meta_500k.id, name="Não deve funcionar")


def test_deactivate_goal(session: Session, meta_500k) -> None:
    GoalService(session).deactivate_goal(meta_500k.id)
    updated = GoalRepository(session).get_by_id(meta_500k.id)
    assert updated.is_active is False


def test_deactivate_goal_nao_aparece_em_get_active(session: Session, meta_500k) -> None:
    GoalService(session).deactivate_goal(meta_500k.id)
    active = GoalRepository(session).get_active()
    assert not any(g.id == meta_500k.id for g in active)


def test_reorder_goals(session: Session) -> None:
    repo = GoalRepository(session)
    g1 = repo.create(name="Primeira", target_value=Decimal("100000"))
    g2 = repo.create(name="Segunda", target_value=Decimal("200000"))
    g3 = repo.create(name="Terceira", target_value=Decimal("300000"))

    GoalService(session).reorder_goals([g3.id, g1.id, g2.id])

    active = repo.get_active()
    names = [g.name for g in active]
    assert names == ["Terceira", "Primeira", "Segunda"]
