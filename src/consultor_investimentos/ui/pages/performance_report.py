"""Relatório Mensal de Performance — valorização, rendimentos e resultado por classe."""
import calendar
import csv
import io
from datetime import date, datetime

import streamlit as st

from consultor_investimentos.config import ASSET_CLASS_COLORS
from consultor_investimentos.database.connection import get_db
from consultor_investimentos.services.dto import PerformanceReportDTO
from consultor_investimentos.services.performance_report_service import PerformanceReportService
from consultor_investimentos.ui.components.metrics import fmt_brl, fmt_brl_private, fmt_date_br

_MONTHS_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def _color_value(value: float) -> str:
    if value > 0:
        return "color: #4CAF50"
    if value < 0:
        return "color: #F44336"
    return ""


def _fmt_signed(value) -> str:
    if value is None:
        return "—"
    return fmt_brl(value, show_sign=True)


def _render_row(row, col_widths: list):
    cols = st.columns(col_widths)
    cols[0].write(f"**{row.ticker}**")
    cols[1].write(row.asset_name)

    if row.previous_price is not None:
        prev_text = fmt_brl_private(row.previous_price)
        if row.previous_price_date:
            prev_text += f" _{fmt_date_br(row.previous_price_date)}_"
    else:
        prev_text = "—"

    if row.current_price is not None:
        curr_text = fmt_brl_private(row.current_price)
        if row.current_price_date:
            curr_text += f" _{fmt_date_br(row.current_price_date)}_"
    else:
        curr_text = "—"

    cols[2].write(prev_text)
    cols[3].write(curr_text)

    app_str = fmt_brl(row.appreciation, show_sign=True)
    inc_str = fmt_brl(row.income, show_sign=True) if row.income else "—"
    res_str = fmt_brl(row.total_result, show_sign=True)

    color_app = _color_value(float(row.appreciation))
    color_res = _color_value(float(row.total_result))
    color_inc = _color_value(float(row.income))

    cols[4].markdown(f"<span style='{color_app}'>{app_str}</span>", unsafe_allow_html=True)
    cols[5].markdown(f"<span style='{color_inc}'>{inc_str}</span>", unsafe_allow_html=True)
    cols[6].markdown(f"<span style='{color_res}'>{res_str}</span>", unsafe_allow_html=True)


def _generate_csv(report: PerformanceReportDTO) -> bytes:
    with get_db() as session:
        rows = PerformanceReportService(session).to_csv_rows(report)

    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


# ── Cabeçalho ──────────────────────────────────────────────────────────────────
st.title("📈 Relatório Mensal de Performance")

today = date.today()

col_month, col_year, col_btn = st.columns([2, 1, 1])
with col_month:
    month = st.selectbox(
        "Mês",
        options=list(range(1, 13)),
        format_func=lambda m: _MONTHS_PT[m],
        index=today.month - 1,
    )
with col_year:
    year = st.number_input(
        "Ano",
        min_value=2000,
        max_value=today.year + 1,
        value=today.year,
        step=1,
    )
with col_btn:
    st.write("")
    st.write("")
    gerar = st.button("🔍 Gerar Relatório", type="primary", use_container_width=True)

if not gerar and "perf_report_cache" not in st.session_state:
    st.info("Selecione o mês e o ano e clique em **Gerar Relatório**.")
    st.stop()

if gerar:
    with st.spinner("Calculando..."):
        with get_db() as session:
            report = PerformanceReportService(session).generate(int(year), int(month))
    st.session_state["perf_report_cache"] = report
    st.session_state["perf_report_label"] = f"{_MONTHS_PT[int(month)]}/{int(year)}"

report: PerformanceReportDTO = st.session_state["perf_report_cache"]
report_label: str = st.session_state.get("perf_report_label", "")

if not report.classes:
    st.warning(f"Nenhum ativo ativo encontrado para {report_label}.")
    st.stop()

# ── Resumo geral ───────────────────────────────────────────────────────────────
st.subheader(f"Resultado — {report_label}")

c1, c2, c3 = st.columns(3)
c1.metric(
    "📈 Valorização Total",
    fmt_brl_private(report.total_appreciation),
    delta=None,
)
c2.metric(
    "💰 Rendimentos Totais",
    fmt_brl_private(report.total_income),
)
c3.metric(
    "🏆 Resultado Total",
    fmt_brl_private(report.total_result),
)

st.markdown("---")

# ── Tabela por classe ──────────────────────────────────────────────────────────
COL_WIDTHS = [1.2, 2.5, 1.5, 1.5, 1.4, 1.4, 1.4]
HEADERS = ["Ticker", "Ativo", "Preço Base", "Preço Atual", "Valorização", "Rendimentos", "Resultado"]

for cls_summary in report.classes:
    ac = cls_summary.asset_class
    color = ASSET_CLASS_COLORS.get(ac, "#607D8B")

    st.markdown(
        f"<h4 style='color:{color}; margin-bottom:4px'>{ac.value}</h4>",
        unsafe_allow_html=True,
    )

    # Cabeçalho
    header_cols = st.columns(COL_WIDTHS)
    for col, label in zip(header_cols, HEADERS):
        col.markdown(f"**{label}**")
    st.divider()

    for row in cls_summary.rows:
        _render_row(row, COL_WIDTHS)

    # Subtotal da classe
    sub_cols = st.columns(COL_WIDTHS)
    sub_cols[0].markdown("**Subtotal**")
    sub_cols[1].write("")
    sub_cols[2].write("")
    sub_cols[3].write("")

    app_color = _color_value(float(cls_summary.total_appreciation))
    inc_color = _color_value(float(cls_summary.total_income))
    res_color = _color_value(float(cls_summary.total_result))

    sub_cols[4].markdown(
        f"<span style='font-weight:bold;{app_color}'>{fmt_brl(cls_summary.total_appreciation, show_sign=True)}</span>",
        unsafe_allow_html=True,
    )
    sub_cols[5].markdown(
        f"<span style='font-weight:bold;{inc_color}'>{fmt_brl(cls_summary.total_income, show_sign=True)}</span>",
        unsafe_allow_html=True,
    )
    sub_cols[6].markdown(
        f"<span style='font-weight:bold;{res_color}'>{fmt_brl(cls_summary.total_result, show_sign=True)}</span>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

# ── Exportação CSV ─────────────────────────────────────────────────────────────
csv_bytes = _generate_csv(report)
filename = f"relatorio_performance_{report.year}_{report.month:02d}.csv"

st.download_button(
    label="⬇️ Exportar CSV",
    data=csv_bytes,
    file_name=filename,
    mime="text/csv",
)
