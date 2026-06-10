"""Atualizar Posições — bulk update de ativos VALUE_ONLY."""
from datetime import date
from decimal import Decimal, InvalidOperation

import streamlit as st

from consultor_investimentos.database.connection import get_db
from consultor_investimentos.services.portfolio_service import PortfolioService
from consultor_investimentos.ui.components.metrics import fmt_brl, fmt_brl_private, fmt_date_br
from consultor_investimentos.ui.state import ERROR_MSG, SUCCESS_MSG

if msg := st.session_state.pop(SUCCESS_MSG, None):
    st.success(msg)
if msg := st.session_state.pop(ERROR_MSG, None):
    st.error(msg)

st.title("🔄 Atualizar Posições")
st.caption(
    "Informe o valor atual de cada posição e clique em **Salvar tudo**. "
    "Apenas ativos do tipo 'Valor Total' aparecem aqui."
)

with get_db() as session:
    assets = PortfolioService(session).get_value_only_assets_for_update()

if not assets:
    st.info("Nenhum ativo do tipo 'Valor Total' cadastrado.")
    st.stop()

update_date = st.date_input("Data de referência", value=date.today())

st.markdown("---")

inputs: dict[int, str] = {}

for asset in assets:
    col_info, col_input = st.columns([3, 2])
    with col_info:
        last_val = fmt_brl_private(asset["last_price"]) if asset["last_price"] else "—"
        last_dt = fmt_date_br(asset["last_date"]) if asset["last_date"] else "—"
        st.markdown(f"**{asset['ticker']}** — {asset['name']}")
        st.caption(f"{asset['asset_class']} · Último: {last_val} em {last_dt}")
    with col_input:
        inputs[asset["id"]] = st.text_input(
            "Novo valor (R$)",
            placeholder=f"ex: {float(asset['last_price']):.2f}" if asset["last_price"] else "ex: 1000,00",
            key=f"bulk_{asset['id']}",
            label_visibility="collapsed",
        )

st.markdown("---")

if st.button("💾 Salvar tudo", type="primary"):
    updates: list[tuple[int, date, Decimal]] = []
    errors: list[str] = []

    for asset in assets:
        raw = inputs.get(asset["id"], "").strip()
        if not raw:
            continue
        try:
            price = Decimal(raw.replace(".", "").replace(",", "."))
            if price <= 0:
                raise ValueError("Valor deve ser positivo.")
            updates.append((asset["id"], update_date, price))
        except (InvalidOperation, ValueError):
            errors.append(f"{asset['ticker']}: valor inválido '{raw}'")

    if errors:
        for err in errors:
            st.error(err)
    elif not updates:
        st.warning("Nenhum valor informado.")
    else:
        try:
            with get_db() as session:
                count = PortfolioService(session).bulk_update_prices(updates)
            st.session_state[SUCCESS_MSG] = f"{count} posição(ões) atualizada(s) em {update_date.strftime('%d/%m/%Y')}."
            st.rerun()
        except Exception as e:
            st.session_state[ERROR_MSG] = f"Erro ao salvar: {e}"
            st.rerun()
