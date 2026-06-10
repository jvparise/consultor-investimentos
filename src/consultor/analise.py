"""Análise da carteira via Claude API."""

from __future__ import annotations

import anthropic
from dataclasses import dataclass

from .coleta import DadosMercado


@dataclass
class ResultadoAnalise:
    resumo_carteira: str
    analise_cenario: str
    sugestoes: str
    alertas: str


def montar_contexto_carteira(
    carteira: dict,
    dados_mercado: DadosMercado,
    valores_mes_anterior: dict[str, float],
    valores_atuais: dict[str, float],
) -> str:
    linhas = ["## Carteira atual\n"]

    total_anterior = sum(valores_mes_anterior.values()) if valores_mes_anterior else 0
    total_atual = sum(valores_atuais.values())
    variacao_total = total_atual - total_anterior

    for nome, valor_atual in sorted(valores_atuais.items()):
        anterior = valores_mes_anterior.get(nome, valor_atual)
        variacao = valor_atual - anterior
        pct = (variacao / anterior * 100) if anterior else 0
        linhas.append(f"- {nome}: R$ {valor_atual:,.2f} (var: R$ {variacao:+,.2f} / {pct:+.2f}%)")

    linhas.append(f"\n**Total: R$ {total_atual:,.2f}** (var: R$ {variacao_total:+,.2f})")

    linhas.append("\n## Cenário macroeconômico\n")
    linhas.append(f"- Selic: {dados_mercado.selic_anual:.2f}% a.a.")
    linhas.append(f"- CDI mensal: {dados_mercado.cdi_mensal * 100:.4f}%")
    linhas.append(f"- IPCA 12m: {dados_mercado.ipca_acumulado_12m:.2f}%")
    linhas.append(f"- Dólar (PTAX): R$ {dados_mercado.dolar_brl:.4f}")
    linhas.append(f"\nData de referência: {dados_mercado.data_coleta}")

    return "\n".join(linhas)


def analisar_carteira(
    carteira: dict,
    dados_mercado: DadosMercado,
    valores_mes_anterior: dict[str, float],
    valores_atuais: dict[str, float],
    api_key: str,
) -> ResultadoAnalise:
    cliente = anthropic.Anthropic(api_key=api_key)

    contexto = montar_contexto_carteira(carteira, dados_mercado, valores_mes_anterior, valores_atuais)

    prompt = f"""Você é um assessor de investimentos pessoal experiente no mercado brasileiro.
Analise a carteira abaixo e forneça orientações práticas e objetivas.

{contexto}

Responda em português com 4 seções bem definidas:

**1. RESUMO DA CARTEIRA**
Visão geral da composição atual (renda fixa, FIIs, ações internacionais, fundos) com percentuais aproximados.

**2. ANÁLISE DO CENÁRIO**
Como o cenário macroeconômico atual (Selic, IPCA, dólar) impacta cada classe de ativo da carteira.

**3. SUGESTÕES DE REBALANCEAMENTO**
Sugestões concretas considerando o perfil da carteira. Indique o que aumentar, reduzir ou manter.

**4. ALERTAS**
Pontos de atenção: ativos com performance abaixo do esperado, concentrações de risco, vencimentos próximos relevantes.

Seja direto e prático. Evite generalidades. Base suas sugestões nos números apresentados."""

    mensagem = cliente.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    resposta = mensagem.content[0].text

    secoes = {"resumo": "", "cenario": "", "sugestoes": "", "alertas": ""}
    secao_atual = None

    for linha in resposta.split("\n"):
        if "RESUMO DA CARTEIRA" in linha.upper():
            secao_atual = "resumo"
        elif "ANÁLISE DO CENÁRIO" in linha.upper() or "ANALISE DO CENARIO" in linha.upper():
            secao_atual = "cenario"
        elif "SUGESTÕES" in linha.upper() or "SUGESTOES" in linha.upper():
            secao_atual = "sugestoes"
        elif "ALERTAS" in linha.upper():
            secao_atual = "alertas"
        elif secao_atual:
            secoes[secao_atual] += linha + "\n"

    return ResultadoAnalise(
        resumo_carteira=secoes["resumo"].strip(),
        analise_cenario=secoes["cenario"].strip(),
        sugestoes=secoes["sugestoes"].strip(),
        alertas=secoes["alertas"].strip(),
    )
