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

## ⚙️ Fluxo de Importação
