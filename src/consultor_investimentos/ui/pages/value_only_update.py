"""Atualizar Posições — bulk update de ativos VALUE_ONLY."""
from datetime import date
from decimal import Decimal, InvalidOperation

import streamlit as st

from consultor_investimentos.config import Currency
from consultor_investimentos.database.connection import get_db
from consultor_investimentos.services.exchange_rate_service import ExchangeRateService
from consultor_investimentos.services.portfolio_service import PortfolioService
from consultor_investimentos.services.snapshot_service import SnapshotService
from consultor_investimentos.ui.components.metrics import fmt_brl_private, fmt_date_br
from consultor_investimentos.ui.state import ERROR_MSG, SUCCESS_MSG

_PERIOD_OPTIONS = {"Mês atual": "month", "Ano atual": "year"}


def _parse_decimal(raw: str) -> str:
    """Aceita tanto 1000.12 (ponto decimal) quanto 1000,12 (vírgula decimal) e 1.000,12."""
    raw = raw.strip()
    has_dot = "." in raw
    has_comma = "," in raw
    if has_dot and has_comma:
        if raw.rindex(".") > raw.rindex(","):
            return raw.replace(",", "")
        return raw.replace(".", "").replace(",", ".")
    if has_comma:
        return raw.replace(",", ".")
    return raw


if msg := st.session_state.pop(SUCCESS_MSG, None):
    st.success(msg)
if msg := st.session_state.pop(ERROR_MSG, None):
    st.error(msg)

st.title("🔄 Atualizar Posições")
st.caption(
    "Informe o valor atual de cada posição e pressione **Enter** ou clique em **Salvar tudo**. "
    "Apenas ativos do tipo 'Valor Total' aparecem aqui."
)

today = date.today()
period_label = st.radio(
    "Base de comparação",
    options=list(_PERIOD_OPTIONS.keys()),
    horizontal=True,
    label_visibility="collapsed",
)
period_key = _PERIOD_OPTIONS[period_label]
period_start = date(today.year, today.month, 1) if period_key == "month" else date(today.year, 1, 1)

with get_db() as session:
    assets = PortfolioService(session).get_value_only_assets_for_update(period_start=period_start)
    fx_rates = ExchangeRateService(session).get_all_rates()

if not assets:
    st.info("Nenhum ativo do tipo 'Valor Total' cadastrado.")
    st.stop()

with st.form("bulk_update_form"):
    update_date = st.date_input("Data de referência", value=date.today())

    st.markdown("---")

    inputs: dict[int, str] = {}

    for asset in assets:
        currency = Currency(asset.get("currency", "BRL"))
        is_foreign = currency != Currency.BRL
        curr_sym = currency.value
        rate = fx_rates.get(currency, Decimal("1"))

        col_info, col_input = st.columns([3, 2])
        with col_info:
            last_price_native = asset["last_price"]
            base_price_native = asset["month_base_price"]
            base_date = asset["month_base_date"]
            base_dt = fmt_date_br(base_date) if base_date else "—"

            if is_foreign and last_price_native:
                last_val = f"{curr_sym} {float(last_price_native):,.2f} ({fmt_brl_private(last_price_native * rate)})"
            else:
                last_val = fmt_brl_private(last_price_native) if last_price_native else "—"

            if is_foreign and base_price_native:
                base_val = f"{curr_sym} {float(base_price_native):,.2f}"
            else:
                base_val = fmt_brl_private(base_price_native) if base_price_native else "—"

            if last_price_native and base_price_native and base_price_native > 0:
                variation = (last_price_native - base_price_native) / base_price_native * 100
                sign = "+" if variation >= 0 else ""
                var_str = f" ({sign}{float(variation):.1f}%)"
            else:
                var_str = ""

            st.markdown(f"**{asset['ticker']}** — {asset['name']}")
            base_label = "Base mês" if period_key == "month" else "Base ano"
            st.caption(f"{asset['asset_class']} · Atual: {last_val}{var_str} · {base_label}: {base_val} em {base_dt}")

        with col_input:
            placeholder = f"ex: {float(last_price_native):.2f}" if last_price_native else f"ex: 1000,00"
            inputs[asset["id"]] = st.text_input(
                f"Novo valor ({curr_sym})",
                placeholder=placeholder,
                key=f"bulk_{asset['id']}",
                label_visibility="collapsed",
            )

    st.markdown("---")
    submitted = st.form_submit_button("💾 Salvar tudo", type="primary")

if submitted:
    updates: list[tuple[int, date, Decimal]] = []
    errors: list[str] = []

    for asset in assets:
        raw = inputs.get(asset["id"], "").strip()
        if not raw:
            continue
        try:
            price = Decimal(_parse_decimal(raw))
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
                SnapshotService(session).ensure_snapshot_for_today()
            st.session_state[SUCCESS_MSG] = f"{count} posição(ões) atualizada(s) em {update_date.strftime('%d/%m/%Y')}."
            st.rerun()
        except Exception as e:
            st.session_state[ERROR_MSG] = f"Erro ao salvar: {e}"
            st.rerun()
