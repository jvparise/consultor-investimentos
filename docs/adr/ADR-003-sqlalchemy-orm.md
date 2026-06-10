# ADR-003 — ORM: SQLAlchemy com modelos declarativos

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

O sistema precisa de acesso a banco de dados com type safety, suporte a migrations e facilidade de teste.

## Decisão

Usar SQLAlchemy 2.x com a API declarativa (`DeclarativeBase`) e `Mapped` / `mapped_column` para type hints nativos.

## Alternativas consideradas

**SQLAlchemy Core (sem ORM):** Mais controle sobre SQL gerado. Descartado por exigir mais código manual para operações CRUD e não ter suporte direto do Alembic para autogenerate.

**Peewee:** ORM mais simples. Descartado por ecossistema menor, sem suporte ao padrão `Mapped` moderno e integração mais fraca com Alembic.

**SQL puro com sqlite3:** Máxima simplicidade. Descartado por falta de type safety, sem migrations automatizadas, sem relacionamentos declarados.

## Consequências

**Positivo:**
- `Mapped[tipo]` dá type hints reais nas colunas — erros detectados pelo linter
- Alembic autogenerate detecta diferenças entre modelos e banco automaticamente
- Relacionamentos (`relationship()`) simplificam joins
- Testes podem usar banco SQLite em memória sem mudanças de código

**Negativo:**
- Lazy loading de relacionamentos pode causar `DetachedInstanceError` no Streamlit — mitigado pela regra de não guardar ORM em `st.session_state` (ADR-007)
- Curva de aprendizado maior que SQL puro para queries complexas
