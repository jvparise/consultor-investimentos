"""Importação de dados via CSV InvestorIA ou Extrato XP Investimentos."""
from __future__ import annotations

import io

import streamlit as st

from consultor_investimentos.database.connection import get_db
from consultor_investimentos.importers.csv_parser import compute_file_hash, parse_csv
from consultor_investimentos.importers.xp_parser import XPParser
from consultor_investimentos.services.import_service import ImportService
from consultor_investimentos.services.snapshot_service import SnapshotService
from consultor_investimentos.ui.state import (
    ERROR_MSG,
    IMPORT_FILE_HASH,
    IMPORT_FILE_NAME,
    IMPORT_PARSED_ROWS,
    IMPORT_PREVIEW,
    SUCCESS_MSG,
)

if msg := st.session_state.pop(SUCCESS_MSG, None):
    st.success(msg)
if msg := st.session_state.pop(ERROR_MSG, None):
    st.error(msg)

st.title("⬆️ Importar Dados")

tab_import, tab_model = st.tabs(["⬆️ Importar", "📋 Modelo CSV InvestorIA"])

# ── Tab: Modelo ─────────────────────────────────────────────────────────────────
with tab_model:
    st.subheader("Modelo de Arquivo CSV — Formato InvestorIA")
    st.markdown("""
Faça o download do modelo abaixo e preencha com seus dados.

| Coluna | Descrição | Obrigatório |
|--------|-----------|:-----------:|
| `ticker` | Código do ativo (ex: VALE3) | ✅ |
| `tipo` | Tipo da transação (veja lista abaixo) | ✅ |
| `data` | Data — formato `AAAA-MM-DD` ou `DD/MM/AAAA` | ✅ |
| `valor_total` | Valor total da transação | ✅ |
| `quantidade` | Quantidade de cotas/ações (QUANTITY_PRICE) | — |
| `preco_unitario` | Preço por cota/ação (QUANTITY_PRICE) | — |
| `taxas` | Taxas e corretagem | — |
| `notas` | Observações livres | — |
| `novo_valor_posicao` | Novo valor total da posição após lançamento (VALUE_ONLY) | — |

**Tipos válidos:** `COMPRA`, `VENDA`, `APORTE`, `RESGATE`, `DIVIDENDO`, `JUROS`, `SALDO_INICIAL`, `OUTROS`

**Formatos numéricos aceitos:** `6550.00` ou `6.550,00`
""")

    model_buf = io.StringIO()
    model_buf.write("ticker,tipo,data,valor_total,quantidade,preco_unitario,taxas,notas,novo_valor_posicao\n")
    model_buf.write("VALE3,COMPRA,2024-01-15,6550.00,100,65.50,12.50,Compra inicial,\n")
    model_buf.write("VALE3,VENDA,2024-06-01,3500.00,50,70.00,8.00,,\n")
    model_buf.write("CDB-XP,APORTE,2024-01-20,5000.00,,,,Aporte mensal,55000.00\n")
    model_buf.write("VALE3,DIVIDENDO,2024-03-15,150.00,,,,Dividendos Q1,\n")

    st.download_button(
        label="⬇️ Baixar Modelo CSV",
        data=model_buf.getvalue().encode("utf-8"),
        file_name="modelo_importacao.csv",
        mime="text/csv",
    )

