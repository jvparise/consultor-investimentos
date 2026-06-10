"""Metas e Projeções — FIRE, metas do usuário e projeções financeiras."""
from datetime import date
from decimal import Decimal

import streamlit as st

from consultor_investimentos.config import ProjectionScenario, SCENARIO_LABELS
from consultor_investimentos.database.connection import get_db
from consultor_investimentos.services.goal_service import GoalService
from consultor_investimentos.services.portfolio_service import PortfolioService
from consultor_investimentos.services.projection_service import ProjectionService
from consultor_investimentos.services.settings_service import SettingsService
from consultor_investimentos.ui.components.charts import projection_lines
from consultor_investimentos.ui.components.metrics import fmt_brl, fmt_date_br, fmt_months, fmt_pct
from consultor_investimentos.ui.state import (
    CONFIRM_DEACTIVATE_GOAL_ID,
    EDIT_GOAL_ID,
    ERROR_MSG,
    GOAL_FORM_OPEN,
    SUCCESS_MSG,
)

# ── Flash messages ─────────────────────────────────────────────────────────────
if msg := st.session_state.pop(SUCCESS_MSG, None):
    st.success(msg)
if msg := st.session_state.pop(ERROR_MSG, None):
    st.error(msg)

st.title("🎯 Metas e Projeções")

# ── Carrega todos os dados em uma única sessão (P6) ────────────────────────────
with get_db() as session:
    settings = SettingsService(session).get_settings()
    summary  = PortfolioService(session).get_portfolio_summary()
    goals_raw = GoalService(session).get_all_goals_progress(
        current_portfolio_value=summary.total_value,
        monthly_contribution=settings.monthly_contribution,
    )

# Stateless — sem acesso ao banco
fire = ProjectionService().calculate_fire_metrics(
    current_value=summary.total_value,
    monthly_expenses=settings.monthly_expenses,
    monthly_contribution=settings.monthly_contribution,
)

# Partições da lista de metas
active_goals   = [g for g in goals_raw if not g.is_achieved]
achieved_goals = [g for g in goals_raw if g.is_achieved]

# ── Bloco FIRE ────────────────────────────────────────────────────────────────
if settings.monthly_expenses > 0:
    fire_icon = "🔥✅" if fire.is_achieved else "🔥"
    with st.container(border=True):
        st.markdown(f"#### {fire_icon} Independência Financeira (FIRE)")
        st.caption(
            f"Gastos mensais: {fmt_brl(settings.monthly_expenses)} × 300 = "
            f"**{fmt_brl(fire.fire_number)}** necessário"
        )

        pct = min(float(fire.pct_of_fire), 100.0)
        bar_text = (
            "✅ FIRE atingido! Parabéns!"
            if fire.is_achieved
            else f"{pct:.1f}% — faltam {fmt_brl(fire.fire_number - fire.current_value)}"
        )
        st.progress(pct / 100, text=bar_text)

        c1, c2, c3 = st.columns(3)
        for col, scenario in zip(
            (c1, c2, c3),
            (ProjectionScenario.CONSERVATIVE, ProjectionScenario.MODERATE, ProjectionScenario.AGGRESSIVE),
        ):
            label = SCENARIO_LABELS[scenario]
            months = fire.months_to_fire.get(scenario)
            col.metric(label, fmt_months(months))
else:
    st.info(
        "Configure seus **gastos mensais** em ⚙️ Configurações para ativar o cálculo de FIRE."
    )

st.markdown("---")

# ── Formulário de nova meta ────────────────────────────────────────────────────
st.subheader("Suas Metas")

if not st.session_state.get(GOAL_FORM_OPEN):
    if st.button("➕ Nova Meta", type="primary"):
        st.session_state[GOAL_FORM_OPEN] = True
        st.rerun()
