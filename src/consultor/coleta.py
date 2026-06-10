"""Coleta de preços de mercado e dados macroeconômicos."""

from __future__ import annotations

import os
import httpx
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass
class DadosMercado:
    precos_fiis: dict[str, float] = field(default_factory=dict)
    precos_acoes_us: dict[str, float] = field(default_factory=dict)
    dolar_brl: float = 0.0
    cdi_mensal: float = 0.0
    selic_anual: float = 0.0
    ipca_acumulado_12m: float = 0.0
    data_coleta: str = ""


def buscar_precos_brapi(tickers: list[str]) -> dict[str, float]:
    """Busca preços de ativos brasileiros via brapi.dev (1 por requisição no plano free)."""
    token = os.getenv("BRAPI_TOKEN", "")
    if not tickers:
        return {}
    precos: dict[str, float] = {}
    with httpx.Client(timeout=15) as client:
        for ticker in tickers:
            url = f"https://brapi.dev/api/quote/{ticker}"
            params = {"token": token} if token else {}
            try:
                resp = client.get(url, params=params)
                results = resp.json().get("results", [])
                if results:
                    preco = results[0].get("regularMarketPrice")
                    if preco:
                        precos[ticker] = float(preco)
            except Exception:
                continue
    return precos


def buscar_preco_yahoo_usd(ticker: str) -> float:
    """Busca preço em USD de ação americana via Yahoo Finance."""
    import yfinance as yf
    try:
        hist = yf.Ticker(ticker).history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 0.0


def buscar_dolar_bcb() -> float:
    """Busca a cotação do dólar PTAX (venda) no Banco Central."""
    for delta in range(4):
        dia = (date.today() - timedelta(days=delta)).strftime("%m-%d-%Y")
        url = (
            f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
            f"CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{dia}'"
            f"&$format=json&$select=cotacaoVenda"
        )
        try:
            with httpx.Client(timeout=10) as client:
                valores = client.get(url).json().get("value", [])
                if valores:
                    return float(valores[-1]["cotacaoVenda"])
        except Exception:
            continue
    return 0.0


def buscar_cdi_mensal_bcb() -> float:
    """Busca a taxa CDI mensal mais recente do Banco Central."""
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados/ultimos/1?formato=json"
    try:
        with httpx.Client(timeout=10) as client:
            return float(client.get(url).json()[0]["valor"]) / 100
    except Exception:
        return 0.0


def buscar_selic_bcb() -> float:
    """Busca a meta Selic atual (% ao ano)."""
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"
    try:
        with httpx.Client(timeout=10) as client:
            return float(client.get(url).json()[0]["valor"])
    except Exception:
        return 0.0


def buscar_ipca_12m_bcb() -> float:
    """Busca IPCA acumulado dos últimos 12 meses."""
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/1?formato=json"
    try:
        with httpx.Client(timeout=10) as client:
            return float(client.get(url).json()[0]["valor"])
    except Exception:
        return 0.0


def coletar_todos_dados(carteira: dict, valores_planilha: dict[str, float] | None = None) -> DadosMercado:
    """Coleta todos os dados de mercado necessários para a carteira."""
    dados = DadosMercado(data_coleta=datetime.now().strftime("%d/%m/%Y %H:%M"))
    fallback = valores_planilha or {}

    dados.dolar_brl = buscar_dolar_bcb()
    dados.cdi_mensal = buscar_cdi_mensal_bcb()
    dados.selic_anual = buscar_selic_bcb()
    dados.ipca_acumulado_12m = buscar_ipca_12m_bcb()

    ativos = carteira.get("ativos", {})

    # FIIs via brapi.dev (preços em BRL)
    tickers_fiis = [t.replace(".SA", "") for t in ativos.get("fiis", {}).keys()]
    precos_fiis = buscar_precos_brapi(tickers_fiis)

    for ticker, info in ativos.get("fiis", {}).items():
        nome = info["nome"]
        qtd = info.get("quantidade", 0)
        if qtd <= 0:
            continue
        preco = precos_fiis.get(ticker.replace(".SA", ""), 0.0)
        if preco > 0:
            dados.precos_fiis[nome] = preco * qtd
        elif nome in fallback:
            dados.precos_fiis[nome] = fallback[nome]

    # Ações americanas via Yahoo Finance (preços em USD)
    for ticker, info in ativos.get("acoes_us", {}).items():
        nome = info["nome"]
        qtd = info.get("quantidade", 0)
        if qtd <= 0:
            continue
        preco = buscar_preco_yahoo_usd(ticker)
        if preco > 0:
            dados.precos_acoes_us[nome] = preco * qtd
        elif nome in fallback:
            dados.precos_acoes_us[nome] = fallback[nome]

    return dados


def calcular_valor_cdb(valor_investido: float, percentual_cdi: float, cdi_mensal: float) -> float:
    """Calcula valor aproximado de CDB pós-fixado no mês."""
    return valor_investido * (1 + cdi_mensal * percentual_cdi)
