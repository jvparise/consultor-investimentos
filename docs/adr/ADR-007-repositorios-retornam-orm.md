# ADR-007 — Repositórios retornam objetos ORM diretamente

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

Decisão explícita após análise dos trade-offs: repositórios devem retornar objetos ORM (modelos SQLAlchemy) ou entidades de domínio desacopladas (dataclasses)?

## Decisão

Repositórios retornam objetos ORM SQLAlchemy diretamente. Não há camada de mapeamento ORM → entidade de domínio nos repositórios.

## Alternativas consideradas

**Repositórios retornam dataclasses de domínio:** Desacoplamento total do ORM, seguro para `st.session_state`. Rejeitado porque exige manter dois modelos sincronizados por tabela (ORM + dataclass + mapeamento), triplicando o trabalho de cada mudança de schema — desproporcional para projeto local single-user.

## Consequências

**Positivo:**
- Zero código de mapeamento
- Mudanças de schema refletem automaticamente
- Menos arquivos e menos superfície de erro

**Negativo / Riscos mitigados:**

O risco real é o `DetachedInstanceError` no Streamlit: objetos ORM guardados em `st.session_state` levantam exceção ao acessar relacionamentos lazy após o rerun, porque a sessão SQLAlchemy já foi fechada.

**Mitigação por regra arquitetural (não por código):**
1. Objetos ORM **nunca** são guardados em `st.session_state`
2. Páginas Streamlit **nunca** chamam repositórios diretamente — apenas Services
3. Services consomem ORM internamente e retornam DTOs (`Position`, `PortfolioSummary`, etc.) para a UI

O desacoplamento real acontece na fronteira Services → UI, não em Repositories → Services.

**Revisitar se:** O projeto crescer para múltiplos usuários, adicionar uma API REST, ou precisar de testes de repositório sem banco real.
