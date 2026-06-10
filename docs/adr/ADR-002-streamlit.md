# ADR-002 — Framework de UI: Streamlit

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

O sistema precisa de dashboards interativos com gráficos. O usuário é desenvolvedor Python e quer velocidade de entrega, sem aprender frontend.

## Decisão

Usar Streamlit como único framework de UI. Não há separação frontend/backend — tudo roda em um único processo Python.

## Alternativas consideradas

**FastAPI + HTMX:** O PRD original sugeria esta combinação. Descartado porque exige manter dois processos (FastAPI server + cliente), configuração de rotas REST, e mais código para a mesma funcionalidade de dashboard local.

**Dash (Plotly):** Similar ao Streamlit. Descartado por ser mais verboso para layouts simples e ter menor ecossistema de componentes prontos.

**FastAPI + React:** Totalmente fora de proporção para um projeto local pessoal.

## Consequências

**Positivo:**
- `streamlit run app.py` é o único comando necessário
- Gráficos Plotly integram nativamente
- Formulários e estado com `st.session_state` sem boilerplate
- Iteração rápida: salvar o arquivo já atualiza a UI

**Negativo:**
- Modelo de execução diferente do tradicional: **o script inteiro re-executa a cada interação do usuário**
- Objetos com estado (como sessões SQLAlchemy ORM) não podem ser guardados em `st.session_state` entre reruns — ver ADR-007
- Sem separação explícita de rotas — navegação via `st.Page` / multipage
- Não é adequado para APIs REST ou uso multi-usuário no futuro

**Regra derivada:** Nenhuma lógica de negócio nas páginas Streamlit. Páginas apenas chamam Services e renderizam resultado (ver ADR-008).
