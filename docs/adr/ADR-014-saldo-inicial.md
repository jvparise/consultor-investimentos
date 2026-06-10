# ADR-014 — Onboarding via saldo inicial, não histórico de transações

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

O usuário já possui uma carteira consolidada (R$ 210.000). Cadastrar anos de histórico de transações (cada compra de cada ativo desde o início) é inviável e desnecessário para o objetivo do sistema.

## Decisão

O onboarding usa um tipo especial de transação: `INITIAL_BALANCE`.

**Para `QUANTITY_PRICE` (ações, FIIs, ETFs):**
- Usuário informa: quantidade atual de cotas + preço médio de compra
- O sistema cria uma `Transaction(type=INITIAL_BALANCE, quantity=N, unit_price=PM, total_amount=N×PM)`
- Esse registro **define** o ponto de partida — não entra na média ponderada móvel futura como uma compra comum

**Para `VALUE_ONLY` (CDBs, fundos, LCIs):**
- Usuário informa: valor atual da posição
- O sistema cria uma `Transaction(type=INITIAL_BALANCE, total_amount=valor, quantity=NULL, unit_price=NULL)`
- E registra o mesmo valor em `asset_prices` para a data do saldo inicial

Transações futuras (BUY, SELL, CONTRIBUTION etc.) são registradas normalmente a partir da data de onboarding.

## Alternativas consideradas

**Import de extrato CSV (B3/corretoras):** Elimina entrada manual. Rejeitado para MVP por exigir parsers de múltiplos formatos de extrato e validação de dados externos — complexidade fora do escopo.

**Não suportar histórico pré-sistema:** Usuário começaria do zero. Rejeitado porque tornaria o sistema inútil para quem já investe.

## Consequências

**Positivo:**
- Onboarding em minutos, não horas
- Patrimônio real refletido desde o primeiro uso
- Preço médio informado pelo usuário (vem do extrato da corretora) é mais confiável que recalcular por histórico

**Negativo:**
- Rentabilidade pré-onboarding não é rastreável pelo sistema
- Se o usuário informar preço médio errado no INITIAL_BALANCE, o cálculo de gain/loss estará incorreto — sem forma de corrigir retroativamente sem deletar e reinserir
- `INITIAL_BALANCE` precisa ser tratado diferente de `BUY` no cálculo de preço médio ponderado

**Regra derivada:** `PortfolioService.calcular_preco_medio_ponderado()` trata `INITIAL_BALANCE` como ponto de partida absoluto — não como uma compra que entra na média com compras anteriores (que não existem).
