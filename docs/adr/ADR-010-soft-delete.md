# ADR-010 — Soft delete para ativos

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

Quando um ativo é "excluído" da carteira (posição zerada, ativo liquidado), o histórico de transações precisa ser preservado para auditoria, histórico patrimonial e eventual cálculo de IR.

## Decisão

Ativos nunca são deletados fisicamente do banco. A coluna `is_active` (Boolean, default=True) em `assets` é definida como `False` ao "excluir". O método correto é `AssetRepository.deactivate(id)`, não `delete()`.

Ativos inativos:
- Não aparecem em listas de seleção para novas transações
- Não aparecem no dashboard de posições ativas
- Continuam visíveis em consultas de histórico e auditoria
- Suas transações e preços históricos são preservados integralmente

## Alternativas consideradas

**Hard delete com CASCADE:** Deleta o ativo e todas as transações/preços associados. Rejeitado porque destrói histórico financeiro real — impossível reconstruir rentabilidade passada ou base de custo para IR.

**Mover para tabela de arquivo:** Complexidade desnecessária para este volume de dados.

## Consequências

**Positivo:**
- Histórico patrimonial íntegro mesmo após encerramento de posição
- Permite reativar um ativo se o usuário comprar novamente no futuro
- Auditoria completa de todas as operações

**Negativo:**
- Todas as queries de listagem ativa precisam filtrar `WHERE is_active = TRUE`
- Risco de esquecer o filtro em uma query — mitigado pelo `AssetRepository.get_active()` como método padrão

**Regra derivada:** `AssetRepository.get_all()` retorna todos (incluindo inativos — para histórico). `AssetRepository.get_active()` retorna apenas ativos — usado em 95% dos casos na UI.
