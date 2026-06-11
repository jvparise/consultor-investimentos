"""Testes unitários para XPParser — CSV e XLSX (sem banco de dados)."""
from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

import openpyxl
import pytest

from consultor_investimentos.config import TransactionType
from consultor_investimentos.importers.xp_parser import XPParser

# ── Helpers ─────────────────────────────────────────────────────────────────────

_HDR = "Data;Movimentação;Ativo;Quantidade;Preço;Valor Financeiro;Observação\n"


def _csv(*rows: str, sep: str = ";", hdr: str = _HDR) -> bytes:
    return (hdr + "\n".join(rows)).encode("utf-8")


def _xlsx(*rows: tuple, headers: tuple = ("Data", "Movimentação", "Ativo", "Quantidade", "Preço", "Valor Financeiro", "Observação")) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Testes CSV ───────────────────────────────────────────────────────────────────

def test_parse_compra_csv() -> None:
    raw = _csv("15/01/2024;Compra;VALE3;100;65,50;6550,00;")
    txs, errors = XPParser().parse(raw)

    assert errors == []
    assert len(txs) == 1
    tx = txs[0]
    assert tx.ticker == "VALE3"
    assert tx.transaction_type == TransactionType.BUY
    assert tx.tx_date == date(2024, 1, 15)
    assert tx.total_amount == Decimal("6550.00")
    assert tx.quantity == Decimal("100")
    assert tx.unit_price == Decimal("65.50")


def test_parse_venda_csv() -> None:
    raw = _csv("01/06/2024;Venda;VALE3;50;70,00;3500,00;")
    txs, errors = XPParser().parse(raw)

    assert errors == []
    tx = txs[0]
    assert tx.transaction_type == TransactionType.SELL
    assert tx.total_amount == Decimal("3500.00")


def test_parse_dividendo_csv() -> None:
    raw = _csv("15/03/2024;Dividendo;VALE3;;;150,00;Dividendos Q1")
    txs, errors = XPParser().parse(raw)

    assert errors == []
    tx = txs[0]
    assert tx.transaction_type == TransactionType.DIVIDEND
    assert tx.total_amount == Decimal("150.00")
    assert tx.notes == "Dividendos Q1"


def test_parse_juros_csv() -> None:
    raw = _csv("10/04/2024;Juros sobre Capital Próprio;ITUB4;;;80,00;JCP abril")
    txs, errors = XPParser().parse(raw)

    assert errors == []
    tx = txs[0]
    assert tx.transaction_type == TransactionType.INTEREST
    assert tx.total_amount == Decimal("80.00")


def test_parse_jcp_abreviado() -> None:
    raw = _csv("10/04/2024;JCP;ITUB4;;;80,00;")
    txs, errors = XPParser().parse(raw)

    assert len(txs) == 1
    assert txs[0].transaction_type == TransactionType.INTEREST


def test_parse_aporte_csv() -> None:
    raw = _csv("20/01/2024;Aporte;CDB-XP;;;5000,00;Aporte mensal")
    txs, errors = XPParser().parse(raw)

    assert errors == []
    tx = txs[0]
    assert tx.transaction_type == TransactionType.CONTRIBUTION
    assert tx.total_amount == Decimal("5000.00")


def test_parse_resgate_csv() -> None:
    raw = _csv("01/07/2024;Resgate;CDB-XP;;;3000,00;")
    txs, errors = XPParser().parse(raw)

    assert errors == []
    assert txs[0].transaction_type == TransactionType.WITHDRAWAL


def test_parse_saldo_inicial_csv() -> None:
    raw = _csv("02/01/2024;Saldo Inicial;VALE3;100;62,00;6200,00;")
    txs, errors = XPParser().parse(raw)

    assert errors == []
    assert txs[0].transaction_type == TransactionType.INITIAL_BALANCE


def test_datas_formato_br() -> None:
    raw = _csv("31/12/2023;Compra;VALE3;10;60,00;600,00;")
    txs, _ = XPParser().parse(raw)
    assert txs[0].tx_date == date(2023, 12, 31)


def test_datas_formato_iso() -> None:
    raw = _csv("2024-06-15;Compra;VALE3;10;60,00;600,00;")
    txs, _ = XPParser().parse(raw)
    assert txs[0].tx_date == date(2024, 6, 15)


def test_valores_formato_br() -> None:
    """1.000,50 deve ser lido como 1000.50."""
    raw = _csv("15/01/2024;Compra;VALE3;100;65,50;6.550,00;")
    txs, _ = XPParser().parse(raw)
    assert txs[0].total_amount == Decimal("6550.00")
    assert txs[0].unit_price == Decimal("65.50")


def test_valores_formato_us() -> None:
    """6,550.00 (formato US) deve ser lido corretamente."""
    raw = _csv("15/01/2024;Compra;IVV;10;500.00;5,000.00;")
    txs, _ = XPParser().parse(raw)
    assert txs[0].total_amount == Decimal("5000.00")
    assert txs[0].unit_price == Decimal("500.00")


def test_arquivo_vazio() -> None:
    txs, errors = XPParser().parse(b"")
    assert txs == []
    assert len(errors) > 0
    assert any("vazio" in e.lower() for e in errors)


