"""Integração com Google Sheets via gspread."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def conectar(credentials_path: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return gspread.authorize(creds)


def ler_ultimo_mes(client: gspread.Client, spreadsheet_id: str, aba: str) -> dict[str, float]:
    """Lê os valores do mês mais recente da planilha."""
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(aba)
    dados = ws.get_all_values()

    valores: dict[str, float] = {}
    ultimo_header_idx = -1

    for i, row in enumerate(dados):
        if row and row[0] == "Tipo de Investimento":
            ultimo_header_idx = i

    if ultimo_header_idx == -1:
        return valores

    for row in dados[ultimo_header_idx + 1:]:
        if not row or not row[0]:
            continue
        nome = row[0].strip()
        if nome.startswith("TOTAL"):
            continue
        try:
            valor_str = row[2].replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
            if valor_str and valor_str not in ["-", ""]:
                valores[nome] = float(valor_str)
        except (ValueError, IndexError):
            pass

    return valores


def _formatar_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def escrever_mes(
    client: gspread.Client,
    spreadsheet_id: str,
    aba: str,
    nome_mes: str,
    linhas: list[list[Any]],
) -> None:
    """Adiciona um novo bloco mensal na planilha."""
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(aba)
    dados_existentes = ws.get_all_values()

    proxima_linha = len(dados_existentes) + 2  # linha em branco de separação

    cabecalho_mes = [[nome_mes] + [""] * 17]
    cabecalho_colunas = [[
        "Tipo de Investimento", "Preço Mês Anterior", "Preço Atual",
        "Valorização", "Rendimento", "%",
        "Cota Abertura", "Cota Mín", "Cota Máx", "Yeld/ano",
        "Data Base", "Data de pagamento",
        "", "", "", "", "", "",
    ]]

    linhas_formatadas = []
    for linha in linhas:
        linhas_formatadas.append([
            linha[0],
            _formatar_brl(linha[1]) if isinstance(linha[1], float) else linha[1],
            _formatar_brl(linha[2]) if isinstance(linha[2], float) else linha[2],
            _formatar_brl(linha[3]) if isinstance(linha[3], float) else linha[3],
            _formatar_brl(linha[4]) if isinstance(linha[4], float) else linha[4],
            f"{linha[5]:.2f}%" if isinstance(linha[5], float) else linha[5],
        ] + [""] * 12)

    todas_linhas = cabecalho_mes + cabecalho_colunas + linhas_formatadas
    ws.insert_rows(todas_linhas, row=proxima_linha)
