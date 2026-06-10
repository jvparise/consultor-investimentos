# ADR-009 — Decimal para todos os valores financeiros

**Status:** Aceito  
**Data:** 2026-06-09

## Contexto

Valores monetários não podem usar `float` em sistemas financeiros. O tipo `float` usa representação binária de ponto flutuante que causa erros de arredondamento acumulativos:

```python
>>> 0.1 + 0.2
0.30000000000000004
>>> 1234.56 * 100
123456.00000000001
```

Em cálculos de patrimônio, esses erros se acumulam ao longo de meses e distorcem resultados.

## Decisão

Todo valor financeiro usa `decimal.Decimal` em Python e `Numeric(precision, scale)` no SQLAlchemy/SQLite:

- Valores monetários (R$): `Numeric(15, 2)` → até R$ 9 trilhões com 2 casas decimais
- Preços unitários e quantidades: `Numeric(15, 6)` → suporta cotas fracionadas e preços de ativos com muitas casas (ex.: cripto)
- Percentuais: `Numeric(5, 2)` → até 999,99%

SQLAlchemy mapeia `Numeric` para `decimal.Decimal` automaticamente quando `asdecimal=True` (padrão).

## Alternativas consideradas

**`float` nativo Python:** Simples mas incorreto para finanças. Rejeitado.

**`int` em centavos (R$ × 100):** Evita float. Rejeitado por aumentar complexidade na leitura/escrita e não escalar para quantidades fracionadas.

## Consequências

**Positivo:**
- Aritmética exata para operações financeiras
- Sem erros de arredondamento acumulativos

**Negativo:**
- `Decimal` não é serializável para JSON nativamente — precisará de conversão em contextos futuros (ex.: exportação)
- Operações com `Decimal` são mais lentas que `float` — irrelevante para o volume deste projeto

**Regra derivada:** Constantes numéricas em `config.py` são `Decimal("valor")`, não `float`. Ex.: `Decimal("0.07")`, nunca `0.07`.