else:
    with st.container(border=True):
        st.markdown("**Nova Meta**")
        with st.form("form_create_goal"):
            new_name    = st.text_input("Nome *", placeholder="Ex: Reserva de Emergência")
            new_value   = st.number_input("Valor alvo (R$) *", min_value=0.0, step=1000.0, format="%.2f")
            has_date    = st.checkbox("Definir data-alvo")
            new_date: date | None = None
            if has_date:
                new_date = st.date_input("Data-alvo", value=date.today())
            create_btn = st.form_submit_button("✅ Criar Meta", type="primary")
            cancel_btn = st.form_submit_button("❌ Cancelar")

        if cancel_btn:
            st.session_state.pop(GOAL_FORM_OPEN, None)
            st.rerun()

        if create_btn:
            try:
                with get_db() as session:
                    GoalService(session).create_goal(
                        name=new_name,
                        target_value=Decimal(str(new_value)),
                        target_date=new_date if has_date else None,
                    )
                st.session_state.pop(GOAL_FORM_OPEN, None)
                st.session_state[SUCCESS_MSG] = f"Meta '{new_name.strip()}' criada com sucesso."
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

# ── Lista de metas ativas (não atingidas) ─────────────────────────────────────
if not goals_raw:
    st.info("Nenhuma meta cadastrada. Crie sua primeira meta acima.")
