# ADR-013 — UserSettings single-row (id sempre = 1)

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

O sistema é pessoal e single-user. Configurações como aporte mensal, gastos e metas de alocação por classe são únicas — não há perfis múltiplos.

## Decisão

A tabela `user_settings` tem no máximo **uma linha**, com `id = 1` sempre.

Acesso via `SettingsRepository.get_or_create()` — se a linha não existir (primeiro uso), cria com valores padrão. Nunca há `INSERT` de nova linha: apenas `UPDATE` na linha existente.

`CheckConstraint("id = 1")` no banco impede inserção de segunda linha por acidente.

A soma dos percentuais de alocação alvo deve ser `0` (não configurado) ou `100` (configurado). Validado no Service, não no banco.

## Alternativas consideradas

**Tabela de configurações key-value (`key VARCHAR, value TEXT`):** Flexível para adicionar novas configurações sem migration. Rejeitado porque perde type safety — `monthly_contribution` como `TEXT` pode receber qualquer valor, sem validação de tipo no banco.

**Arquivo de configuração TOML/JSON:** Simples. Rejeitado por misturar dois mecanismos de persistência (banco + arquivo) e por não ter backup automático junto com o banco.

## Consequências

**Positivo:**
- Type safety nas configurações financeiras (colunas `Numeric`)
- `CheckConstraint` impede segunda linha no nível do banco
- Queries simples: `SELECT * FROM user_settings WHERE id = 1`

**Negativo:**
- Adicionar nova configuração requer migration de schema
- Se o `CheckConstraint` for ignorado por ferramenta externa, o comportamento é indefinido

**Regra derivada:** `SettingsRepository` nunca expõe método `create()` publicamente. Apenas `get_or_create()` e `update()`.
