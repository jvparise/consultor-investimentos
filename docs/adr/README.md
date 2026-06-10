# Architecture Decision Records

Registro de decisões arquiteturais relevantes do projeto.

## Formato

Cada ADR segue a estrutura:

- **Status:** Aceito | Substituído por ADR-XXX | Depreciado
- **Contexto:** Qual problema motivou a decisão
- **Decisão:** O que foi decidido
- **Alternativas consideradas:** O que foi descartado e por quê
- **Consequências:** O que essa decisão implica (positivo e negativo)

## Índice

| ADR | Título | Status |
|-----|--------|--------|
| [ADR-001](ADR-001-sqlite.md) | Banco de dados: SQLite | Aceito |
| [ADR-002](ADR-002-streamlit.md) | Framework de UI: Streamlit | Aceito |
| [ADR-003](ADR-003-sqlalchemy-orm.md) | ORM: SQLAlchemy com modelos declarativos | Aceito |
| [ADR-004](ADR-004-alembic-migrations.md) | Migrations: Alembic | Aceito |
| [ADR-005](ADR-005-offline-first-mvp.md) | MVP offline-first sem APIs externas | Aceito |
| [ADR-006](ADR-006-dois-tipos-de-ativo.md) | Dois tipos de ativo: QUANTITY_PRICE e VALUE_ONLY | Aceito |
| [ADR-007](ADR-007-repositorios-retornam-orm.md) | Repositórios retornam objetos ORM diretamente | Aceito |
| [ADR-008](ADR-008-services-como-camada-obrigatoria.md) | Services como camada obrigatória entre UI e dados | Aceito |
| [ADR-009](ADR-009-decimal-para-valores-financeiros.md) | Decimal para todos os valores financeiros | Aceito |
| [ADR-010](ADR-010-soft-delete.md) | Soft delete para ativos | Aceito |
| [ADR-011](ADR-011-snapshots-modo-b.md) | Snapshots patrimoniais: Modo B (manual + auto na sessão) | Aceito |
| [ADR-012](ADR-012-rentabilidade-metodo-simplificado.md) | Rentabilidade pelo método simplificado | Aceito |
| [ADR-013](ADR-013-single-user-settings.md) | UserSettings single-row (id sempre = 1) | Aceito |
| [ADR-014](ADR-014-saldo-inicial.md) | Onboarding via saldo inicial, não histórico de transações | Aceito |
| [ADR-015](ADR-015-formula-projecao-valor-futuro.md) | Fórmula de projeção: iteração mês a mês com taxa equivalente | Aceito |
