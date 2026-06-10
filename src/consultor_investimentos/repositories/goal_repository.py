from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from consultor_investimentos.database.models import Goal


class GoalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, id: int) -> Goal | None:
        return self._session.get(Goal, id)

    def get_active(self) -> list[Goal]:
        return list(
            self._session.execute(
                select(Goal)
                .where(Goal.is_active == True)  # noqa: E712
                .order_by(Goal.order_index.asc())
            ).scalars().all()
        )

    def get_all(self) -> list[Goal]:
        return list(
            self._session.execute(
                select(Goal).order_by(Goal.order_index.asc())
            ).scalars().all()
        )

    def create(
        self,
        name: str,
        target_value: Decimal,
        target_date: date | None = None,
        description: str | None = None,
    ) -> Goal:
        if target_value <= Decimal("0"):
            raise ValueError("Valor alvo da meta deve ser maior que zero.")

        max_order = self._session.execute(
            select(func.max(Goal.order_index))
        ).scalar() or 0

        goal = Goal(
            name=name.strip(),
            target_value=target_value,
            target_date=target_date,
            description=description,
            order_index=max_order + 1,
        )
        self._session.add(goal)
        self._session.flush()
        return goal

    def update(
        self,
        id: int,
        name: str | None = None,
        target_value: Decimal | None = None,
        target_date: date | None = None,
        description: str | None = None,
    ) -> Goal:
        goal = self.get_by_id(id)
        if goal is None:
            raise ValueError(f"Meta com id={id} não encontrada.")

        if name is not None:
            goal.name = name.strip()
        if target_value is not None:
            if target_value <= Decimal("0"):
                raise ValueError("Valor alvo da meta deve ser maior que zero.")
            goal.target_value = target_value
        if target_date is not None:
            goal.target_date = target_date
        if description is not None:
            goal.description = description

        self._session.flush()
        return goal

    def deactivate(self, id: int) -> None:
        goal = self.get_by_id(id)
        if goal is None:
            raise ValueError(f"Meta com id={id} não encontrada.")
        if not goal.is_active:
            raise ValueError(f"Meta '{goal.name}' já está inativa.")
        goal.is_active = False
        self._session.flush()

    def reorder(self, ordered_ids: list[int]) -> None:
        """Atualiza order_index de cada meta na ordem fornecida. Operação atômica."""
        for index, goal_id in enumerate(ordered_ids, start=1):
            goal = self.get_by_id(goal_id)
            if goal is not None:
                goal.order_index = index
        self._session.flush()
