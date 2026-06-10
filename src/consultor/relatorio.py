"""Exibição do relatório no terminal usando rich."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .coleta import DadosMercado
from .analise import ResultadoAnalise

console = Console()


def exibir_cabecalho(data_coleta: str) -> None:
    console.print(Panel(
        Text("💼 Consultor de Investimentos Pessoal", justify="center", style="bold white"),
        subtitle=f"[dim]{data_coleta}[/dim]",
        style="bold blue",
        box=box.DOUBLE,
    ))


def exibir_macro(dados: DadosMercado) -> None:
    table = Table(title="Cenário Macroeconômico", box=box.ROUNDED, style="dim")
    table.add_column("Indicador", style="cyan")
    table.add_column("Valor", justify="right", style="bold")

    table.add_row("Selic (a.a.)", f"{dados.selic_anual:.2f}%")
    table.add_row("CDI (mensal)", f"{dados.cdi_mensal * 100:.4f}%")
    table.add_row("IPCA 12m", f"{dados.ipca_acumulado_12m:.2f}%")
    table.add_row("Dólar PTAX", f"R$ {dados.dolar_brl:.4f}")

    console.print(table)


def exibir_posicoes(
    valores_atuais: dict[str, float],
    valores_anteriores: dict[str, float],
) -> None:
    table = Table(title="Posições Atuais", box=box.ROUNDED)
    table.add_column("Ativo", style="cyan", min_width=30)
    table.add_column("Mês Anterior", justify="right")
    table.add_column("Atual", justify="right", style="bold")
    table.add_column("Variação", justify="right")
    table.add_column("%", justify="right")

    total_anterior = 0.0
    total_atual = 0.0

    for nome, atual in valores_atuais.items():
        anterior = valores_anteriores.get(nome, atual)
        variacao = atual - anterior
        pct = (variacao / anterior * 100) if anterior else 0

        cor_var = "green" if variacao >= 0 else "red"
        sinal = "+" if variacao >= 0 else ""

        table.add_row(
            nome,
            f"R$ {anterior:>12,.2f}",
            f"R$ {atual:>12,.2f}",
            f"[{cor_var}]{sinal}R$ {variacao:,.2f}[/{cor_var}]",
            f"[{cor_var}]{sinal}{pct:.2f}%[/{cor_var}]",
        )

        total_anterior += anterior
        total_atual += atual

    variacao_total = total_atual - total_anterior
    pct_total = (variacao_total / total_anterior * 100) if total_anterior else 0
    cor_total = "green" if variacao_total >= 0 else "red"
    sinal_total = "+" if variacao_total >= 0 else ""

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]R$ {total_anterior:>12,.2f}[/bold]",
        f"[bold]R$ {total_atual:>12,.2f}[/bold]",
        f"[bold {cor_total}]{sinal_total}R$ {variacao_total:,.2f}[/bold {cor_total}]",
        f"[bold {cor_total}]{sinal_total}{pct_total:.2f}%[/bold {cor_total}]",
    )

    console.print(table)


def exibir_analise(analise: ResultadoAnalise) -> None:
    if analise.resumo_carteira:
        console.print(Panel(analise.resumo_carteira, title="[bold]Resumo da Carteira[/bold]", style="blue"))

    if analise.analise_cenario:
        console.print(Panel(analise.analise_cenario, title="[bold]Análise do Cenário[/bold]", style="cyan"))

    if analise.sugestoes:
        console.print(Panel(analise.sugestoes, title="[bold]Sugestões de Rebalanceamento[/bold]", style="green"))

    if analise.alertas:
        console.print(Panel(analise.alertas, title="[bold]Alertas[/bold]", style="yellow"))


def exibir_relatorio_completo(
    dados_mercado: DadosMercado,
    valores_atuais: dict[str, float],
    valores_anteriores: dict[str, float],
    analise: ResultadoAnalise,
) -> None:
    exibir_cabecalho(dados_mercado.data_coleta)
    console.print()
    exibir_macro(dados_mercado)
    console.print()
    exibir_posicoes(valores_atuais, valores_anteriores)
    console.print()
    exibir_analise(analise)
