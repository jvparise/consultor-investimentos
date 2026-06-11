# InvestorIA V1.2 — Arquitetura

**Versão:** 1.2.0  
**Data:** 2026-06-11  
**Stack:** Python 3.12 · Streamlit · SQLAlchemy 2.x · Alembic · SQLite · pytest · uv

---

## Visão Geral

O InvestorIA é um sistema single-user de gestão patrimonial que roda localmente. Toda a persistência é feita em SQLite via SQLAlchemy ORM. A interface é Streamlit com layout multi-página.

### Camadas

```
┌─────────────────────────────────────────┐
│              UI (Streamlit)             │
│  pages/*.py — sem acesso a Session      │
└─────────────┬───────────────────────────┘
              │ DTOs apenas
┌─────────────▼───────────────────────────┐
│              Services                   │
│  Lógica de negócio + cálculos          │
└─────────────┬───────────────────────────┘
              │ ORM objects
┌─────────────▼───────────────────────────┐
│            Repositories                 │
│  Queries SQLAlchemy — sem negócio       │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│         SQLite (arquivo local)          │
└─────────────────────────────────────────┘
```

**Invariantes:**
1. UI nunca instancia `Session` diretamente — usa `get_db()` e repassa para services
2. `TransactionService.register()` é a única porta de escrita financeira
3. `ImportService.commit()` delega para `TransactionService`
4. Todos os valores monetários são `Decimal`; `float` proibido em cálculos financeiros
5. `transactions.total_amount` sempre em BRL; preços em `asset_prices` na moeda nativa do ativo

---

## Módulos

### database/models.py — Schema ORM

| Modelo | Tabela | Propósito |
|--------|--------|-----------|
| `Asset` | `assets` | Cadastro de ativos (ticker, classe, tipo, moeda) |
| `Transaction` | `transactions` | Movimentações (compra, venda, dividendo, aporte…) |
| `AssetPrice` | `asset_prices` | Histórico de preços/valores por data |
| `PortfolioSnapshot` | `portfolio_snapshots` | Patrimônio total diário |
| `PortfolioSnapshotDetail` | `portfolio_snapshot_details` | Alocação por classe dentro de cada snapshot |
| `Goal` | `goals` | Metas financeiras |
| `ImportLog` | `import_logs` | Audit log de importações (hash SHA-256) |
| `UserSettings` | `user_settings` | Configurações single-user |
| `ExchangeRate` | `exchange_rates` | Cotações USD→BRL, EUR→BRL |

### repositories/

Cada repositório recebe `Session` no construtor e expõe métodos de leitura/escrita tipados. Não contém lógica de negócio.

| Repositório | Responsabilidade principal |
|-------------|---------------------------|
| `AssetRepository` | CRUD de ativos + soft delete/reactivate |
| `ContributionRepository` | CRUD de transações + validação de tipos permitidos |
| `HoldingRepository` | Preços históricos: upsert, latest, period_base |
| `ExchangeRateRepository` | Cotações USD/EUR: get, upsert |
| `PerformanceRepository` | Queries para relatório: price_up_to, income_in_period |
| `SnapshotRepository` | Snapshots diários: upsert, get_latest, get_history |
| `ImportLogRepository` | Audit log: create, has_successful_import |
| `SettingsRepository` | Single-row settings |
| `GoalRepository` | CRUD de metas |

### services/

| Service | Responsabilidade |
|---------|-----------------|
| `TransactionService` | Única porta de escrita financeira; auto-registra preços para INITIAL_BALANCE |
| `ImportService` | validate() sem escrita + commit() all-or-nothing com audit log |
| `PortfolioService` | Posições, alocação, bulk update, métricas de rentabilidade |
| `SnapshotService` | try_auto_snapshot (on load) + ensure_snapshot_for_today (pós-operação) |
| `PerformanceReportService` | Gera PerformanceReportDTO; converte tudo para BRL |
| `ExchangeRateService` | get/set cotações; BRL sempre retorna 1; bloqueia taxa ≤ 0 |
| `SettingsService` | Configurações + CRUD de ativos (com saldo inicial) |
| `GoalService` | Progresso de metas + projeções por cenário |
| `ProjectionService` | Cálculo FIRE (regra dos 4%) e projeções de patrimônio |

### importers/

| Parser | Entrada | Saída |
|--------|---------|-------|
| `csv_parser.parse_csv()` | bytes (CSV formato InvestorIA) | `(list[ImportTransaction], list[str])` |
| `XPParser.parse()` | bytes (CSV ou XLSX XP) | `(list[ImportTransaction], list[str])` |

Ambos retornam o mesmo contrato — a UI e o `ImportService` não distinguem a origem.

---

## Fluxo de Importação

```
bytes do arquivo
       │
       ├─ CSV InvestorIA ──▶ parse_csv()
       │                           │
       └─ XP (CSV/XLSX) ──▶ XPParser.parse()
                                   │
                     list[ImportTransaction]
                                   │
                    ImportService.validate()   ← verifica ativo existe,
                           │                     tipo permitido, qty sell
                    preview (UI)
                           │
                    ImportService.commit()
                           │
                    for each tx:
                      TransactionService.register()  ← escrita real
                           │
                    ImportLogRepository.create()     ← audit log (mesmo commit)
                           │
                    SnapshotService.ensure_snapshot_for_today()
```

**Idempotência:**
- `compute_file_hash(bytes)` → SHA-256
- `validate(txs, file_hash)` consulta `import_logs` antes de qualquer validação financeira
- Se hash já existe com status "success" → retorna `ImportResult(is_duplicate=True)`
- `commit()` só grava o hash após todas as transações bem-sucedidas (atomicidade)

---

## Fluxo de Snapshots

