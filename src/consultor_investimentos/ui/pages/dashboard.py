"""Dashboard Principal — responde imediatamente às 4 perguntas essenciais:
1. Quanto tenho hoje?
2. Quanto falta para cada meta?
3. Estou no caminho certo?
4. Onde realizar o próximo aporte?
"""
import streamlit as st

from consultor_investimentos.config import AssetClass, ProjectionScenario
from consultor_investimentos.database.connection import get_db
from consultor_investimentos.services.goal_service import GoalService
from consultor_investimentos.services.portfolio_service import PortfolioService
from consultor_investimentos.services.projection_service import ProjectionService
from consultor_investimentos.services.settings_service import SettingsService
from consultor_investimentos.services.snapshot_service import SnapshotService
from consultor_investimentos.ui.components.charts import (
    allocation_donut,
    allocation_gap_bars,
    patrimony_area,
    projection_lines,
)
from consultor_investimentos.ui.components.metrics import (
    fmt_brl,
    fmt_months,
    fmt_pct,
)
from consultor_investimentos.ui.state import SUCCESS_MSG

# --- Flash message ---
if msg := st.session_state.pop(SUCCESS_MSG, None):
    st.success(msg)

# --- Carrega todos os dados num único contexto de sessão ---
with get_db() as session:
    settings = SettingsService(session).get_settings()
    summary = PortfolioService(session).get_portfolio_summary()
    goals_progress = GoalService(session).get_all_goals_progress(
        current_portfolio_value=summary.total_value,
        monthly_contribution=settings.monthly_contribution,
    )
    fire = ProjectionService().calculate_fire_metrics(
        current_value=summary.total_value,
        monthly_expenses=settings.monthly_expenses,
        monthly_contribution=settings.monthly_contribution,
    )
    history = SnapshotService(session).get_history()

# ── Tela de boas-vindas (sem ativos) ────────────────────────────────────────
if not summary.positions:
    st.title("📊 InvestorIA")
    st.markdown("---")
    st.info(
        "**Bem-vindo!** Você ainda não possui ativos cadastrados.\n\n"
        "Comece cadastrando seus ativos e registrando o saldo inicial em **Configurações**."
    )
    if st.button("⚙️ Ir para Configurações", type="primary"):
        st.switch_page("ui/pages/settings.py")
    st.stop()

# ── Cabeçalho ───────────────────────────────────────────────────────────────
st.title(f"📊 Dashboard")
st.caption(f"Olá, **{settings.user_name}** · {len(summary.positions)} ativo(s) na carteira")

if summary.has_incomplete_prices:
    st.warning(
        "⚠️ Um ou mais ativos estão sem preço atualizado. "
        "Os valores podem estar desatualizados. Atualize os preços em **Carteira**."
    )

st.markdown("---")

# ── Bloco 1: KPIs principais ─────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="💰 Patrimônio Total",
        value=fmt_brl(summary.total_value),
        delta=f"{fmt_brl(summary.absolute_return, show_sign=True)} ({fmt_pct(summary.pct_return)})",
        delta_color="normal" if summary.absolute_return >= 0 else "inverse",
    )

with col2:
    fire_label = "🔥 FIRE" + (" ✓" if fire.is_achieved else "")
    fire_months = fire.months_to_fire.get(ProjectionScenario.MODERATE)
    fire_delta = (
        "Atingido! Parabéns!"
        if fire.is_achieved
        else f"{fmt_months(fire_months)} (moderado)"
    )
    st.metric(
        label=fire_label,
        value=f"{float(fire.pct_of_fire):.1f}%",
        delta=fire_delta,
        delta_color="off",
    )

with col3:
    next_goal = next((g for g in goals_progress if not g.is_achieved), None)
    if next_goal:
        moderate_proj = next_goal.projections.get(ProjectionScenario.MODERATE)
        months_str = fmt_months(moderate_proj.months_to_goal if moderate_proj else None)
        on_track_icon = "✅" if next_goal.on_track else "⚠️"
        st.metric(
            label=f"🎯 Próxima Meta {on_track_icon}",
            value=fmt_brl(next_goal.goal_target_value),
            delta=f"{float(next_goal.pct_complete):.0f}% · {months_str}",
            delta_color="off",
        )
    elif goals_progress:
        st.metric(label="🎯 Metas", value="Todas atingidas!", delta="Parabéns! 🎉", delta_color="off")
    else:
        st.metric(label="🎯 Metas", value="—", delta="Nenhuma meta cadastrada", delta_color="off")

with col4:
    aporte = settings.monthly_contribution
    if aporte > 0:
        st.metric(
            label="📥 Aporte Mensal",
            value=fmt_brl(aporte),
            delta=f"Gastos: {fmt_brl(settings.monthly_expenses)}/mês",
            delta_color="off",
        )
    else:
        st.metric(label="📥 Aporte Mensal", value="Não configurado", delta="Configure em ⚙️", delta_color="off")

st.markdown("---")

# ── Bloco 2: Gráficos lado a lado ────────────────────────────────────────────
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("Alocação Atual")
    st.plotly_chart(allocation_donut(summary.allocation), width="stretch")

with col_right:
    st.subheader("Evolução Patrimonial")
    if len(history) >= 2:
        st.plotly_chart(patrimony_area(history), width="stretch")
    else:
        st.info(
            "O gráfico de evolução aparecerá após o sistema registrar "
            "pelo menos 2 snapshots patrimoniais (um por dia de uso)."
        )

st.markdown("---")

