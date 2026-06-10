"""Testes numéricos do ProjectionService — valores validados contra HP-12C (ADR-015)."""
from decimal import Decimal

import pytest

from consultor_investimentos.config import ProjectionScenario
from consultor_investimentos.services.projection_service import ProjectionService

_svc = ProjectionService()


# --- Taxa mensal equivalente ---

def test_taxa_mensal_7_pct() -> None:
    r = _svc.monthly_rate(Decimal("0.07"))
    assert abs(r - Decimal("0.005654")) < Decimal("0.000001")


def test_taxa_mensal_10_pct() -> None:
    r = _svc.monthly_rate(Decimal("0.10"))
    assert abs(r - Decimal("0.007974")) < Decimal("0.000001")


def test_taxa_mensal_13_pct() -> None:
    r = _svc.monthly_rate(Decimal("0.13"))
    assert abs(r - Decimal("0.010236")) < Decimal("0.000001")


def test_taxa_mensal_zero() -> None:
    r = _svc.monthly_rate(Decimal("0"))
    assert r == Decimal("0")


# --- Projeção para meta ---

def test_projecao_meta_500k_moderado() -> None:
    """HP-12C: PV=210k, PMT=6k, FV=500k, i=0.7974% → n=34."""
    result = _svc.project_to_goal(
        current_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
        target_value=Decimal("500000"),
        annual_rate=Decimal("0.10"),
    )
    assert result.months_to_goal == 34
    assert result.is_achievable is True


def test_projecao_meta_1M_moderado() -> None:
    """HP-12C: PV=210k, PMT=6k, FV=1M, i=0.7974% → n=76."""
    result = _svc.project_to_goal(
        current_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
        target_value=Decimal("1000000"),
        annual_rate=Decimal("0.10"),
    )
    assert result.months_to_goal == 76
    assert result.is_achievable is True


def test_projecao_meta_ja_atingida() -> None:
    result = _svc.project_to_goal(
        current_value=Decimal("600000"),
        monthly_contribution=Decimal("6000"),
        target_value=Decimal("500000"),
        annual_rate=Decimal("0.10"),
    )
    assert result.months_to_goal == 0
    assert result.is_achievable is True
    assert len(result.points) == 1
    assert result.points[0].month == 0
    assert result.points[0].value == Decimal("600000")


def test_projecao_inatingivel_sem_aporte_sem_taxa() -> None:
    result = _svc.project_to_goal(
        current_value=Decimal("0"),
        monthly_contribution=Decimal("0"),
        target_value=Decimal("500000"),
        annual_rate=Decimal("0"),
    )
    assert result.months_to_goal is None
    assert result.is_achievable is False


def test_points_comecam_no_mes_zero_com_valor_atual() -> None:
    result = _svc.project_to_goal(
        current_value=Decimal("100000"),
        monthly_contribution=Decimal("5000"),
        target_value=Decimal("200000"),
        annual_rate=Decimal("0.10"),
    )
    assert result.points[0].month == 0
    assert result.points[0].value == Decimal("100000")


def test_points_crescem_monotonicamente_com_taxa_positiva() -> None:
    result = _svc.project_to_goal(
        current_value=Decimal("100000"),
        monthly_contribution=Decimal("1000"),
        target_value=Decimal("200000"),
        annual_rate=Decimal("0.10"),
    )
    values = [p.value for p in result.points]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


# --- Todos os cenários ---

def test_project_all_scenarios_retorna_tres_cenarios() -> None:
    results = _svc.project_all_scenarios(
        current_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
        target_value=Decimal("500000"),
    )
    assert set(results.keys()) == {
        ProjectionScenario.CONSERVATIVE,
        ProjectionScenario.MODERATE,
        ProjectionScenario.AGGRESSIVE,
    }


def test_cenario_otimista_atinge_mais_rapido_que_conservador() -> None:
    results = _svc.project_all_scenarios(
        current_value=Decimal("210000"),
        monthly_contribution=Decimal("6000"),
        target_value=Decimal("500000"),
    )
    n_conservador = results[ProjectionScenario.CONSERVATIVE].months_to_goal
    n_otimista = results[ProjectionScenario.AGGRESSIVE].months_to_goal
    assert n_otimista is not None
    assert n_conservador is not None
    assert n_otimista < n_conservador


