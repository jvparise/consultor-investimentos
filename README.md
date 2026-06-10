# 📊 InvestorIA

Sistema de investimentos com motor de importação de transações financeiras, validação de consistência e auditoria completa.

---

## 🚀 Visão Geral

O InvestorIA é um sistema para gerenciamento de carteira de investimentos com foco em:

- Importação de dados financeiros via CSV/XLSX
- Garantia de consistência de saldo (running quantity)
- Idempotência de arquivos importados
- Auditoria completa de operações
- Snapshot automático de estado da carteira

---

## 🧱 Arquitetura

O sistema segue arquitetura rígida:

Repository → Service → UI

Regras:

- UI não acessa banco diretamente
- Regras de negócio ficam em services
- TransactionService é a única porta de escrita financeira

---

## 🆕 Novidades da v1.2

✓ Importação de extratos CSV/XLSX com preview de validação  
✓ Idempotência por hash de arquivo  
✓ Audit log de importações  
✓ Atualização em lote de ativos VALUE_ONLY  
✓ Inputs monetários no formato brasileiro (R$ 1.234,56)  
✓ Modo privacidade (oculta valores sensíveis na tela)  
✓ Classes de ativos V2
  - ETF — categoria independente de Ações
  - FII Tijolo — separado de FII Papel
  - FII Papel — separado de FII Tijolo

---

## ⚙️ Fluxo de Importação