# ── Tab: Importar ───────────────────────────────────────────────────────────────
with tab_import:
    source = st.radio(
        "Tipo de arquivo",
        options=["CSV InvestorIA", "XP Investimentos"],
        horizontal=True,
        help=(
            "**CSV InvestorIA**: formato padrão do sistema.  \n"
            "**XP Investimentos**: extrato exportado diretamente pela corretora (CSV ou XLSX)."
        ),
    )
    is_xp = source == "XP Investimentos"

    if is_xp:
        st.caption(
            "💡 Exporte o extrato pela plataforma XP: "
            "**Extrato → Movimentação → Exportar** (CSV ou Excel)."
        )
        col_enc, _ = st.columns([2, 2])
        with col_enc:
            encoding = st.selectbox("Encoding (para CSV)", ["utf-8", "latin-1"], index=1)
        uploaded = st.file_uploader(
            "Selecione o extrato XP (CSV ou XLSX)",
            type=["csv", "xlsx", "xls", "txt"],
        )
    else:
        col_enc, col_sep = st.columns(2)
        with col_enc:
            encoding = st.selectbox("Encoding", ["utf-8", "latin-1"], index=0)
        with col_sep:
            separator = st.selectbox("Separador", ["auto", ",", ";"], index=0)
        uploaded = st.file_uploader("Selecione o arquivo CSV", type=["csv", "txt"])

    if uploaded is not None:
        if st.button("🔍 Pré-visualizar"):
            raw = uploaded.read()
            file_hash = compute_file_hash(raw)

            if is_xp:
                parser = XPParser()
                transactions, parse_errors = parser.parse(raw, encoding=encoding)
            else:
                transactions, parse_errors = parse_csv(
                    raw,
                    separator=separator,  # type: ignore[possibly-undefined]
                    encoding=encoding,
                )

            # Erros de parse mostrados como warnings (não bloqueantes se houver transações)
            critical_errors = [e for e in parse_errors if not transactions]
            row_warnings = [e for e in parse_errors if transactions]

            if critical_errors:
                for err in critical_errors:
                    st.error(err)
                st.session_state[IMPORT_PARSED_ROWS] = []
                st.session_state[IMPORT_PREVIEW] = None
                st.session_state[IMPORT_FILE_HASH] = None
                st.session_state[IMPORT_FILE_NAME] = None
            elif not transactions:
                st.warning("Nenhuma linha válida encontrada no arquivo.")
                st.session_state[IMPORT_PARSED_ROWS] = []
                st.session_state[IMPORT_PREVIEW] = None
                st.session_state[IMPORT_FILE_HASH] = None
                st.session_state[IMPORT_FILE_NAME] = None
            else:
                if row_warnings:
                    for w in row_warnings:
                        st.warning(w)

                with get_db() as session:
                    preview = ImportService(session).validate(transactions, file_hash=file_hash)
                st.session_state[IMPORT_PARSED_ROWS] = transactions
                st.session_state[IMPORT_PREVIEW] = preview
                st.session_state[IMPORT_FILE_HASH] = file_hash
                st.session_state[IMPORT_FILE_NAME] = uploaded.name

    preview = st.session_state.get(IMPORT_PREVIEW)
    parsed_rows: list = st.session_state.get(IMPORT_PARSED_ROWS, [])

    if preview is not None:
        st.divider()

        if preview.is_duplicate:
            st.warning(
                "⚠️ **Arquivo duplicado** — este arquivo já foi importado anteriormente. "
                "Se precisar reimportar, remova o registro de importação correspondente."
            )
        else:
            col_tot, col_ok, col_err = st.columns(3)
            col_tot.metric("Total de linhas", preview.total_rows)
            col_ok.metric("✅ Válidas", preview.valid_rows)
            col_err.metric("❌ Erros", preview.error_rows)

            def _fmt_brl(value: object) -> str:
                if value is None:
                    return "—"
                return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            table_data = [
                {
                    "Linha": r.row_number,
                    "Ticker": r.ticker,
                    "Tipo": r.transaction_type,
                    "Data": r.tx_date.strftime("%d/%m/%Y") if r.tx_date else "—",
                    "Valor Total": _fmt_brl(r.total_amount),
                    "Status": "✅ OK" if r.status == "ok" else ("⚠️ Aviso" if r.status == "warning" else "❌ Erro"),
                    "Mensagem": r.message or "",
                }
                for r in preview.rows
            ]
            st.dataframe(table_data, use_container_width=True)

            if preview.error_rows > 0:
                st.warning("Corrija os erros acima antes de importar.")

        can_import = not preview.is_duplicate and preview.error_rows == 0 and len(parsed_rows) > 0

        if st.button(
            f"✅ Importar {preview.valid_rows} transação(ões)",
            disabled=not can_import,
            type="primary",
        ):
            file_hash = st.session_state.get(IMPORT_FILE_HASH)
            file_name = st.session_state.get(IMPORT_FILE_NAME)
            try:
                with get_db() as session:
                    ImportService(session).commit(
                        parsed_rows,
                        file_hash=file_hash,
                        file_name=file_name,
                    )
                    SnapshotService(session).ensure_snapshot_for_today()

                st.session_state[SUCCESS_MSG] = (
                    f"{preview.valid_rows} transação(ões) importada(s) com sucesso!"
                )
                st.session_state[IMPORT_PARSED_ROWS] = []
                st.session_state[IMPORT_PREVIEW] = None
                st.session_state[IMPORT_FILE_HASH] = None
                st.session_state[IMPORT_FILE_NAME] = None
                st.rerun()
            except Exception as exc:
                st.session_state[ERROR_MSG] = f"Erro durante importação: {exc}"
                st.rerun()
