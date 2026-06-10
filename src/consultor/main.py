"""CLI principal do consultor de investimentos."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv, find_dotenv
from rich.console import Console
from rich.prompt import Confirm, FloatPrompt

from .coleta import coletar_todos_dados, calcular_valor_cdb
from .analise import analisar_carteira
from .relatorio import exibir_relatorio_completo, console

load_dotenv(Path.cwd() / ".env", override=False)

app = typer.Typer(help="Consultor de investimentos pessoal")

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "carteira.json"


def carregar_carteira() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def salvar_carteira(carteira: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(carteira, f, ensure_ascii=False, indent=2)


def coletar_valores_manuais(carteira: dict, dados_mercado) -> dict[str, float]:
    """Solicita ao usuário os valores dos ativos que não podem ser coletados automaticamente."""
    console.print("\n[bold yellow]Informe os valores atuais dos ativos manuais:[/bold yellow]")
    valores: dict[str, float] = {}

    ativos = carteira.get("ativos", {})

    # Ativos manuais (CRAs, debêntures, Nubank)
    for nome, info in ativos.get("manual", {}).items():
        valor = FloatPrompt.ask(f"  {nome}", default=info.get("valor_atual", 0.0))
        valores[nome] = valor
        info["valor_atual"] = valor

    # Fundos (XP FIRF, AZ QUEST, Trend)
    for nome, info in ativos.get("fundos", {}).items():
        valor = FloatPrompt.ask(f"  {nome}", default=info.get("valor_atual", 0.0))
        valores[nome] = valor
        info["valor_atual"] = valor

    # CDBs com cálculo baseado em CDI
    for nome, info in ativos.get("renda_fixa", {}).items():
        if info.get("tipo") in ("cdb_cdi",) and info.get("valor_investido", 0) > 0:
            novo = calcular_valor_cdb(
                info["valor_investido"],
                info.get("percentual_cdi", 1.0),
                dados_mercado.cdi_mensal,
            )
            valores[nome] = novo
        else:
            valor = FloatPrompt.ask(f"  {nome}", default=info.get("valor_atual", 0.0))
            valores[nome] = valor

    return valores


@app.command()
def analisar(
    atualizar_sheets: Annotated[bool, typer.Option("--sheets/--no-sheets", help="Atualizar Google Sheets")] = False,
    so_relatorio: Annotated[bool, typer.Option("--so-relatorio", help="Exibe relatório sem chamar Claude")] = False,
) -> None:
    """Coleta dados, analisa a carteira e exibe o relatório."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key and not so_relatorio:
        console.print("[red]Erro: ANTHROPIC_API_KEY não definida no .env[/red]")
        raise typer.Exit(1)

    carteira = carregar_carteira()

    # Lê planilha sempre (para fallback de preços e comparação)
    valores_anteriores: dict[str, float] = {}
    try:
        from .planilha import conectar, ler_ultimo_mes
        credentials_path = str(Path(__file__).parent.parent.parent / "credentials" / "service_account.json")
        gc = conectar(credentials_path)
        cfg_sheets = carteira.get("google_sheets", {})
        valores_anteriores = ler_ultimo_mes(gc, cfg_sheets["spreadsheet_id"], cfg_sheets["aba_atual"])
        console.print("[green]Planilha lida com sucesso.[/green]")
    except Exception as e:
        console.print(f"[yellow]Aviso: não foi possível ler o Google Sheets: {e}[/yellow]")

    console.print("[cyan]Coletando dados de mercado...[/cyan]")
    dados_mercado = coletar_todos_dados(carteira, valores_anteriores)

    # Valores manuais primeiro (fundos, CRAs, CDBs, Nubank)
    valores_manuais = coletar_valores_manuais(carteira, dados_mercado)

    # Ordem de exibição: FIIs → fundos → renda fixa → manuais → ações
    valores_atuais: dict[str, float] = {}
    valores_atuais.update(dados_mercado.precos_fiis)
    valores_atuais.update(valores_manuais)
    valores_atuais.update(dados_mercado.precos_acoes_us)
    salvar_carteira(carteira)

    analise = None
    if not so_relatorio:
        console.print("[cyan]Consultando Claude...[/cyan]")
        from .analise import ResultadoAnalise
        analise = analisar_carteira(carteira, dados_mercado, valores_anteriores, valores_atuais, api_key)
    else:
        from .analise import ResultadoAnalise
        analise = ResultadoAnalise("", "", "", "")

    exibir_relatorio_completo(dados_mercado, valores_atuais, valores_anteriores, analise)

    if atualizar_sheets and valores_anteriores:
        if Confirm.ask("\nAtualizar Google Sheets com os valores de hoje?"):
            try:
                from .planilha import conectar, escrever_mes
                from datetime import datetime
                credentials_path = str(Path(__file__).parent.parent.parent / "credentials" / "service_account.json")
                gc = conectar(credentials_path)
                cfg_sheets = carteira.get("google_sheets", {})
                nome_mes = datetime.now().strftime("%B/%Y").capitalize()

                linhas = []
                for nome, atual in sorted(valores_atuais.items()):
                    anterior = valores_anteriores.get(nome, atual)
                    variacao = atual - anterior
                    pct = (variacao / anterior * 100) if anterior else 0
                    linhas.append([nome, anterior, atual, variacao, 0.0, pct])

                escrever_mes(gc, cfg_sheets["spreadsheet_id"], cfg_sheets["aba_atual"], nome_mes, linhas)
                console.print("[green]Planilha atualizada com sucesso![/green]")
            except Exception as e:
                console.print(f"[red]Erro ao atualizar planilha: {e}[/red]")


@app.command()
def configurar() -> None:
    """Configura as quantidades dos ativos na carteira."""
    carteira = carregar_carteira()
    ativos = carteira.get("ativos", {})

    console.print("[bold]Configure as quantidades dos seus ativos:[/bold]\n")

    for grupo, itens in ativos.items():
        if grupo in ("manual", "renda_fixa", "fundos"):
            continue
        console.print(f"[cyan]{grupo.upper()}[/cyan]")
        for ticker, info in itens.items():
            qtd = typer.prompt(f"  {info['nome']} (qtd atual: {info.get('quantidade', 0)})", default=info.get("quantidade", 0), type=int)
            info["quantidade"] = qtd

    console.print("\n[cyan]RENDA FIXA (valor investido + % CDI)[/cyan]")
    for nome, info in ativos.get("renda_fixa", {}).items():
        valor = typer.prompt(f"  {nome} - valor investido", default=info.get("valor_investido", 0.0), type=float)
        pct = typer.prompt(f"  {nome} - % CDI (ex: 1.0 = 100%)", default=info.get("percentual_cdi", 1.0), type=float)
        info["valor_investido"] = valor
        info["percentual_cdi"] = pct

    salvar_carteira(carteira)
    console.print("\n[green]Carteira configurada e salva![/green]")


if __name__ == "__main__":
    app()
