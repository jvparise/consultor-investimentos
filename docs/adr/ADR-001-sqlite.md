# ADR-001 — Banco de dados: SQLite

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

O sistema é pessoal, local e single-user. Precisa de persistência de dados financeiros sem custo de infraestrutura.

## Decisão

Usar SQLite como banco de dados, com arquivo em `data/investimentos.db`.

## Alternativas consideradas

**PostgreSQL:** Robusto, suporta concorrência, tipo DECIMAL nativo. Descartado porque exige servidor rodando em background, configuração de usuário/senha e é desproporcional para uso local single-user.

**JSON/CSV em arquivo:** Simples de implementar. Descartado por falta de integridade referencial, sem suporte a queries, sem transações atômicas — inadequado para dados financeiros.

## Consequências

**Positivo:**
- Zero configuração de servidor
- Arquivo único e portável — backup é copiar o `.db`
- SQLAlchemy suporta plenamente via dialect SQLite
- Suficiente para dezenas de milhares de transações

**Negativo:**
- `PRAGMA foreign_keys=ON` precisa ser ativado manualmente a cada conexão (implementado em `connection.py`)
- `ALTER TABLE` não suportado nativamente — Alembic precisa de `render_as_batch=True`
- Sem suporte a múltiplos usuários concorrentes (irrelevante para este projeto)

**Regra derivada:** O arquivo `data/investimentos.db` deve estar no `.gitignore`.
