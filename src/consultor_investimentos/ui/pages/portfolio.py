"""Carteira / Portfólio — visão completa das posições."""
from datetime import date
from decimal import Decimal

import streamlit as st

from consultor_investimentos.config import AssetTrackingType
from consultor_investimentos.database.connection import get_db
from consultor_investimentos.services.portfolio_service import PortfolioService
from consultor_investimentos.services.settings_service import SettingsService
from consultor_investimentos.ui.state import CONFIRM_REACTIVATE_ASSET_ID
from consultor_investimentos.ui.components.charts import allocation_donut
from consultor_investimentos.ui.components.metrics import (
    fmt_brl,
    fmt_date_br,
    fmt_price,
    fmt_pct,
    fmt_qty,
)
from consultor_investimentos.ui.state import (
    CONFIRM_DEACTIVATE_ASSET_ID,
    ERROR_MSG,
    SUCCESS_MSG,
)

# ── Flash messages ────────────────────────────────────────────────────────────
if msg := st.session_state.pop(SUCCESS_MSG, None):
    st.success(msg)
if msg := st.session_state.pop(ERROR_MSG, None):
    st.error(msg)

# ── Carrega dados ─────────────────────────────────────────────────────────────
with get_db() as session:
    summary = PortfolioService(session).get_portfolio_summary()

st.title("💼 Carteira")

if not summary.positions and not summary.unpriced_tickers:
    st.info(
        "Nenhum ativo cadastrado. Adicione ativos e registre o saldo inicial em **Configurações**."
    )
    st.stop()

# ── Alerta de preços incompletos ──────────────────────────────────────────────
if summary.has_incomplete_prices:
    tickers_str = ", ".join(summary.unpriced_tickers)
    st.warning(
        f"⚠️ **Sem preço registrado:** {tickers_str}. "
        "Atualize os preços abaixo para incluir esses ativos nos totais."
    )

# ── KPIs do portfólio ─────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(
        label="💰 Patrimônio Investido",
        value=fmt_brl(summary.total_value),
        delta=f"{fmt_brl(summary.absolute_return, show_sign=True)} ({fmt_pct(summary.pct_return)})",
        delta_color="normal" if summary.absolute_return >= 0 else "inverse",
    )
with col2:
    st.metric(label="📊 Custo Total", value=fmt_brl(summary.total_cost))
with col3:
    st.metric(
        label="🏷️ Ativos",
        value=str(len(summary.positions)),
        delta=f"+{len(summary.unpriced_tickers)} sem preço" if summary.unpriced_tickers else None,
        delta_color="off",
    )

st.markdown("---")

# ── Gráfico de alocação ────────────────────────────────────────────────────────
if summary.allocation:
    col_chart, col_table = st.columns([1, 2])
    with col_chart:
        st.subheader("Alocação por Classe")
        st.plotly_chart(allocation_donut(summary.allocation), width="stretch")

    with col_table:
        st.subheader("Distribuição")
        for alloc in summary.allocation:
            st.markdown(
                f"**{alloc.asset_class.value}** — "
                f"{fmt_brl(alloc.total_value)} ({fmt_pct(alloc.percentage, show_sign=False)})"
            )
    st.markdown("---")

# ── Posições ──────────────────────────────────────────────────────────────────
st.subheader("Posições")

