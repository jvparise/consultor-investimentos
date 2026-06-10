from datetime import date
from decimal import Decimal

from consultor_investimentos.config import (
    FIRE_MULTIPLIER,
    MAX_PROJECTION_MONTHS,
    SCENARIO_ANNUAL_RATES,
    ProjectionScenario,
)
from consultor_investimentos.services.dto import (
    FireMetrics,
    ProjectionPoint,
    ProjectionResult,
)


class ProjectionService:
    """Serviço stateless de projeções financeiras. Não requer session de banco."""

    @staticmethod
    def monthly_rate(annual_rate: Decimal) -> Decimal:
        """Taxa mensal equivalente: r = (1 + taxa_anual)^(1/12) - 1."""
        return Decimal(str((1 + float(annual_rate)) ** (1 / 12) - 1))

    def project_to_goal(
        self,
        current_value: Decimal,
        monthly_contribution: Decimal,
        target_value: Decimal,
        annual_rate: Decimal,
    ) -> ProjectionResult:
        scenario = self._scenario_for_rate(annual_rate)
        r = self.monthly_rate(annual_rate)

        points: list[ProjectionPoint] = [ProjectionPoint(month=0, value=current_value)]

        if current_value >= target_value:
            return ProjectionResult(
                scenario=scenario,
                annual_rate=annual_rate,
                monthly_rate=r,
                months_to_goal=0,
                target_value=target_value,
                is_achievable=True,
                points=points,
            )

        value = current_value
        months_to_goal: int | None = None

        for month in range(1, MAX_PROJECTION_MONTHS + 1):
            value = value * (1 + r) + monthly_contribution
            points.append(ProjectionPoint(month=month, value=value))
            if value >= target_value and months_to_goal is None:
                months_to_goal = month
                break

        is_achievable = months_to_goal is not None

        return ProjectionResult(
            scenario=scenario,
            annual_rate=annual_rate,
            monthly_rate=r,
            months_to_goal=months_to_goal,
            target_value=target_value,
            is_achievable=is_achievable,
            points=points,
        )

    def project_all_scenarios(
        self,
        current_value: Decimal,
        monthly_contribution: Decimal,
        target_value: Decimal,
    ) -> dict[ProjectionScenario, ProjectionResult]:
        return {
            scenario: self.project_to_goal(
                current_value=current_value,
                monthly_contribution=monthly_contribution,
                target_value=target_value,
                annual_rate=rate,
            )
            for scenario, rate in SCENARIO_ANNUAL_RATES.items()
        }

    def calculate_fire_metrics(
        self,
        current_value: Decimal,
        monthly_expenses: Decimal,
        monthly_contribution: Decimal,
    ) -> FireMetrics:
        fire_number = monthly_expenses * FIRE_MULTIPLIER
        is_achieved = current_value >= fire_number

        if fire_number > 0:
            pct_of_fire = (current_value / fire_number * 100).quantize(Decimal("0.01"))
        else:
            pct_of_fire = Decimal("0")

        months_to_fire: dict[ProjectionScenario, int | None] = {}
        fire_projections: dict[ProjectionScenario, ProjectionResult] = {}

        for scenario, rate in SCENARIO_ANNUAL_RATES.items():
            result = self.project_to_goal(
                current_value=current_value,
                monthly_contribution=monthly_contribution,
                target_value=fire_number,
                annual_rate=rate,
            )
            fire_projections[scenario] = result
            months_to_fire[scenario] = result.months_to_goal

        return FireMetrics(
            monthly_expenses=monthly_expenses,
            fire_number=fire_number,
            current_value=current_value,
            pct_of_fire=pct_of_fire,
            is_achieved=is_achieved,
            months_to_fire=months_to_fire,
            fire_projections=fire_projections,
        )

    @staticmethod
    def _scenario_for_rate(annual_rate: Decimal) -> ProjectionScenario:
        for scenario, rate in SCENARIO_ANNUAL_RATES.items():
            if rate == annual_rate:
                return scenario
        return ProjectionScenario.MODERATE