else:
    for i, goal in enumerate(active_goals):
        edit_open    = st.session_state.get(EDIT_GOAL_ID) == goal.goal_id
        confirm_open = st.session_state.get(CONFIRM_DEACTIVATE_GOAL_ID) == goal.goal_id

        with st.container(border=True):
            # ── Cabeçalho com reordenação ─────────────────────────────────
            h_name, h_up, h_dn, h_spacer = st.columns([5, 0.4, 0.4, 2])
            on_track_icon = "✅" if goal.on_track else "⚠️"
            date_str = f" · Prazo: {fmt_date_br(goal.goal_target_date)}" if goal.goal_target_date else ""
            h_name.markdown(f"**{on_track_icon} {goal.goal_name}**{date_str}")

            if i > 0:
                if h_up.button("↑", key=f"up_{goal.goal_id}", help="Mover para cima"):
                    new_order = [g.goal_id for g in active_goals]
                    new_order[i - 1], new_order[i] = new_order[i], new_order[i - 1]
                    full_order = new_order + [g.goal_id for g in achieved_goals]
                    with get_db() as session:
                        GoalService(session).reorder_goals(full_order)
                    st.rerun()

            if i < len(active_goals) - 1:
                if h_dn.button("↓", key=f"dn_{goal.goal_id}", help="Mover para baixo"):
                    new_order = [g.goal_id for g in active_goals]
                    new_order[i], new_order[i + 1] = new_order[i + 1], new_order[i]
                    full_order = new_order + [g.goal_id for g in achieved_goals]
                    with get_db() as session:
                        GoalService(session).reorder_goals(full_order)
                    st.rerun()

            # ── Progresso ─────────────────────────────────────────────────
            pct = float(goal.pct_complete)
            bar_text = (
                f"{pct:.1f}% — "
                f"{fmt_brl(goal.current_value)} / {fmt_brl(goal.goal_target_value)} · "
                f"faltam {fmt_brl(goal.remaining_value)}"
            )
            st.progress(pct / 100, text=bar_text)

            # ── Cenários de projeção ───────────────────────────────────────
            m1, m2, m3 = st.columns(3)
            for col, scenario in zip(
                (m1, m2, m3),
                (ProjectionScenario.CONSERVATIVE, ProjectionScenario.MODERATE, ProjectionScenario.AGGRESSIVE),
            ):
                result = goal.projections.get(scenario)
                col.metric(
                    SCENARIO_LABELS[scenario],
                    fmt_months(result.months_to_goal if result else None),
                )

            # ── Ações ─────────────────────────────────────────────────────
            a1, a2, _ = st.columns([1, 1, 5])
            if a1.button("✏️ Editar", key=f"edit_btn_{goal.goal_id}"):
                if edit_open:
                    st.session_state.pop(EDIT_GOAL_ID, None)
                else:
                    st.session_state[EDIT_GOAL_ID] = goal.goal_id
                    st.session_state.pop(CONFIRM_DEACTIVATE_GOAL_ID, None)
                st.rerun()

            if a2.button("🗑️ Desativar", key=f"deact_btn_{goal.goal_id}"):
                if confirm_open:
                    st.session_state.pop(CONFIRM_DEACTIVATE_GOAL_ID, None)
                else:
                    st.session_state[CONFIRM_DEACTIVATE_GOAL_ID] = goal.goal_id
                    st.session_state.pop(EDIT_GOAL_ID, None)
                st.rerun()

            # ── Formulário de edição ──────────────────────────────────────
            if edit_open:
                st.markdown("---")
                with st.form(f"form_edit_{goal.goal_id}"):
                    e_name = st.text_input("Nome", value=goal.goal_name)
                    e_value = st.number_input(
                        "Valor alvo (R$)",
                        value=float(goal.goal_target_value),
                        min_value=0.01,
                        step=1000.0,
                        format="%.2f",
                    )

                    has_current_date = goal.goal_target_date is not None
                    if has_current_date:
                        remove_date = st.checkbox("Remover prazo (limpar data-alvo)")
                        e_date: date | None = None
                        if not remove_date:
                            e_date = st.date_input("Data-alvo", value=goal.goal_target_date)
                    else:
                        set_date = st.checkbox("Definir data-alvo")
                        e_date = None
                        if set_date:
                            e_date = st.date_input("Data-alvo", value=date.today())

                    save_btn = st.form_submit_button("💾 Salvar", type="primary")
                    cancel_edit = st.form_submit_button("❌ Cancelar")

                if cancel_edit:
                    st.session_state.pop(EDIT_GOAL_ID, None)
                    st.rerun()

                if save_btn:
                    try:
                        with get_db() as session:
                            svc = GoalService(session)
                            if has_current_date:
                                if remove_date:
                                    svc.update_goal(
                                        goal.goal_id,
                                        name=e_name,
                                        target_value=Decimal(str(e_value)),
                                        target_date=None,
                                    )
                                else:
                                    svc.update_goal(
                                        goal.goal_id,
                                        name=e_name,
                                        target_value=Decimal(str(e_value)),
                                        target_date=e_date,
                                    )
                            else:
                                if set_date:
                                    svc.update_goal(
                                        goal.goal_id,
                                        name=e_name,
                                        target_value=Decimal(str(e_value)),
                                        target_date=e_date,
                                    )
                                else:
                                    svc.update_goal(
                                        goal.goal_id,
                                        name=e_name,
                                        target_value=Decimal(str(e_value)),
                                    )
                        st.session_state.pop(EDIT_GOAL_ID, None)
                        st.session_state[SUCCESS_MSG] = f"Meta '{e_name.strip()}' atualizada."
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

            # ── Confirmação de desativação ────────────────────────────────
            if confirm_open:
                st.markdown("---")
                st.warning(
                    f"⚠️ Confirma a desativação de **{goal.goal_name}**? "
                    "A meta não aparecerá mais na lista."
                )
                c_yes, c_no, _ = st.columns([1, 1, 5])
                if c_yes.button("✅ Confirmar", key=f"confirm_deact_{goal.goal_id}", type="primary"):
                    try:
                        with get_db() as session:
                            GoalService(session).deactivate_goal(goal.goal_id)
                        st.session_state.pop(CONFIRM_DEACTIVATE_GOAL_ID, None)
                        st.session_state[SUCCESS_MSG] = f"Meta '{goal.goal_name}' desativada."
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                if c_no.button("❌ Cancelar", key=f"cancel_deact_{goal.goal_id}"):
                    st.session_state.pop(CONFIRM_DEACTIVATE_GOAL_ID, None)
                    st.rerun()

