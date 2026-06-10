# ADR-015 — Fórmula de Projeção: Valor Futuro com Aportes Mensais

**Status:** Aceito  
**Data:** 2026-06-09

---

## Contexto

O sistema precisa projetar em quantos meses o patrimônio atual atingirá uma meta financeira,
considerando aportes mensais constantes e uma taxa de rentabilidade anual.

Há duas abordagens possíveis: fórmula fechada de Valor Futuro, ou iteração mês a mês.

---

## Decisão

Usar **iteração mês a mês** com taxa mensal equivalente calculada a partir da taxa anual.

### Fórmula da taxa mensal equivalente

```
r = (1 + taxa_anual)^(1/12) - 1
```

Esta é a taxa mensal equivalente — não a taxa anual dividida por 12 (que seria taxa proporcional,
matematicamente incorreta para juros compostos).

### Iteração mensal

```
valor[0] = patrimônio_atual
valor[n] = valor[n-1] × (1 + r) + aporte_mensal
```

A cada mês: o patrimônio atual rende pela taxa mensal e o aporte é adicionado ao final do período.
O processo repete até `valor[n] >= meta` ou até `MAX_PROJECTION_MONTHS = 600` (50 anos).

### Por que iteração e não a fórmula fechada?

A fórmula fechada é matematicamente equivalente:
```
FV = PV × (1+r)^n + PMT × [((1+r)^n - 1) / r]
```

Mas a iteração é preferida porque:

1. **Produz a série mensal** necessária para o gráfico como subproduto natural — sem cálculo adicional
2. **Mais auditável**: cada passo é verificável individualmente
3. **Extensível**: aportes variáveis ou eventos pontuais (v2.0) são triviais de adicionar
4. **Mesmo resultado**: para PMT constante, iteração e fórmula fechada produzem o mesmo n

---

## Premissas

1. **Aporte constante**: mesmo valor todos os meses (sem variação)
2. **Rentabilidade nominal**: não desconta inflação
3. **Aporte ao final do período**: o aporte é somado depois do rendimento do mês (convenção "fim de período")
4. **Reinvestimento total**: dividendos e rendimentos já estão embutidos na taxa de rentabilidade anual
5. **Sem impostos**: IR sobre ganhos não é considerado
6. **Taxa nominal e constante**: não há variação de cenário durante a projeção

---

## Limitações

- Não considera a variação real da rentabilidade ao longo do tempo
- Não considera IR sobre ganhos (para ativos tributados, o resultado real é pior)
- Não considera inflação — os valores são nominais
- Aporte constante é simplificação: na prática, aportes tendem a crescer com a renda
- A projeção é **ilustrativa**, não preditiva

**Disclaimer obrigatório na UI:**
> "Projeção baseada em taxa de rentabilidade constante e aporte mensal fixo.
> Não considera inflação, impostos ou variação de mercado."

---

## Cenários

| Cenário | Taxa Anual | Taxa Mensal Equivalente |
|---------|-----------|------------------------|
| Conservador | 7,00% a.a. | 0,5654% a.m. |
| Moderado | 10,00% a.a. | 0,7974% a.m. |
| Otimista | 13,00% a.a. | 1,0236% a.m. |

**Cálculo da taxa mensal (moderado como exemplo):**
```
r = (1 + 0,10)^(1/12) - 1
r = (1,10)^(0,08333...) - 1
r = 1,007974... - 1
r = 0,007974... (0,7974% a.m.)
```

---

## Validação Numérica contra HP-12C

Todos os valores abaixo foram validados com calculadora financeira HP-12C.

### Cenário base do usuário

```
PV  = R$ 210.000 (patrimônio atual)
PMT = R$   6.000 (aporte mensal)
```

### Meta 1 — R$ 500.000 (cenário moderado, 10% a.a.)

```
HP-12C:
  PV  = 210.000
  PMT = 6.000
  FV  = 500.000
  i   = 0,7974% a.m.
  n   = ?  →  n ≈ 34 meses
```

