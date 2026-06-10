from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from consultor_investimentos.config import ProjectionScenario, SCENARIO_ANNUAL_RATES
from consultor_investimentos.repositories import GoalRepository
from consultor_investimentos.services.dto import GoalProgress, ProjectionResult
from consultor_investimentos.services.projection_service import ProjectionService

# Sentinela: distingue "não informado" (padrão) de "informado como None" (limpar campo)
_UNSET: Any = object()


class GoalService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._goal_repo = GoalRepository(session)
        self._projection_service = ProjectionService()

    # ── Leitura ──────────────────────────────────────────────────────────────

    def get_goal_progress(
        self,
        goal_id: int,
        current_portfolio_value: Decimal,
        monthly_contribution: Decimal,
    ) -> GoalProgress | None:
        goal = self._goal_repo.get_by_id(goal_id)
        if goal is None or not goal.is_active:
            return None
        return self._build_progress(goal, current_portfolio_value, monthly_contribution)

    def get_all_goals_progress(
        self,
        current_portfolio_value: Decimal,
        monthly_contribution: Decimal,
    ) -> list[GoalProgress]:
        goals = self._goal_repo.get_active()
        return [
            self._build_progress(goal, current_portfolio_value, monthly_contribution)
            for goal in goals
        ]

    # ── Escrita ──────────────────────────────────────────────────────────────

    def create_goal(
        self,
        name: str,
        target_value: Decimal,
        target_date: date | None = None,
    ) -> None:
        if not name.strip():
            raise ValueError("Nome da meta não pode ser vazio.")
        if target_value <= Decimal("0"):
            raise ValueError("Valor alvo deve ser maior que zero.")
        self._goal_repo.create(
            name=name.strip(),
            target_value=target_value,
            target_date=target_date,
        )

    def update_goal(
        self,
        goal_id: int,
        name: str | None = None,
        target_value: Decimal | None = None,
        target_date: Any = _UNSET,
    ) -> None:
        """Atualiza campos da meta.

        target_date=_UNSET (padrão): não altera a data.
        target_date=None: limpa a data-alvo (remove o prazo).
        target_date=<date>: define nova data-alvo.
        """
        goal = self._goal_repo.get_by_id(goal_id)
        if goal is None:
            raise ValueError(f"Meta com id={goal_id} não encontrada.")
        if not goal.is_active:
            raise ValueError("Não é possível editar uma meta desativada.")

        if name is not None:
            if not name.strip():
                raise ValueError("Nome da meta não pode ser vazio.")
            goal.name = name.strip()

        if target_value is not None:
            if target_value <= Decimal("0"):
                raise ValueError("Valor alvo deve ser maior que zero.")
            goal.target_value = target_value

        if target_date is not _UNSET:
            goal.target_date = target_date

        self._session.flush()

    def deactivate_goal(self, goal_id: int) -> None:
        self._goal_repo.deactivate(goal_id)

    def reorder_goals(self, ordered_ids: list[int]) -> None:
        self._goal_repo.reorder(ordered_ids)

    # ── Cálculo interno ──────────────────────────────────────────────────────

    def _build_progress(
        self,
        goal: object,
        current_value: Decimal,
        monthly_contribution: Decimal,
    ) -> GoalProgress:
        target = goal.target_value
        is_achieved = current_value >= target
        remaining = max(Decimal("0"), target - current_value)
        pct_complete = (
            min(current_value / target * 100, Decimal("100")).quantize(Decimal("0.01"))
            if target > 0
            else Decimal("100")
        )

        projections: dict[ProjectionScenario, ProjectionResult] = {
            scenario: self._projection_service.project_to_goal(
                current_value=current_value,
                monthly_contribution=monthly_contribution,
                target_value=target,
                annual_rate=rate,
            )
            for scenario, rate in SCENARIO_ANNUAL_RATES.items()
        }

        on_track = self._is_on_track(goal.target_date, is_achieved, projections)

        return GoalProgress(
            goal_id=goal.id,
            goal_name=goal.name,
            goal_target_value=target,
            goal_target_date=goal.target_date,
            current_value=current_value,
            remaining_value=remaining,
            pct_complete=pct_complete,
            is_achieved=is_achieved,
            on_track=on_track,
            projections=projections,
        )

    @staticmethod
    def _is_on_track(
        target_date: date | None,
        is_achieved: bool,
        projections: dict[ProjectionScenario, ProjectionResult],
    ) -> bool:
        if is_achieved:
            return True
        if target_date is None:
            return True

        moderate = projections.get(ProjectionScenario.MODERATE)
        if moderate is None or not moderate.is_achievable or moderate.months_to_goal is None:
            return False

        from datetime import date as date_class
        today = date_class.today()
        months_available = (
            (target_date.year - today.year) * 12 + (target_date.month - today.month)
        )
        return moderate.months_to_goal <= months_available
