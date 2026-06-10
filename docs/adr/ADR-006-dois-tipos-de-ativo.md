# ADR-006 — Dois tipos de ativo: QUANTITY_PRICE e VALUE_ONLY

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

A carteira do usuário contém dois tipos fundamentalmente diferentes de ativo:
- Ativos com cotação unitária (ações, FIIs, ETFs): valor = quantidade × preço por cota
- Ativos sem cotação unitária (CDBs, fundos, LCIs, debêntures): valor = saldo total da posição

Tratar ambos da mesma forma levaria a campos sem sentido (ex.: "quantidade de cotas" de um CDB) ou a cálculos incorretos.

## Decisão

Introduzir o enum `AssetTrackingType` com dois valores:
- `QUANTITY_PRICE`: rastreado por quantidade × preço unitário
- `VALUE_ONLY`: rastreado por valor total da posição

O campo `price` em `asset_prices` tem semântica diferente por tipo:
- `QUANTITY_PRICE` → preço por cota/ação
- `VALUE_ONLY` → valor total da posição naquela data

Campos `quantity` e `unit_price` em `transactions` são `NULLABLE` — preenchidos apenas para `QUANTITY_PRICE`.

## Alternativas consideradas

**Tabelas separadas por tipo:** `equity_positions` e `fixed_income_positions`. Rejeitado por duplicar lógica de snapshot, relatório e metas — qualquer agregação precisaria de UNION.

**Campo único com semântica implícita:** Ignorar a distinção e sempre usar `total_amount`. Rejeitado porque impede calcular preço médio de entrada para ativos negociáveis.

## Consequências

**Positivo:**
- Modelo correto para cada tipo de ativo — sem campos vazios forçados
- `PortfolioService.get_position()` aplica lógica correta por tipo
- Formulários da UI exibem campos condicionais ao tipo selecionado

**Negativo:**
- Dois fluxos de lógica em `PortfolioService` — um por `tracking_type`
- A semântica dual do campo `price` precisa estar documentada no código (comentário em `models.py`) e neste ADR

**Tipos de transação permitidos por tracking_type** estão mapeados em `config.py` (`ALLOWED_TRANSACTION_TYPES`) e validados no `TransactionRepository`.
