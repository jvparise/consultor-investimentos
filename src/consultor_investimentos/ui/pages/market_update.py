"""Atualizar Cotações — preços via Yahoo Finance e câmbio via Banco Central."""
from datetime import date

import streamlit as st

from consultor_investimentos.config import AssetTrackingType, Currency
from consultor_investimentos.database.connection import get_db
from consultor_investimentos.services.market_data import MarketDataService
from consultor_investimentos.services.snapshot_service import SnapshotService
from consultor_investimentos.ui.components.metrics import fmt_brl_private, fmt_date_br
from consultor_investimentos.ui.state import PRIVACY_MODE

_SOURCE_BADGE = {"YAHOO": "🌐 Yahoo", "BCB": "🏦 BCB", "MANUAL": "✏️ Manual"}
_STATUS_ICON = {"updated": "✅", "skipped": "⏭", "error": "❌"}


def _fmt_price(price, currency: str) -> str:
    if price is None:
        return "—"
    symbol = "US$ " if currency == Currency.USD.value else ("€ " if currency == Currency.EUR.value else "R$ ")
    return fmt_brl_private(f"{symbol}{price:,.2f}")


st.title("📡 Atualizar Cotações")
st.caption(
    "Busca preços de ativos QUANTITY_PRICE via **Yahoo Finance** "
    "e cotações de câmbio via **Banco Central do Brasil (PTAX)**."
)

# ── Tabela de status atual ─────────────────────────────────────────────────────

with get_db() as session:
    svc = MarketDataService(session)
    price_status = svc.get_price_status()
    fx_rates = {}
    for currency in (Currency.USD, Currency.EUR):
        row = svc._fx_repo.get(currency)
        fx_rates[currency.value] = row

if price_status:
    st.subheader("Preços Atuais")
    rows = []
    for s in price_status:
        tracking = s["tracking_type"]
        is_qp = tracking == AssetTrackingType.QUANTITY_PRICE.value
        rows.append({
            "Ativo": s["ticker"],
            "Nome": s["name"],
            "Classe": s["asset_class"],
            "Tipo": "Q×P" if is_qp else "Valor",
            "Moeda": s["currency"],
            "Últ. Preço": _fmt_price(s["last_price"], s["currency"]),
            "Data": fmt_date_br(s["last_date"]) if s["last_date"] else "—",
            "Fonte": _SOURCE_BADGE.get(s["source"] or "", "—"),
            "Yahoo Ticker": s["yahoo_ticker"] or "—",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.info("Nenhum ativo ativo cadastrado.")

# ── Ações ──────────────────────────────────────────────────────────────────────

st.divider()
col1, col2 = st.columns([1, 1])

with col1:
    if st.button("📊 Atualizar tudo (Yahoo Finance)", use_container_width=True):
        with st.spinner("Buscando preços no Yahoo Finance…"):
            with get_db() as session:
                svc = MarketDataService(session)
                summary = svc.update_all_prices()
                SnapshotService(session).ensure_snapshot_for_today()

        st.session_state["market_update_summary"] = summary
        st.rerun()

with col2:
    if st.button("💱 Atualizar câmbio (BCB)", use_container_width=True):
        with st.spinner("Consultando PTAX no Banco Central…"):
            with get_db() as session:
                svc = MarketDataService(session)
                fx_results = svc.update_exchange_rates()

        st.session_state["fx_update_results"] = fx_results
        st.rerun()

# ── Resultado da última atualização de preços ──────────────────────────────────

if summary := st.session_state.get("market_update_summary"):
    st.subheader("Resultado da Última Atualização")
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Atualizados", summary.updated)
    c2.metric("⏭ Ignorados", summary.skipped)
    c3.metric("❌ Erros", summary.errors)

    detail = []
    for r in summary.results:
        icon = _STATUS_ICON.get(r.status, "?")
        detail.append({
            "": icon,
            "Ativo": r.ticker,
            "Yahoo Ticker": r.yahoo_ticker or "—",
            "Preço Anterior": fmt_brl_private(f"R$ {r.previous_price:,.4f}") if r.previous_price else "—",
            "Novo Preço": fmt_brl_private(f"R$ {r.new_price:,.4f}") if r.new_price else "—",
            "Mensagem": r.error_message or "",
        })
    st.dataframe(detail, use_container_width=True, hide_index=True)

# ── Câmbio ─────────────────────────────────────────────────────────────────────

st.divider()
st.subheader("Cotações de Câmbio")

if fx_results := st.session_state.get("fx_update_results"):
    for r in fx_results:
        icon = _STATUS_ICON.get(r.status, "?")
        msg = r.error_message or f"Atualizado para R$ {r.new_rate:,.4f}"
        st.write(f"{icon} **{r.currency}/BRL** — {msg}")

fx_rows = []
for currency_code, row in fx_rates.items():
    fx_rows.append({
        "Moeda": currency_code,
        "Cotação (BRL)": fmt_brl_private(f"R$ {row.rate:,.4f}") if row else "—",
        "Atualizado em": row.updated_at.strftime("%d/%m/%Y %H:%M") if row else "—",
    })
if fx_rows:
    st.dataframe(fx_rows, use_container_width=True, hide_index=True)
else:
    st.info("Nenhuma cotação cadastrada. Clique em 'Atualizar câmbio' ou cadastre manualmente em Configurações.")