Verificação pela fórmula fechada:
```
r = 0,007974
x = (1 + r)^34 = (1,007974)^34 ≈ 1,3134
FV = 210.000 × 1,3134 + 6.000 × [(1,3134 - 1) / 0,007974]
FV ≈ 275.814 + 6.000 × 39,30
FV ≈ 275.814 + 235.800
FV ≈ 511.614  ✓ (acima de 500.000 na iteração do mês 34)
```

**Resultado esperado: 34 meses** (Dezembro de 2028, partindo de Junho de 2026)

### Meta 2 — R$ 1.000.000 (cenário moderado, 10% a.a.)

```
HP-12C:
  PV  = 210.000
  PMT = 6.000
  FV  = 1.000.000
  i   = 0,7974% a.m.
  n   = ?  →  n ≈ 76 meses
```

**Resultado esperado: 76 meses** (Outubro de 2032, partindo de Junho de 2026)

### FIRE Number (regra dos 4%)

```
Gastos mensais = R$ 2.000
FIRE Number    = R$ 2.000 × 300 = R$ 600.000

Derivação da regra dos 4%:
  Patrimônio × 4% / 12 = gasto mensal
  Patrimônio = gasto_mensal × 12 / 0,04 = gasto_mensal × 300

Renda passiva mensal ao atingir FIRE:
  R$ 600.000 × 4% / 12 = R$ 2.000/mês (= gastos mensais, por construção)

% do FIRE atual:
  R$ 210.000 / R$ 600.000 × 100 = 35,00%

Meses para o FIRE (moderado, 10% a.a.):
  HP-12C: PV=210.000, PMT=6.000, FV=600.000, i=0,7974%  →  n ≈ 43 meses
```

**Resultado esperado: 43 meses** (Janeiro de 2030, partindo de Junho de 2026)

---

## Casos de Teste Obrigatórios

Os asserts dos testes devem ser fixados com os valores abaixo ANTES de escrever o código.
Qualquer divergência indica erro na implementação, não nos números.

```
test_taxa_mensal_equivalente_7_pct:
  taxa_anual = Decimal("0.07")
  resultado ≈ Decimal("0.005654")  (tolerância: 6 casas decimais)

test_taxa_mensal_equivalente_10_pct:
  taxa_anual = Decimal("0.10")
  resultado ≈ Decimal("0.007974")  (tolerância: 6 casas decimais)

test_taxa_mensal_equivalente_13_pct:
  taxa_anual = Decimal("0.13")
  resultado ≈ Decimal("0.010236")  (tolerância: 6 casas decimais)

test_projecao_meta_500k_moderado:
  PV=210000, PMT=6000, target=500000, taxa=10% a.a.
  months_to_goal == 34

test_projecao_meta_1M_moderado:
  PV=210000, PMT=6000, target=1000000, taxa=10% a.a.
  months_to_goal == 76

test_fire_number:
  expenses=2000 → fire_number == 600000

test_fire_pct_atual:
  current=210000, fire_number=600000 → pct_of_fire == Decimal("35.00")

test_projecao_meta_ja_atingida:
  PV=600000 > target=500000 → months_to_goal == 0, is_achievable == True

test_projecao_inatingivel:
  PV=0, PMT=0, taxa=0% → months_to_goal == None, is_achievable == False

test_monthly_points_primeiro_elemento_e_o_estado_inicial:
  points[0].month == 0, points[0].value == current_value

test_monthly_points_crescem_monotonicamente_cenario_positivo:
  taxa > 0 e PMT >= 0 → cada ponto deve ser >= anterior
```

---

## Consequências

**Positivo:**
- Fórmula transparente e validada numericamente
- Série mensal disponível para gráficos sem cálculo adicional
- Extensível para aportes variáveis em v2.0

**Negativo:**
- Iteração de até 600 passos por cenário por chamada (3 cenários = 1.800 iterações máximo)
- Negligenciável em performance para o volume deste projeto

**Regra derivada:** Os números desta tabela são os valores de referência dos testes.
Se um teste falhar com um desses valores, o erro está no código, não no test.
Nunca ajustar o assert para "fazer o teste passar" sem revalidar o cálculo.
