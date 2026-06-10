# ADR-012 — Rentabilidade pelo método simplificado

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

Há três métodos para calcular rentabilidade de uma carteira com aportes periódicos:

1. **Método simplificado:** `(Valor Atual - Total Aportado) / Total Aportado`
2. **MWR / IRR (Money-Weighted Return):** Considera o timing dos aportes — retorno real do investidor
3. **TWR (Time-Weighted Return):** Padrão CFA/institucional — elimina distorção causada por aportes, mede performance do gestor independente de fluxo de caixa

## Decisão

Usar o **método simplificado** no MVP com disclaimer obrigatório e visível.

Fórmula:
```
rentabilidade = (valor_atual - total_aportado) / total_aportado × 100
```

Onde `total_aportado` = soma de todos os `INITIAL_BALANCE` + `BUY` + `CONTRIBUTION` - `WITHDRAWAL`.

Disclaimer obrigatório em toda exibição de rentabilidade:
> "Rentabilidade calculada pelo método simplificado: (Valor Atual − Total Aportado) ÷ Total Aportado. Não considera o timing dos aportes (não é TWR)."

## Alternativas consideradas

**TWR:** Matematicamente correto para comparar com benchmarks. Rejeitado para MVP porque requer o valor da carteira imediatamente antes de cada aporte — dado que o Modo B de snapshot não garante.

**MWR/IRR:** Mais relevante para o investidor individual (mede o retorno real considerando quando ele aportou). Rejeitado para MVP por exigir biblioteca de cálculo de IRR iterativo e ser mais complexo de explicar na UI.

## Consequências

**Positivo:**
- Implementação trivial — sem dependência de biblioteca externa
- Resultado intuitivo para o usuário leigo

**Negativo:**
- **Distorção conhecida:** Um grande aporte recente faz a rentabilidade parecer menor do que é (o dinheiro novo ainda não "rendeu"). Isso pode confundir o usuário.
- Não comparável com rentabilidade de fundos (que usam TWR) ou CDI

**Planejado para v2.0:** Adicionar TWR como cálculo paralelo quando os snapshots diários estiverem disponíveis para todos os ativos (Modo A de snapshot).

**Regra derivada:** O texto do disclaimer está centralizado em `config.RENTABILITY_DISCLAIMER` — nunca duplicado nos arquivos de página.
