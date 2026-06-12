# InvestorIA

Sistema pessoal de gestão patrimonial — acompanhamento de carteira, relatórios de performance, importação de extratos e projeções FIRE.

---

## Funcionalidades

| Módulo | Descrição |
|--------|-----------|
| **Dashboard** | Visão geral do patrimônio, metas e próxima alocação recomendada |
| **Benchmark** | Comparação da carteira vs CDI, SELIC, IPCA, Ibovespa e S&P500 em base 100 |
| **Carteira** | Posições atuais, rentabilidade, alocação por classe e projeções FIRE |
| **Relatório Mensal** | Performance por ativo e classe: valorização, dividendos, resultado total |
| **Atualizar Cotações** | Atualização automática de preços via Yahoo Finance e câmbio via Banco Central |
| **Atualizar Posições** | Atualização em lote de ativos VALUE_ONLY (fundos, renda fixa) com comparação mês/ano |
| **Transações** | Registro e histórico de movimentações por ativo |
| **Importar** | Importação via CSV InvestorIA ou extrato XP Investimentos (CSV/XLSX) |
| **Metas** | Metas financeiras com projeção por cenário |
| **Histórico** | Evolução patrimonial com gráfico de área |
| **Configurações** | Cadastro de ativos, cotações de câmbio (USD/EUR), alocação-alvo |

### Destaques

- **Moeda estrangeira** — ativos em USD e EUR com conversão automática para BRL no dashboard, carteira, snapshots e relatório
- **Modo privacidade** — oculta todos os valores monetários com um toggle na sidebar
- **Importação XP Investimentos** — ingere extratos exportados diretamente pela corretora (CSV ou Excel) sem conversão manual
- **Audit log + idempotência** — cada arquivo importado é identificado por SHA-256; reimportações são bloqueadas automaticamente
- **Snapshot diário automático** — patrimônio calculado e armazenado ao abrir o app e após cada operação relevante

---

## Instalação

**Pré-requisitos:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
git clone <repo>
cd consultor-investimentos
uv sync
uv run alembic upgrade head
```

---

## Execução

```bash
uv run streamlit run src/consultor_investimentos/app.py
```

Acesse `http://localhost:8501` no navegador.

---

## Testes

```bash
uv run pytest tests/ -q
```

475 testes — 32 suítes (22 unit + 10 integration).

---

## Estrutura do Projeto

```
consultor-investimentos/
├── src/consultor_investimentos/
│   ├── app.py                            # Entry point Streamlit + menu de navegação
│   ├── config.py                         # Enums e constantes (AssetClass, Currency, TransactionType…)
│   ├── database/
│   │   ├── connection.py                 # Engine SQLite + get_db() context manager
│   │   └── models.py                     # ORM: Asset, Transaction, AssetPrice, ExchangeRate, …
│   ├── importers/
│   │   ├── csv_parser.py                 # Parser formato InvestorIA + compute_file_hash
│   │   └── xp_parser.py                  # Parser extrato XP (CSV e XLSX, detecção automática)
│   ├── repositories/                     # Acesso a dados — sem lógica de negócio
│   │   ├── asset_repository.py
│   │   ├── contribution_repository.py
│   │   ├── exchange_rate_repository.py
│   │   ├── holding_repository.py
│   │   ├── import_log_repository.py
│   │   ├── performance_repository.py
│   │   ├── settings_repository.py
│   │   └── snapshot_repository.py
│   ├── services/
│   │   ├── dto.py                        # Data Transfer Objects
│   │   ├── exchange_rate_service.py      # Gestão de cotações USD/EUR
│   │   ├── import_service.py             # validate() + commit() — porta de importação em lote
│   │   ├── performance_report_service.py # Relatório mensal de performance
│   │   ├── portfolio_service.py          # Posições, alocação, bulk update de preços
│   │   ├── projection_service.py         # Cálculos FIRE e projeções
│   │   ├── settings_service.py           # Configurações do usuário e ativos
│   │   ├── snapshot_service.py           # Snapshots diários do patrimônio
│   │   └── transaction_service.py        # Única porta de escrita de transações
│   ├── ui/
│   │   ├── pages/                        # Páginas Streamlit (uma por módulo)
│   │   ├── components/
│   │   │   ├── charts.py                 # Gráficos Plotly (área patrimonial, pizza de alocação)
│   │   │   └── metrics.py                # Formatadores: fmt_brl, fmt_date_br, fmt_qty…
│   │   └── state.py                      # Chaves de session_state
│   └── utils/
│       ├── brl.py                        # parse_brl() e fmt_brl_input()
│       └── currency.py                   # convert_to_brl(value, currency, rates)
├── migrations/
│   └── versions/                         # 5 migrations Alembic
├── tests/
│   ├── conftest.py                       # Engine SQLite in-memory + fixtures compartilhadas
│   ├── integration/                      # 10 suítes — estado commitado entre operações
│   └── unit/                             # 16 suítes — lógica isolada
├── docs/
│   ├── adr/                              # 16 Architecture Decision Records
│   └── architecture/                     # Documentos de arquitetura por versão
└── pyproject.toml
```

---

## Arquitetura

```
UI (Streamlit pages)
    ↓  apenas DTOs — nunca Session
Services (regras de negócio)
    ↓  queries e escritas
Repositories (SQLAlchemy 2.x)
    ↓
SQLite (arquivo local)
```

**Princípios:**
- UI nunca acessa `Session` diretamente
- `TransactionService.register()` é a única porta de escrita financeira
- `ImportService` delega escritas para `TransactionService`
- Todos os valores monetários usam `Decimal` (nunca `float`)
- Preços em moeda nativa; `transactions.total_amount` sempre em BRL

---

## Tipos de Ativo

| Tracking | Descrição | Exemplos |
|----------|-----------|---------|
| `QUANTITY_PRICE` | Quantidade × preço unitário | Ações, ETFs, FIIs, Cripto |
| `VALUE_ONLY` | Valor total da posição | CDB, LCI/LCA, Tesouro Direto, Fundos |

## Classes de Ativos

`Ações` · `ETF` · `FII Tijolo` · `FII Papel` · `Renda Fixa` · `Internacional` · `Cripto` · `Caixa / Liquidez` · `Outros`

## Moedas Suportadas

`BRL` (padrão) · `USD` · `EUR`

---

## Roadmap V1.5

- Relatório anual consolidado
- Exportação de relatórios para XLSX
- Notificações de rebalanceamento
- Suporte a mais moedas (GBP, CHF)
- Comparação de carteira com benchmarks personalizados