# --- FIRE ---

def test_fire_number_gastos_2000() -> None:
    """R$ 2.000/mês × 300 = R$ 600.000."""
    metrics = _svc.calculate_fire_metrics(
        current_value=Decimal("210000"),
        monthly_expenses=Decimal("2000"),
        monthly_contribution=Decimal("6000"),
    )
    assert metrics.fire_number == Decimal("600000")


def test_fire_pct_atual_35_pct() -> None:
    """R$ 210.000 / R$ 600.000 = 35%."""
    metrics = _svc.calculate_fire_metrics(
        current_value=Decimal("210000"),
        monthly_expenses=Decimal("2000"),
        monthly_contribution=Decimal("6000"),
    )
    assert metrics.pct_of_fire == Decimal("35.00")


def test_fire_meses_moderado_43() -> None:
    """HP-12C: PV=210k, PMT=6k, FV=600k, i=0.7974% → n=43."""
    metrics = _svc.calculate_fire_metrics(
        current_value=Decimal("210000"),
        monthly_expenses=Decimal("2000"),
        monthly_contribution=Decimal("6000"),
    )
    assert metrics.months_to_fire[ProjectionScenario.MODERATE] == 43


def test_fire_ja_atingido() -> None:
    metrics = _svc.calculate_fire_metrics(
        current_value=Decimal("700000"),
        monthly_expenses=Decimal("2000"),
        monthly_contribution=Decimal("0"),
    )
    assert metrics.is_achieved is True
    assert all(v == 0 for v in metrics.months_to_fire.values())


def test_fire_gastos_zero_nao_divide_por_zero() -> None:
    metrics = _svc.calculate_fire_metrics(
        current_value=Decimal("210000"),
        monthly_expenses=Decimal("0"),
        monthly_contribution=Decimal("6000"),
    )
    assert metrics.fire_number == Decimal("0")
    assert metrics.is_achieved is True


# ── fire_projections (E1) ─────────────────────────────────────────────────────

def test_fire_metrics_contem_fire_projections() -> None:
    """FireMetrics deve incluir ProjectionResult completo para cada cenário (E1)."""
    from consultor_investimentos.services.dto import ProjectionResult
    metrics = _svc.calculate_fire_metrics(
        current_value=Decimal("210000"),
        monthly_expenses=Decimal("2000"),
        monthly_contribution=Decimal("6000"),
    )
    assert set(metrics.fire_projections.keys()) == {
        ProjectionScenario.CONSERVATIVE,
        ProjectionScenario.MODERATE,
        ProjectionScenario.AGGRESSIVE,
    }
    for result in metrics.fire_projections.values():
        assert isinstance(result, ProjectionResult)


def test_fire_projections_tem_pontos_para_grafico() -> None:
    """Cada ProjectionResult em fire_projections deve ter pontos para o gráfico."""
    metrics = _svc.calculate_fire_metrics(
        current_value=Decimal("210000"),
        monthly_expenses=Decimal("2000"),
        monthly_contribution=Decimal("6000"),
    )
    for result in metrics.fire_projections.values():
        assert len(result.points) > 0
        assert result.points[0].month == 0
        assert result.points[0].value == Decimal("210000")


def test_fire_projections_months_to_goal_coerente_com_months_to_fire() -> None:
    """fire_projections[scenario].months_to_goal == months_to_fire[scenario]."""
    metrics = _svc.calculate_fire_metrics(
        current_value=Decimal("210000"),
        monthly_expenses=Decimal("2000"),
        monthly_contribution=Decimal("6000"),
    )
    for scenario in ProjectionScenario:
        assert (
            metrics.fire_projections[scenario].months_to_goal
            == metrics.months_to_fire[scenario]
        )


def test_fire_projections_ja_atingido_months_zero() -> None:
    """Quando FIRE já atingido, fire_projections[scenario].months_to_goal == 0."""
    metrics = _svc.calculate_fire_metrics(
        current_value=Decimal("700000"),
        monthly_expenses=Decimal("2000"),
        monthly_contribution=Decimal("0"),
    )
    for result in metrics.fire_projections.values():
        assert result.months_to_goal == 0
        assert result.is_achievable is True