for pos in summary.positions:
    is_qp = pos.tracking_type == AssetTrackingType.QUANTITY_PRICE.value
    return_color = "🟢" if pos.absolute_return >= 0 else "🔴"
    price_date_str = fmt_date_br(pos.price_date)

    with st.expander(
        f"**{pos.ticker}** · {fmt_brl(pos.current_value)} "
        f"· {return_color} {fmt_pct(pos.pct_return)}"
        f" · {fmt_pct(pos.portfolio_pct, show_sign=False)} da carteira",
        expanded=False,
    ):
        # ── Dados da posição ──────────────────────────────────────────────
        d_col1, d_col2, d_col3, d_col4 = st.columns(4)
        with d_col1:
            st.markdown(f"**{pos.name}**")
            st.caption(f"{pos.asset_class.value}")
        with d_col2:
            if is_qp:
                st.metric("Qtd.", fmt_qty(pos.quantity))
                st.metric("P. Médio", fmt_price(pos.average_price))
            else:
                st.metric("Qtd.", "—")
                st.metric("P. Médio", "—")
        with d_col3:
            st.metric("Preço Atual", fmt_price(pos.current_price))
            st.caption(f"Data: {price_date_str}")
        with d_col4:
            st.metric("Custo Total", fmt_brl(pos.total_cost))
            st.metric("Retorno", fmt_brl(pos.absolute_return, show_sign=True))

        if pos.notes:
            st.caption(f"📝 {pos.notes}")

        st.markdown("---")

        # ── Atualizar preço ───────────────────────────────────────────────
        price_label = "preço unitário" if is_qp else "valor da posição"
        with st.expander(f"✏️ Atualizar {price_label}", expanded=False):
            with st.form(key=f"form_price_{pos.asset_id}"):
                new_date = st.date_input(
                    "Data",
                    value=date.today(),
                    key=f"price_date_{pos.asset_id}",
                )
                new_price_str = st.text_input(
                    f"Novo {price_label} (R$)",
                    placeholder="ex: 75.50",
                    key=f"price_val_{pos.asset_id}",
                )
                submitted = st.form_submit_button("Salvar", type="primary")

            if submitted:
                try:
                    new_price = Decimal(new_price_str.replace(",", "."))
                    if new_price <= 0:
                        raise ValueError("Valor deve ser positivo.")
                    with get_db() as session:
                        PortfolioService(session).update_asset_price(
                            asset_id=pos.asset_id,
                            price_date=new_date,
                            price=new_price,
                        )
                    st.session_state[SUCCESS_MSG] = (
                        f"{pos.ticker}: preço atualizado para {fmt_brl(new_price)} em {fmt_date_br(new_date)}."
                    )
                    st.rerun()
                except (ValueError, Exception) as e:
                    st.error(f"Erro: {e}")

        # ── Editar ativo ──────────────────────────────────────────────────
        with st.expander("🔧 Editar nome / observações", expanded=False):
            with st.form(key=f"form_edit_{pos.asset_id}"):
                new_name = st.text_input(
                    "Nome",
                    value=pos.name,
                    key=f"edit_name_{pos.asset_id}",
                )
                new_notes = st.text_area(
                    "Observações",
                    value=pos.notes or "",
                    key=f"edit_notes_{pos.asset_id}",
                    height=80,
                )
                save_edit = st.form_submit_button("Salvar alterações", type="primary")

            if save_edit:
                name_clean = new_name.strip() or None
                notes_clean = new_notes.strip() or None
                if not name_clean:
                    st.error("O nome não pode estar em branco.")
                else:
                    try:
                        with get_db() as session:
                            SettingsService(session).update_asset(
                                asset_id=pos.asset_id,
                                name=name_clean,
                                notes=notes_clean,
                            )
                        st.session_state[SUCCESS_MSG] = f"{pos.ticker}: dados atualizados."
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

        # ── Desativar ativo ───────────────────────────────────────────────
        confirm_key = CONFIRM_DEACTIVATE_ASSET_ID
        is_confirming = st.session_state.get(confirm_key) == pos.asset_id

        with st.expander("🗑️ Desativar ativo", expanded=is_confirming):
            st.caption(
                "Desativar remove o ativo da carteira e do dashboard. "
                "As transações históricas são preservadas."
            )
            if not is_confirming:
                if st.button(
                    f"Desativar {pos.ticker}",
                    key=f"deactivate_btn_{pos.asset_id}",
                    type="secondary",
                ):
                    st.session_state[confirm_key] = pos.asset_id
                    st.rerun()
            else:
                st.warning(f"⚠️ Confirma a desativação de **{pos.ticker} — {pos.name}**?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        "✅ Confirmar desativação",
                        type="primary",
                        key=f"confirm_deact_{pos.asset_id}",
                    ):
                        try:
                            with get_db() as session:
                                SettingsService(session).deactivate_asset(pos.asset_id)
                            st.session_state.pop(confirm_key, None)
                            st.session_state[SUCCESS_MSG] = f"{pos.ticker} desativado com sucesso."
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
                with c2:
                    if st.button("❌ Cancelar", key=f"cancel_deact_{pos.asset_id}"):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()

