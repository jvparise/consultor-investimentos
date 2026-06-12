# Release Notes — InvestorIA V1.4.0

**Data:** 2026-06-12  
**Baseline anterior:** V1.3 (Atualização Automática de Preços)

---

## Novidades

### Feature 11 — Benchmark e Histórico de Índices

Comparação histórica da carteira contra os principais índices de mercado:

- **Tabela `benchmark_history`** — armazena histórico diário de CDI, SELIC, IPCA, Ibovespa e S&P500 com constraint única por `(benchmark_name, reference_date)`
- **`BenchmarkRepository`** — `upsert`, `get_latest`, `get_history`, `exists`; suporte a filtros de data
- **`BenchmarkService`** — três operações centrais:
  - `update_benchmarks()` — busca CDI/SELIC/IPCA via SGS (Banco Central) e IBOV/SP500 via Yahoo Finance; update incremental (só busca registros após o último disponível)
  - `get_benchmark_series()` — retorna série normalizada em base 100 para um benchmark específico
  - `compare_with_portfolio()` — retorna `PortfolioVsBenchmarkDTO` com carteira + todos os benchmarks normalizados em base 100
- **Normalização base 100** — cada série inicia em 100 na primeira data disponível; CDI/SELIC/IPCA compostos (fator acumulado); IBOV/SP500 por divisão pelo valor inicial
- **Update incremental** — segunda execução busca apenas dados posteriores ao último registro no banco; não há duplicatas
- **Integração com `MarketDataService`** — `update_benchmarks()` delega para `BenchmarkService`; providers injetáveis (DI) para testabilidade
- **Página `📊 Benchmark`** — seletor de período (30d / 90d / 180d / 1 ano / 3 anos / Desde o início), gráfico de linhas com todas as séries, tabela de rentabilidade e diferença para CDI, status de última atualização por índice, botão "Atualizar benchmarks"
- **DTOs novos** — `BenchmarkPointDTO`, `BenchmarkSeriesDTO`, `PortfolioVsBenchmarkDTO` em `services/dto.py`
- **`Benchmark` enum** — `CDI`, `SELIC`, `IPCA`, `IBOV`, `SP500` em `config.py`

---

## Princípios mantidos

- Página não consulta internet — usa somente `benchmark_history` e `portfolio_snapshots` já persistidos
- Falha em um benchmark não interrompe os demais
- Nenhuma chamada externa nos testes (Yahoo e BCB mockados)
- Arquitetura Repository → Service → UI preservada

---

## Migrações de Banco de Dados

| Revision | Descrição |
|----------|-----------|
| `e3f4a5b6c7d8` | Cria tabela `benchmark_history` com índice e constraint única |

---

## Estatísticas

| Métrica | Valor |
|---------|-------|
| Arquivos criados | 8 |
| Arquivos modificados | 9 |
| Migrations novas | 1 |
| Testes totais | 475 |
| Testes novos | 38 (14 unit repo + 16 unit service + 8 integration) |
| Suítes de teste | 32 (22 unit + 10 integration) |