```
App load
  └─▶ SnapshotService.try_auto_snapshot()
        └─ se já existe hoje → skip
        └─ senão → _create_snapshot(today, CALCULATED)

Após BUY/SELL/CONTRIBUTION/INITIAL_BALANCE:
  └─▶ SnapshotService.ensure_snapshot_for_today()
        └─ sempre sobrescreve → estado fresco

_create_snapshot():
  1. get_latest_all_active() → último preço de cada ativo ativo
  2. get_rates() → cotações USD/EUR (+ BRL=1)
  3. para cada ativo:
       currency = asset.currency
       price_brl = convert_to_brl(unit_price, currency, rates)
       if QUANTITY_PRICE: value = qty_liquida × price_brl
       if VALUE_ONLY:     value = price_brl
  4. agrupa por AssetClass → portfolio_snapshot_details
  5. upsert em portfolio_snapshots
```

**Tipos de snapshot:**
- `CALCULATED` — todos os ativos com preço
- `INCOMPLETE` — algum ativo sem preço (marcado para transparência)
- `MANUAL` — criado explicitamente pelo usuário

---

## Fluxo de Moeda Estrangeira

```
Cadastro de ativo
  └─ campo currency (BRL/USD/EUR) → salvo em assets.currency

Atualização de cotação (Configurações → Cotações de Câmbio)
  └─ ExchangeRateService.set_rate(USD, 5.70)
       └─ ExchangeRateRepository.upsert(USD, 5.70)
            └─ tabela exchange_rates (unique por currency)

Leitura de preço
  └─ asset_prices.price = valor em moeda nativa
       ex: USD 520.00 para um ETF americano

Conversão para BRL
  └─ convert_to_brl(value, currency, rates)
       if currency == BRL: return value
       rate = rates.get(currency, Decimal("1"))  ← fallback gracioso
       return (value × rate).quantize("0.000001")

Snapshot / Dashboard / Relatório
  └─ rates = fx_repo.get_rates() + {BRL: 1}
  └─ para cada ativo: price_brl = convert_to_brl(native_price, currency, rates)
  └─ total_amount em transactions sempre em BRL
```

**Invariante de armazenamento:**
- `asset_prices.price` → moeda nativa do ativo
- `transactions.total_amount` → sempre BRL (convertido no momento da entrada)

---

## Fluxo de Relatório Mensal

```
UI: seleciona mês/ano → clica "Gerar Relatório"

PerformanceReportService.generate(year, month):
  1. Calcula datas:
       base_date   = último dia do mês anterior
       period_start = primeiro dia do mês
       period_end   = último dia do mês

  2. Carrega rates (ExchangeRateRepository)

  3. Para cada ativo ativo:
       prev_ap = get_price_up_to(asset_id, base_date)   # último ≤ base_date
       curr_ap = get_price_up_to(asset_id, period_end)  # último ≤ period_end
       appreciation = (curr_brl - prev_brl) ou 0 se algum for None
       income = SUM(total_amount) WHERE type IN (DIVIDEND, INTEREST)
                                    AND date IN [period_start, period_end]
       total_result = appreciation + income

  4. Agrupa rows por AssetClass → subtotais
  5. Soma subtotais → totais gerais
  6. Retorna PerformanceReportDTO

UI: renderiza tabela por classe + resumo + botão CSV
```

---

## ADRs Implementadas

| ADR | Decisão | Status |
|-----|---------|--------|
| ADR-001 | SQLite como banco local (zero infra) | Ativo |
| ADR-002 | Streamlit como framework de UI | Ativo |
| ADR-003 | SQLAlchemy ORM 2.x com mapeamento declarativo | Ativo |
| ADR-004 | Alembic para migrações com `render_as_batch=True` (SQLite) | Ativo |
| ADR-005 | Offline-first, sem serviços externos obrigatórios | Ativo |
| ADR-006 | Dois tipos de rastreamento: QUANTITY_PRICE e VALUE_ONLY | Ativo |
| ADR-007 | Repositórios retornam objetos ORM (não dicts) | Ativo |
| ADR-008 | Services como camada obrigatória entre UI e Repository | Ativo |
| ADR-009 | Decimal para todos os valores financeiros | Ativo |
| ADR-010 | Soft delete em Asset (is_active) | Ativo |
| ADR-011 | Snapshots em modo B: calculado automaticamente (sem polling) | Ativo |
| ADR-012 | Rentabilidade pelo método simplificado (não TWR) | Ativo |
| ADR-013 | Single-user settings (sem autenticação) | Ativo |
| ADR-014 | Saldo inicial como INITIAL_BALANCE, não como preço avulso | Ativo |
| ADR-015 | Fórmula de projeção: valor futuro com aportes mensais | Ativo |
| ADR-016 | Campo description excluído da UI (complexidade vs valor) | Ativo |

---

## Decisões implícitas em V1.2 (candidatas a ADR)

- **Moeda nativa em asset_prices** — preços armazenados na moeda do ativo; conversão sempre on-the-fly via `convert_to_brl()`. Alternativa rejeitada: normalizar para BRL no armazenamento (perderia granularidade para retornar ao nativo).
- **Fallback de taxa = 1** — se cotação não cadastrada, `convert_to_brl` usa taxa 1 (sem crash). Evita quebra de app quando usuário cadastra ativo em USD mas esquece de inserir a cotação.
- **XPParser leniente por linha** — erro em uma linha não interrompe o arquivo; apenas linhas com tipo desconhecido são silenciadas com warning (não erro). Tipos mapeados com ~20 variações de nomenclatura XP.
- **performance_repository separado** — queries de relatório não pertencem a HoldingRepository (propósito diferente: "preço mais recente" vs "preço até uma data específica para fins de comparação").