# ── Ativos sem preço ──────────────────────────────────────────────────────────
if summary.unpriced_tickers:
    st.markdown("---")
    st.subheader("📋 Ativos sem preço registrado")
    st.caption("Cadastre o preço para incluir estes ativos nos totais da carteira.")

    with get_db() as session:
        all_active = PortfolioService(session)._asset_repo.get_active()
        unpriced_assets = {a.ticker: a for a in all_active if a.ticker in summary.unpriced_tickers}

    for ticker in summary.unpriced_tickers:
        asset = unpriced_assets.get(ticker)
        with st.expander(f"**{ticker}** — sem preço", expanded=False):
            if asset is None:
                st.caption("Ativo não encontrado.")
                continue

            is_qp = AssetTrackingType(asset.tracking_type) == AssetTrackingType.QUANTITY_PRICE
            price_label = "Preço unitário" if is_qp else "Valor total da posição"

            with st.form(key=f"form_unpriced_{ticker}"):
                new_date = st.date_input("Data", value=date.today(), key=f"up_date_{ticker}")
                new_price_str = st.text_input(
                    f"{price_label} (R$)",
                    placeholder="ex: 75.50",
                    key=f"up_val_{ticker}",
                )
                submitted = st.form_submit_button("Registrar preço", type="primary")

            if submitted:
                try:
                    new_price = Decimal(new_price_str.replace(",", "."))
                    if new_price <= 0:
                        raise ValueError("Valor deve ser positivo.")
                    with get_db() as session:
                        PortfolioService(session).update_asset_price(
                            asset_id=asset.id,
                            price_date=new_date,
                            price=new_price,
                        )
                    st.session_state[SUCCESS_MSG] = (
                        f"{ticker}: preço registrado ({fmt_brl(new_price)} em {fmt_date_br(new_date)})."
                    )
                    st.rerun()
                except (ValueError, Exception) as e:
                    st.error(f"Erro: {e}")

# ── Ativos inativos ───────────────────────────────────────────────────────────
with get_db() as session:
    inactive_assets = SettingsService(session).get_inactive_assets()

if inactive_assets:
    st.markdown("---")
    st.subheader("📦 Ativos Inativos")
    st.caption("Ativos desativados. Reative para incluí-los novamente na carteira.")

    confirm_react_key = CONFIRM_REACTIVATE_ASSET_ID

    for asset in inactive_assets:
        asset_id = asset["id"]
        is_confirming = st.session_state.get(confirm_react_key) == asset_id

        with st.expander(
            f"**{asset['ticker']}** — {asset['name']} · {asset['asset_class']}",
            expanded=is_confirming,
        ):
            if not is_confirming:
                if st.button("🔄 Reativar", key=f"react_btn_{asset_id}"):
                    st.session_state[confirm_react_key] = asset_id
                    st.rerun()
            else:
                st.warning(f"Confirma a reativação de **{asset['ticker']} — {asset['name']}**?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        "✅ Confirmar reativação",
                        type="primary",
                        key=f"confirm_react_{asset_id}",
                    ):
                        try:
                            with get_db() as session:
                                SettingsService(session).reactivate_asset(asset_id)
                            st.session_state.pop(confirm_react_key, None)
                            st.session_state[SUCCESS_MSG] = f"{asset['ticker']} reativado com sucesso."
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
                with c2:
                    if st.button("❌ Cancelar", key=f"cancel_react_{asset_id}"):
                        st.session_state.pop(confirm_react_key, None)
                        st.rerun()
