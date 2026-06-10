# ADR-016 — Campo `description` de Goal excluído da interface

**Status:** Aceito  
**Data:** 2026-06-10  
**Contexto:** Implementação da Etapa 4.4 — Metas e Projeções

---

## Contexto

O modelo `Goal` e o `GoalRepository` possuem o campo `description: str | None`, que permite
armazenar uma descrição livre para cada meta financeira.

O DTO `GoalProgress`, consumido pela UI, **não inclui** este campo — resultado de uma decisão
intencional de manter `GoalProgress` focado em dados calculados (progresso, projeções, on_track).

## Decisão

O campo `description` **não será exposto na UI no MVP**:

1. O campo permanece no banco de dados e no repositório — sem remoção nem migração.
2. O formulário de criação de metas não inclui o campo `description`.
3. O formulário de edição de metas não permite visualizar nem alterar `description`.
4. `GoalProgress` não receberá o campo `description` no MVP.

## Motivação

- **Escopo do MVP:** a UI precisa de nome, valor-alvo e data-alvo para funcionamento completo.
  `description` é um detalhe editorial que não afeta cálculos nem projeções.
- **Sem pré-preenchimento:** para exibir `description` no formulário de edição, seria necessário
  adicioná-la ao `GoalProgress`. Isso aumenta o acoplamento do DTO por um campo de baixo valor.
- **Evitar DTO bloat:** `GoalProgress` é um DTO de projeção, não um espelho da tabela `goals`.
  Adicionar campos não-calculados deve ser avaliado criteriosamente.

## Consequências

- Dados de `description` criados via seed/script continuarão persistidos mas invisíveis na UI.
- Uma versão futura pode adicionar `description` ao `GoalProgress` e à UI sem breaking change.
- Desenvolvedores que vejam o campo no banco não devem interpretá-lo como um bug.

## Alternativas rejeitadas

- **Adicionar `description` ao `GoalProgress`**: adicionaria campo não-calculado ao DTO e exigiria
  carga extra no `GoalRepository.get_by_id()` durante o build de progress. Rejeitado por ora.
- **Remover `description` do modelo**: quebraria migrações existentes sem ganho real. Rejeitado.
