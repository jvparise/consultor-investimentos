# ADR-005 — MVP offline-first sem APIs externas

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

O PRD original incluía no MVP: integração com Yahoo Finance, Tesouro Direto API, BACEN e CoinGecko, além de scheduler automático para atualização de preços. Isso criava dependências externas que poderiam tornar o sistema não-funcional sem internet.

## Decisão

O MVP é 100% offline-first. Preços e valores são inseridos manualmente pelo usuário. Nenhuma API externa, nenhum scheduler, nenhuma thread em background.

## Alternativas consideradas

**MVP com APIs externas desde o início:** Rejeitado porque uma mudança na API do Yahoo Finance (que já aconteceu em 2023) quebraria o MVP completamente. A fundação do produto não pode depender de terceiros.

## Consequências

**Positivo:**
- Sistema funciona sem internet
- Sem risco de quebra por mudança de API externa
- Escopo do MVP reduzido — entrega mais rápida
- Dados são exatamente o que o usuário inseriu — sem discrepâncias de fonte

**Negativo:**
- Usuário precisa atualizar preços manualmente
- Sem atualização em tempo real

**Planejado para v1.5:** Integração com Yahoo Finance (QUANTITY_PRICE) e Tesouro Direto API (renda fixa), com scheduler ativado ao abrir o app — não em background.

**Regra derivada:** Nenhuma chamada de rede no código do MVP. Se aparecer `import httpx` ou `import requests` em qualquer arquivo que não seja legado, é um erro de escopo.