# ── Metas atingidas (ao fundo, badge de conquista) ────────────────────────────
if achieved_goals:
    st.markdown("---")
    st.subheader("🏆 Metas Atingidas")
    for goal in achieved_goals:
        with st.container(border=True):
            st.markdown(f"✅ **{goal.goal_name}** — {fmt_brl(goal.goal_target_value)}")
            st.progress(1.0, text="100% — Meta atingida!")
            a1, a2, _ = st.columns([1, 1, 5])
            if a1.button("🗑️ Desativar", key=f"deact_ach_{goal.goal_id}"):
                st.session_state[CONFIRM_DEACTIVATE_GOAL_ID] = goal.goal_id
                st.rerun()

st.markdown("---")

# ── Projeção Detalhada ─────────────────────────────────────────────────────────
st.subheader("📈 Projeção Detalhada")

# Monta opções do seletor: metas ativas (não atingidas) + FIRE (se configurado)
chart_options: list[tuple[str, dict | None]] = []
for goal in active_goals:
    chart_options.append((goal.goal_name, {"type": "goal", "goal": goal}))
if settings.monthly_expenses > 0:
    chart_options.append(("🔥 FIRE", {"type": "fire"}))

if not chart_options:
    if achieved_goals:
        st.success("🎉 Todas as metas foram atingidas!")
    else:
        st.info("Crie uma meta acima para ver as projeções.")
else:
    option_labels = [label for label, _ in chart_options]
    default_idx = 0

    selected_label = st.selectbox("Meta para projetar:", option_labels, index=default_idx)
    selected_data  = next(data for label, data in chart_options if label == selected_label)

    if selected_data["type"] == "goal":
        goal = selected_data["goal"]
        chart_results  = goal.projections
        chart_target   = goal.goal_target_value
        chart_label    = goal.goal_name
        current_val    = goal.current_value
        target_val_str = fmt_brl(goal.goal_target_value)
    else:
        chart_results  = fire.fire_projections
        chart_target   = fire.fire_number
        chart_label    = "FIRE"
        current_val    = fire.current_value
        target_val_str = fmt_brl(fire.fire_number)

    if chart_results:
        st.plotly_chart(
            projection_lines(
                results=chart_results,
                target_value=chart_target,
                target_label=chart_label,
            ),
            width="stretch",
        )

    # ── Premissas ──────────────────────────────────────────────────────────
    with st.expander("📋 Premissas da projeção", expanded=False):
        st.markdown(
            f"| Premissa | Valor |\n"
            f"|---|---|\n"
            f"| Patrimônio atual | {fmt_brl(current_val)} |\n"
            f"| Aporte mensal | {fmt_brl(settings.monthly_contribution)} |\n"
            f"| Alvo | {target_val_str} |\n"
            f"| Conservador | {SCENARIO_LABELS[ProjectionScenario.CONSERVATIVE]} |\n"
            f"| Moderado | {SCENARIO_LABELS[ProjectionScenario.MODERATE]} |\n"
            f"| Otimista | {SCENARIO_LABELS[ProjectionScenario.AGGRESSIVE]} |\n"
            f"| Período máximo | 600 meses (50 anos) |"
        )
        st.caption(
            "Aporte mensal configurado em ⚙️ Configurações. "
            "Altere lá para refletir mudanças no seu planejamento."
        )

    st.caption(
        "⚠️ **Projeção simplificada:** taxa de rentabilidade constante e aporte mensal fixo. "
        "Não considera inflação, impostos sobre ganho de capital ou variação de mercado. "
        "Use como referência de planejamento, não como garantia de resultado."
    )

    if settings.monthly_expenses > 0:
        st.caption(
            f"🔥 **Número FIRE** = gastos mensais ({fmt_brl(settings.monthly_expenses)}) × 300 "
            f"= {fmt_brl(fire.fire_number)}. "
            "Representa o patrimônio para viver de renda sem consumir o principal (regra dos 4%)."
        )
