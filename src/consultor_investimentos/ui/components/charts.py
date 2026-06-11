"""Componentes de gráficos Plotly reutilizáveis."""
from decimal import Decimal

import plotly.graph_objects as go

from consultor_investimentos.config import ASSET_CLASS_COLORS, AssetClass, ProjectionScenario
from consultor_investimentos.services.dto import (
    AllocationData,
    ProjectionResult,
    SettingsDTO,
    SnapshotPoint,
)

_SCENARIO_COLORS = {
    ProjectionScenario.CONSERVATIVE: "#FF9800",
    ProjectionScenario.MODERATE: "#2196F3",
    ProjectionScenario.AGGRESSIVE: "#4CAF50",
}

_SCENARIO_LABELS = {
    ProjectionScenario.CONSERVATIVE: "Conservador (7% a.a.)",
    ProjectionScenario.MODERATE: "Moderado (10% a.a.)",
    ProjectionScenario.AGGRESSIVE: "Otimista (13% a.a.)",
}

_LAYOUT_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(size=12),
    margin=dict(l=10, r=10, t=10, b=10),
)


def allocation_donut(allocation: list[AllocationData]) -> go.Figure:
    if not allocation:
        return go.Figure()

    labels = [a.asset_class.value for a in allocation]
    values = [float(a.total_value) for a in allocation]
    colors = [ASSET_CLASS_COLORS.get(a.asset_class, "#9E9E9E") for a in allocation]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=colors),
        textinfo="label+percent",
        textposition="outside",
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        **_LAYOUT_DEFAULTS,
        showlegend=False,
        height=260,
    )
    return fig


def patrimony_area(history: list[SnapshotPoint]) -> go.Figure:
    if not history:
        return go.Figure()

    dates = [h.snapshot_date for h in history]
    values = [float(h.total_value) for h in history]

    span_days = (dates[-1] - dates[0]).days if len(dates) >= 2 else 0
    if span_days <= 60:
        tick_fmt = "%d/%b"
    elif span_days <= 365:
        tick_fmt = "%d/%b/%y"
    else:
        tick_fmt = "%b/%y"

    # Limita a 8 ticks distribuídos uniformemente entre os pontos reais
    step = max(1, len(dates) // 8)
    tick_dates = dates[::step]
    if dates[-1] not in tick_dates:
        tick_dates = tick_dates + [dates[-1]]
    tick_texts = [d.strftime(tick_fmt) for d in tick_dates]

    fig = go.Figure(go.Scatter(
        x=dates,
        y=values,
        fill="tozeroy",
        fillcolor="rgba(33,150,243,0.15)",
        line=dict(color="#2196F3", width=2),
        mode="lines+markers",
        marker=dict(size=5, color="#2196F3"),
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        **_LAYOUT_DEFAULTS,
        height=260,
        xaxis=dict(showgrid=False, tickvals=tick_dates, ticktext=tick_texts),
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(0,0,0,0.06)"),
    )
    return fig


def projection_lines(
    results: dict[ProjectionScenario, ProjectionResult],
    target_value: Decimal,
    target_label: str = "Meta",
) -> go.Figure:
    fig = go.Figure()

    for scenario, result in results.items():
        if not result.points:
            continue
        fig.add_trace(go.Scatter(
            x=[p.month for p in result.points],
            y=[float(p.value) for p in result.points],
            mode="lines",
            name=_SCENARIO_LABELS[scenario],
            line=dict(color=_SCENARIO_COLORS[scenario], width=2),
            hovertemplate=(
                f"<b>{_SCENARIO_LABELS[scenario]}</b><br>"
                "Mês %{x}<br>R$ %{y:,.2f}<extra></extra>"
            ),
        ))

    fig.add_hline(
        y=float(target_value),
        line_dash="dash",
        line_color="#F44336",
        line_width=1.5,
        annotation_text=f"  {target_label}",
        annotation_position="right",
        annotation_font_color="#F44336",
    )

    fig.update_layout(
        **{**_LAYOUT_DEFAULTS, "margin": dict(l=10, r=90, t=20, b=70)},
        height=320,
        xaxis=dict(title="Meses", showgrid=False),
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(0,0,0,0.06)"),
        legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5),
    )
    return fig


def allocation_gap_bars(
    allocation: list[AllocationData],
    settings: SettingsDTO,
) -> go.Figure:
    target_map: dict[AssetClass, float] = {
        AssetClass.EQUITY: float(settings.target_equity_pct),
        AssetClass.ETF: float(settings.target_etf_pct),
        AssetClass.FII_BRICK: float(settings.target_fii_brick_pct),
        AssetClass.FII_PAPER: float(settings.target_fii_paper_pct),
        AssetClass.FIXED_INCOME: float(settings.target_fixed_pct),
        AssetClass.INTERNATIONAL: float(settings.target_intl_pct),
        AssetClass.CRYPTO: float(settings.target_crypto_pct),
        AssetClass.OTHER: float(settings.target_other_pct),
    }
    actual_map: dict[AssetClass, float] = {
        a.asset_class: float(a.percentage) for a in allocation
    }

    classes = [
        c for c in AssetClass
        if target_map.get(c, 0) > 0 or actual_map.get(c, 0) > 0
    ]

    if not classes:
        return go.Figure()

    labels = [c.value for c in classes]
    actuals = [actual_map.get(c, 0.0) for c in classes]
    targets = [target_map.get(c, 0.0) for c in classes]
    colors = [ASSET_CLASS_COLORS.get(c, "#9E9E9E") for c in classes]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Alvo",
        y=labels,
        x=targets,
        orientation="h",
        marker=dict(color="rgba(0,0,0,0.08)"),
        hovertemplate="Alvo: %{x:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Real",
        y=labels,
        x=actuals,
        orientation="h",
        marker=dict(color=colors),
        hovertemplate="Real: %{x:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        **{**_LAYOUT_DEFAULTS, "margin": dict(l=10, r=20, t=10, b=40)},
        barmode="overlay",
        height=max(180, len(classes) * 36 + 60),
        xaxis=dict(title="%", range=[0, 100], showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
    )
    return fig