# ── Bloco 3: Onde investir o próximo aporte ───────────────────────────────────
st.subheader("💡 Onde Investir o Próximo Aporte?")

target_sum = sum([
    settings.target_equity_pct,
    settings.target_fii_pct,
    settings.target_fixed_pct,
    settings.target_intl_pct,
    settings.target_crypto_pct,
    settings.target_other_pct,
])

if target_sum == 0:
    st.info("Configure sua **alocação alvo** em ⚙️ Configurações para receber sugestões de aporte.")
else:
    target_map = {
        AssetClass.EQUITY: settings.target_equity_pct,
        AssetClass.FII: settings.target_fii_pct,
        AssetClass.FIXED_INCOME: settings.target_fixed_pct,
        AssetClass.INTERNATIONAL: settings.target_intl_pct,
        AssetClass.CRYPTO: settings.target_crypto_pct,
        AssetClass.OTHER: settings.target_other_pct,
    }
    actual_map = {a.asset_class: a.percentage for a in summary.allocation}

    gaps = [
        (cls, float(target_map[cls] - actual_map.get(cls, 0)))
        for cls in AssetClass
        if float(target_map.get(cls, 0)) > 0
        and float(target_map[cls] - actual_map.get(cls, 0)) > 0
    ]
    gaps.sort(key=lambda x: x[1], reverse=True)

    if gaps:
        most_underweight_class, gap_pct = gaps[0]
        col_tip, col_chart = st.columns([1, 2])
        with col_tip:
            st.info(
                f"**{most_underweight_class.value}** está **{gap_pct:.1f}%** abaixo do alvo.\n\n"
                f"Considere direcionar seu próximo aporte de "
                f"**{fmt_brl(settings.monthly_contribution)}** para esta classe."
            )
            st.caption("Alocação completa →")
        with col_chart:
            st.plotly_chart(allocation_gap_bars(summary.allocation, settings), width="stretch")
    else:
        st.success("✅ Alocação alinhada com a estratégia definida. Continue aportando proporcionalmente.")
        st.plotly_chart(allocation_gap_bars(summary.allocation, settings), width="stretch")

st.markdown("---")

# ── Bloco 4: Progresso das Metas ──────────────────────────────────────────────
st.subheader("🎯 Progresso das Metas")

if not goals_progress:
    st.info("Nenhuma meta cadastrada. Crie sua primeira meta em **Metas**.")
else:
    # FIRE (sempre exibido se gastos > 0)
    if settings.monthly_expenses > 0:
        with st.container(border=True):
            fire_col1, fire_col2 = st.columns([3, 1])
            with fire_col1:
                st.markdown(f"**🔥 FIRE — Independência Financeira**")
                st.caption(
                    f"Patrimônio alvo: {fmt_brl(fire.fire_number)} "
                    f"(gastos {fmt_brl(settings.monthly_expenses)}/mês × 300)"
                )
                pct_val = min(float(fire.pct_of_fire), 100.0)
                st.progress(pct_val / 100, text=f"{pct_val:.1f}% · Faltam {fmt_brl(fire.fire_number - fire.current_value)}")
            with fire_col2:
                fire_moderate = fire.months_to_fire.get(ProjectionScenario.MODERATE)
                st.metric("Moderado", fmt_months(fire_moderate))

    # Metas do usuário
    for goal in goals_progress:
        on_track_icon = "✅" if goal.on_track else "⚠️"
        with st.container(border=True):
            g_col1, g_col2, g_col3 = st.columns([3, 1, 1])
            with g_col1:
                achieved_badge = " ✓" if goal.is_achieved else ""
                st.markdown(f"**{on_track_icon} {goal.goal_name}{achieved_badge}**")
                if goal.goal_target_date:
                    st.caption(f"Prazo: {goal.goal_target_date.strftime('%d/%m/%Y')} · Alvo: {fmt_brl(goal.goal_target_value)}")
                else:
                    st.caption(f"Sem prazo definido · Alvo: {fmt_brl(goal.goal_target_value)}")
                pct = min(float(goal.pct_complete), 100.0)
                bar_text = f"{pct:.1f}% · Faltam {fmt_brl(goal.remaining_value)}" if not goal.is_achieved else "Meta atingida!"
                st.progress(pct / 100, text=bar_text)
            with g_col2:
                moderate = goal.projections.get(ProjectionScenario.MODERATE)
                st.metric("Moderado", fmt_months(moderate.months_to_goal if moderate else None))
            with g_col3:
                conservative = goal.projections.get(ProjectionScenario.CONSERVATIVE)
                st.metric("Conservador", fmt_months(conservative.months_to_goal if conservative else None))

st.markdown("---")

# ── Bloco 5: Projeção até a próxima meta ──────────────────────────────────────
st.subheader("📈 Projeção Patrimonial")

projection_goal = next((g for g in goals_progress if not g.is_achieved), None)

if projection_goal and projection_goal.projections:
    st.plotly_chart(
        projection_lines(
            results=projection_goal.projections,
            target_value=projection_goal.goal_target_value,
            target_label=projection_goal.goal_name,
        ),
        width="stretch",
    )
elif fire.monthly_expenses > 0 and not fire.is_achieved:
    st.plotly_chart(
        projection_lines(
            results=fire.fire_projections,
            target_value=fire.fire_number,
            target_label="FIRE",
        ),
        width="stretch",
    )
else:
    st.success("🎉 Todas as metas e o FIRE foram atingidos!")

st.caption(
    "⚠️ Projeção baseada em taxa de rentabilidade constante e aporte mensal fixo. "
    "Não considera inflação, impostos ou variação de mercado."
)
