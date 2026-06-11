# Release Notes — InvestorIA V1.2.0

**Data:** 2026-06-11  
**Baseline anterior:** V1.1 (Feature 6 — Sistema de Importação)

---

## Novidades

### Feature 7 — Asset Classes V2

Expansão do modelo de classes de ativos para suportar categorias mais granulares:

- **ETF** — categoria independente, separada de Ações
- **FII Tijolo** — fundos de imóveis físicos, separado de FII Papel
- **FII Papel** — fundos de CRI/CRA, separado de FII Tijolo

Inclui migration de dados (`a1b2c3d4e5f6`) que reclassifica FIIs existentes automaticamente e migration de schema (`f7e8d9c0b1a2`) que adiciona colunas de alocação-alvo para as novas classes.

### Feature 8 — Suporte a Moeda Estrangeira (USD/EUR)

Suporte completo a ativos em dólar e euro:

- Campo `currency` em `assets` (BRL/USD/EUR, default BRL)
- Tabela `exchange_rates` para cotações USD→BRL e EUR→BRL
- `ExchangeRateRepository` + `ExchangeRateService` para gestão de cotações
- `convert_to_brl(value, currency, rates)` em `utils/currency.py`
- Conversão automática no Dashboard, Carteira, Snapshot e Relatório Mensal
- Seção "Cotações de Câmbio" nas Configurações
- Suporte a entrada de valores em moeda nativa nas Transações e Atualizar Posições
- Preços armazenados em moeda nativa; `total_amount` sempre em BRL

### Feature 9 — Relatório Mensal de Performance

Nova página "Relatório Mensal" com análise de resultados por período:

- Seletor mês/ano + botão "Gerar Relatório"
- Por ativo: preço base (último até fim do mês anterior), preço atual, valorização, rendimentos (DIVIDEND + INTEREST), resultado total
- Agrupamento por classe de ativo com subtotais
- Totais gerais da carteira
- Exportação CSV em memória (sem arquivo físico)
- Cores verde/vermelho para valores positivos/negativos

### Feature 10 — Importação de Extratos XP Investimentos

Importação direta de extratos XP sem conversão manual:

- `XPParser` com detecção automática CSV vs XLSX (magic bytes PK)
- Mapeamento de ~20 variações de tipo XP para `TransactionType`
- Headers detectados de forma flexível (sem acentos, case-insensitive)
- Parsing leniente: erro de linha gera warning, processamento continua
- Reutiliza integralmente `ImportService.validate()` e `ImportService.commit()`
- Idempotência e audit log funcionam da mesma forma que o CSV InvestorIA
- UI com seletor "CSV InvestorIA / XP Investimentos" na mesma página de importação
- Dependência adicionada: `openpyxl>=3.1.5`

---

## Melhorias

### UX — Atualizar Posições

- Suporte a tecla Enter para salvar (via `st.form`)
- Valores limpados após salvar
- Dashboard atualizado imediatamente após salvar (via `ensure_snapshot_for_today()`)
- Parser decimal aceita tanto `1000.12` (ponto) quanto `1.000,12` (BR)
- Base de comparação configurável: mês atual ou ano atual
- Exibe variação percentual em relação à base selecionada
- Ativos em moeda estrangeira mostram valor nativo e BRL lado a lado

### UX — Transações

- Ativos em USD/EUR exibem opção de inserir valor na moeda nativa
- Taxa de câmbio pré-preenchida a partir da cotação salva nas Configurações
- Cálculo em tempo real do total em BRL

### Gráfico — Evolução Patrimonial

- Eixo X corrigido: datas explícitas com `tickvals`/`ticktext` (antes mostrava apenas uma data)
- Formato dinâmico: `%d/%b` (≤60d), `%d/%b/%y` (≤365d), `%b/%y` (maior)
- Espaçamento automático: máximo 8 ticks, sempre inclui a data mais recente

---

## Correções

- `get_value_only_assets_for_update()` retornava erro com `period_start` após cache de bytecode desatualizado — corrigido limpando `__pycache__`
- Separador decimal: ponto era incorretamente tratado como milhar em valores como `1000.12` — corrigido com detecção por posição relativa de `.` e `,`
- Eixo X do gráfico histórico exibia "07/Jun" fixo em vez das datas reais dos snapshots

---

## Arquitetura

### Novos módulos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `importers/xp_parser.py` | Converte extrato XP → `ImportTransaction` |
| `repositories/exchange_rate_repository.py` | CRUD de cotações USD/EUR |
| `repositories/performance_repository.py` | Queries para relatório de performance |
| `services/exchange_rate_service.py` | Lógica de negócio de cotações |
| `services/performance_report_service.py` | Geração do relatório mensal |
| `ui/pages/performance_report.py` | UI do relatório mensal |
| `utils/currency.py` | `convert_to_brl()` |

### Novos DTOs (services/dto.py)

- `PerformanceRowDTO` — linha do relatório (por ativo)
- `PerformanceClassSummaryDTO` — subtotal por classe
- `PerformanceReportDTO` — relatório completo com totais

### Princípios mantidos

- UI não acessa `Session` diretamente em nenhum novo módulo
- `TransactionService` não foi modificado
- `ImportService` não foi modificado
- `SnapshotService` não foi modificado
- `CsvParser` não foi modificado

---

## Migrações de Banco de Dados

| Revision | Descrição |
|----------|-----------|
| `6690aa5c7f86` | Schema inicial (baseline V1.0) |
| `a1b2c3d4e5f6` | Migra `asset_class = "FII"` → `"FII Tijolo"` |
| `f7e8d9c0b1a2` | Adiciona `target_etf_pct`, `target_fii_brick_pct`, `target_fii_paper_pct`; remove `target_fii_pct` |
| `c1d2e3f4a5b6` | Adiciona coluna `currency` em `assets` (default `'BRL'`) |
| `d2e3f4a5b6c7` | Cria tabela `exchange_rates` |

---

## Estatísticas

| Métrica | Valor |
|---------|-------|
| Arquivos criados | 10 |
| Arquivos modificados | 16 |
| Migrations novas | 4 (2 de schema + 2 de Feature 8) |
| Testes totais | 379 |
| Suítes de teste | 26 (16 unit + 10 integration) |
| Testes novos nesta release | 54 |
| Dependências novas | 1 (`openpyxl`) |
| Linhas adicionadas (diff) | ~500 |
