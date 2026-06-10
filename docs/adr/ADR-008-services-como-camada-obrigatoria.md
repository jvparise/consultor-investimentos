# ADR-008 — Services como camada obrigatória entre UI e dados

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

Com Streamlit, não há separação natural entre controlador e view. Sem uma regra explícita, lógica de negócio tende a migrar para as páginas, tornando o código impossível de testar e difícil de manter.

## Decisão

A camada de Services é obrigatória e inviolável:

```
Páginas Streamlit  →  Services  →  Repositories  →  SQLAlchemy  →  SQLite
```

**Proibido:**
- Página chamar repositório diretamente
- Página instanciar sessão SQLAlchemy
- Página conter cálculo financeiro (preço médio, projeção, rentabilidade)
- Service retornar objeto ORM para a página — retorna DTOs

**Permitido nas páginas:**
- Chamar métodos de Services
- Renderizar DTOs recebidos dos Services
- Gerenciar estado de UI em `st.session_state` (apenas IDs e valores primitivos)
- Chamar funções de `components/` para renderização

## Alternativas consideradas

**Acesso direto a repositórios nas páginas:** Mais simples no curto prazo. Rejeitado porque impossibilita testes da lógica de negócio sem a UI Streamlit, e leva à dispersão de regras financeiras em múltiplos arquivos de página.

## Consequências

**Positivo:**
- Toda lógica financeira testável sem Streamlit
- Mudança de banco de dados não afeta as páginas
- Refatoração de cálculo (ex.: trocar método de rentabilidade) é feita em um único lugar

**Negativo:**
- Uma camada extra de indireção para operações simples (ex.: listar ativos)
- Disciplina manual necessária — não há enforcement automático

**Regra de teste:** Se um teste de Service precisar importar `streamlit`, algo está errado.
