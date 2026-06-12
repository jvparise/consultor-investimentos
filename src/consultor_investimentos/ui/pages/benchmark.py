"""Benchmark — comparação da carteira contra índices de mercado."""
from datetime import date, timedelta
from decimal import Decimal

import plotly.graph_objects as go
import streamlit as st

from consultor_investimentos.config import Benchmark
from consultor_investimentos.database.connection import get_db
from consultor_investimentos.services.benchmark_service import BenchmarkService
from consultor_investimentos.services.dto import BenchmarkSeriesDTO, PortfolioVsBenchmarkDTO
from consultor_investimentos.services.market_data import MarketDataService
from consultor_investimentos.ui.components.metrics import fmt_date_br
from consultor_investimentos.ui.state import PRIVACY_MODE

_PERIODS = {
    "30 dias": 30,
    "90 dias": 90,
    "180 dias": 180,
    "1 ano": 365,
    "3 anos": 365 * 3,
    "Desde o início": None,
}

_COLORS = {
    "Carteira": "#2196F3",
    Benchmark.CDI.value: "#4CAF50",
    Benchmark.SELIC.value: "#8BC34A",
    Benchmark.IPCA.value: "#FF9800",
    Benchmark.IBOV.value: "#9C27B0",
    Benchmark.SP500.value: "#F44336",
}


def _build_chart(dto: PortfolioVsBenchmarkDTO) -> go.Figure:
    fig = go.Figure()
    for series in dto.all_series():
        if series.is_empty():
            continue
        color = _COLORS.get(series.name, "#607D8B")
        fig.add_trace(go.Scatter(
            x=[p.date for p in series.points],
            y=[float(p.value) for p in series.points],
            name=series.name,
            mode="lines",
            line={"color": color, "width": 2},
        ))

    fig.update_layout(
        yaxis_title="Base 100",
        xaxis_title=None,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        margin={"l": 40, "r": 20, "t": 40, "b": 40},
        height=420,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.1)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.1)")
    return fig


def _fmt_pct(value: Decimal | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value >= 0 else ""
    return f"{sign}{float(value):.2f}%"


def _metrics_table(dto: PortfolioVsBenchmarkDTO) -> None:
    portfolio_ret = dto.portfolio.rentability_pct()
    rows = []

    for series in dto.all_series():
        ret = series.rentability_pct()
        vs_cdi = None
        if ret is not None and dto.cdi.rentability_pct() is not None:
            vs_cdi = ret - dto.cdi.rentability_pct()

        rows.append({
            "Série": series.name,
            "Rentabilidade": _fmt_pct(ret),
            "vs CDI": _fmt_pct(vs_cdi) if series.name != Benchmark.CDI.value else "—",
            "Pontos": len(series.points),
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)


# ── Página ─────────────────────────────────────────────────────────────────────

st.title("📊 Benchmark")
st.caption("Comparação da evolução da carteira versus índices de mercado (base 100).")

# Período
period_label = st.radio(
    "Período",
    options=list(_PERIODS.keys()),
    index=3,
    horizontal=True,
    label_visibility="collapsed",
)
days = _PERIODS[period_label]
end_date = date.today()
if days is None:
    with get_db() as session:
        from consultor_investimentos.repositories.snapshot_repository import SnapshotRepository
        first = SnapshotRepository(session).get_history()
        start_date = first[0].snapshot_date if first else end_date - timedelta(days=365)
else:
    start_date = end_date - timedelta(days=days)

# Gera comparação
with get_db() as session:
    dto = BenchmarkService(session).compare_with_portfolio(start_date, end_date)

# Gráfico
has_data = any(not s.is_empty() for s in dto.all_series())
if has_data:
    st.plotly_chart(_build_chart(dto), use_container_width=True)
else:
    st.info(
        "Sem dados de benchmark para o período. "
        "Clique em **Atualizar benchmarks** para carregar os índices."
    )

# Métricas
if has_data:
    st.subheader("Rentabilidade no Período")
    _metrics_table(dto)

# Status e atualização
st.divider()
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔄 Atualizar benchmarks", use_container_width=True):
        with st.spinner("Atualizando índices…"):
            with get_db() as session:
                results = MarketDataService(session).update_benchmarks()
        msgs = []
        for name, count in results.items():
            if count == -1:
                msgs.append(f"❌ {name}: falha")
            elif count == 0:
                msgs.append(f"⏭ {name}: sem novos dados")
            else:
                msgs.append(f"✅ {name}: {count} registros")
        st.success(" · ".join(msgs))
        st.rerun()

with col1:
    with get_db() as session:
        status_rows = []
        for b in Benchmark:
            from consultor_investimentos.repositories.benchmark_repository import BenchmarkRepository
            latest = BenchmarkRepository(session).get_latest(b.value)
            status_rows.append({
                "Benchmark": b.value,
                "Último registro": fmt_date_br(latest.reference_date) if latest else "—",
            })
    st.dataframe(status_rows, use_container_width=True, hide_index=True)
