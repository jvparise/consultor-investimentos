# ADR-004 — Migrations: Alembic

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

O banco de dados vai evoluir com novas colunas e tabelas ao longo das versões. O usuário acumulará dados reais desde o primeiro uso.

## Decisão

Usar Alembic para gerenciar migrations desde o dia 1, com `render_as_batch=True` para compatibilidade com SQLite.

## Alternativas consideradas

**`Base.metadata.create_all()` apenas:** Cria tabelas na primeira execução mas não gerencia mudanças de schema. Descartado porque a primeira mudança de coluna exigiria recriar o banco manualmente, perdendo dados reais.

**Migrations manuais com SQL:** Possível mas propenso a erro e sem rastreamento de versão.

## Consequências

**Positivo:**
- Cada mudança de schema é rastreada com ID único e data
- `alembic upgrade head` aplica mudanças sem perda de dados
- `alembic downgrade -1` desfaz a última migration se necessário
- `alembic revision --autogenerate` detecta diferenças automaticamente

**Negativo:**
- `render_as_batch=True` necessário para SQLite — o Alembic recria tabelas internamente para simular `ALTER TABLE`
- Autogenerate não detecta mudanças em `CheckConstraint` customizados — precisam ser adicionados manualmente quando necessário

**Regra derivada:** Nunca modificar o schema diretamente no banco. Sempre via migration. Nunca editar uma migration já aplicada — criar uma nova.