def test_somente_cabecalho() -> None:
    txs, errors = XPParser().parse(_HDR.encode())
    assert txs == []
    assert errors == []


def test_linha_invalida_continua() -> None:
    """Linha com data inválida deve gerar erro mas não impedir linhas válidas."""
    raw = _csv(
        "DATA-ERRADA;Compra;VALE3;10;60,00;600,00;",   # inválida
        "15/01/2024;Compra;ITUB4;20;32,00;640,00;",    # válida
    )
    txs, errors = XPParser().parse(raw)

    assert len(txs) == 1
    assert txs[0].ticker == "ITUB4"
    assert len(errors) == 1
    assert "data inválida" in errors[0].lower()


def test_tipo_desconhecido_gera_warning_e_continua() -> None:
    """Tipo não mapeado: warning gerado, linha ignorada, demais processadas."""
    raw = _csv(
        "15/01/2024;TipoEstranho;VALE3;10;60,00;600,00;",  # ignorada
        "15/01/2024;Compra;ITUB4;20;32,00;640,00;",         # válida
    )
    txs, errors = XPParser().parse(raw)

    assert len(txs) == 1
    assert txs[0].ticker == "ITUB4"
    assert any("desconhecido" in e.lower() for e in errors)


def test_multiplas_linhas_validas() -> None:
    raw = _csv(
        "15/01/2024;Compra;VALE3;100;65,50;6550,00;",
        "01/02/2024;Dividendo;VALE3;;;150,00;",
        "01/03/2024;Venda;VALE3;50;70,00;3500,00;",
    )
    txs, errors = XPParser().parse(raw)

    assert errors == []
    assert len(txs) == 3
    types = [t.transaction_type for t in txs]
    assert TransactionType.BUY in types
    assert TransactionType.DIVIDEND in types
    assert TransactionType.SELL in types


def test_separador_virgula() -> None:
    """Suporte a CSV com vírgula como separador."""
    raw = "Data,Movimentação,Ativo,Quantidade,Preço,Valor Financeiro\n15/01/2024,Compra,VALE3,100,65.50,6550.00\n"
    txs, errors = XPParser().parse(raw.encode("utf-8"))

    assert errors == []
    assert txs[0].ticker == "VALE3"
    assert txs[0].transaction_type == TransactionType.BUY


def test_cabecalhos_faltando_retorna_erro_estrutural() -> None:
    """Se colunas obrigatórias estão ausentes, retorna erro estrutural (lista vazia)."""
    raw = "ColA;ColB\nxxx;yyy\n".encode("utf-8")
    txs, errors = XPParser().parse(raw)

    assert txs == []
    assert len(errors) == 1
    assert "colunas obrigatórias" in errors[0].lower()


def test_linhas_vazias_ignoradas() -> None:
    raw = _csv(
        "15/01/2024;Compra;VALE3;100;65,50;6550,00;",
        ";;;;;;;",
        "01/02/2024;Dividendo;VALE3;;;150,00;",
    )
    txs, errors = XPParser().parse(raw)
    assert len(txs) == 2


def test_ticker_normalizado_maiusculo() -> None:
    raw = _csv("15/01/2024;Compra;vale3;100;65,50;6550,00;")
    txs, _ = XPParser().parse(raw)
    assert txs[0].ticker == "VALE3"


# ── Testes XLSX ──────────────────────────────────────────────────────────────────

def test_parse_compra_xlsx() -> None:
    raw = _xlsx(("15/01/2024", "Compra", "VALE3", 100, 65.5, 6550.0, ""))
    txs, errors = XPParser().parse(raw)

    assert errors == []
    assert len(txs) == 1
    assert txs[0].ticker == "VALE3"
    assert txs[0].transaction_type == TransactionType.BUY
    assert txs[0].total_amount == Decimal("6550.0")


def test_parse_dividendo_xlsx() -> None:
    raw = _xlsx(("15/03/2024", "Dividendo", "VALE3", None, None, 150.0, "JCP"))
    txs, errors = XPParser().parse(raw)

    assert errors == []
    assert txs[0].transaction_type == TransactionType.DIVIDEND
    assert txs[0].notes == "JCP"


def test_xlsx_vazio() -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    buf = io.BytesIO()
    wb.save(buf)
    txs, errors = XPParser().parse(buf.getvalue())

    assert txs == []
    assert len(errors) > 0


def test_xlsx_somente_cabecalho() -> None:
    raw = _xlsx()
    txs, errors = XPParser().parse(raw)
    assert txs == []
    assert errors == []


def test_deteccao_automatica_xlsx_vs_csv() -> None:
    """Arquivo XLSX (magic bytes PK) deve ser detectado automaticamente."""
    csv_raw = _csv("15/01/2024;Compra;VALE3;10;65,50;655,00;")
    xlsx_raw = _xlsx(("15/01/2024", "Compra", "VALE3", 10, 65.5, 655.0, ""))

    assert csv_raw[:2] != b"PK"
    assert xlsx_raw[:2] == b"PK"

    txs_csv, _ = XPParser().parse(csv_raw)
    txs_xlsx, _ = XPParser().parse(xlsx_raw)

    assert txs_csv[0].ticker == "VALE3"
    assert txs_xlsx[0].ticker == "VALE3"
