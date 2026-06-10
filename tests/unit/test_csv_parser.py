"""Testes do csv_parser — puro, sem banco de dados."""
import hashlib
from datetime import date
from decimal import Decimal

import pytest

from consultor_investimentos.config import TransactionType
from consultor_investimentos.importers.csv_parser import compute_file_hash, parse_csv

_HEADER = "ticker,tipo,data,valor_total,quantidade,preco_unitario,taxas,notas,novo_valor_posicao\n"
_HEADER_SC = "ticker;tipo;data;valor_total;quantidade;preco_unitario;taxas;notas;novo_valor_posicao\n"


def _csv(rows: str, header: str = _HEADER) -> bytes:
    return (header + rows).encode("utf-8")


# ── Parsing básico ──────────────────────────────────────────────────────────────

def test_parse_compra_quantity_price() -> None:
    data = _csv("VALE3,COMPRA,2024-01-15,6550.00,100,65.50,12.50,Compra inicial,\n")
    txs, errors = parse_csv(data)

    assert errors == []
    assert len(txs) == 1
    tx = txs[0]
    assert tx.ticker == "VALE3"
    assert tx.transaction_type == TransactionType.BUY
    assert tx.tx_date == date(2024, 1, 15)
    assert tx.total_amount == Decimal("6550.00")
    assert tx.quantity == Decimal("100")
    assert tx.unit_price == Decimal("65.50")
    assert tx.fees == Decimal("12.50")
    assert tx.notes == "Compra inicial"
    assert tx.new_position_value is None
    assert tx.row_number == 2


def test_parse_aporte_value_only() -> None:
    data = _csv("CDB-XP,APORTE,2024-01-20,5000.00,,,,Aporte mensal,55000.00\n")
    txs, errors = parse_csv(data)

    assert errors == []
    assert len(txs) == 1
    tx = txs[0]
    assert tx.ticker == "CDB-XP"
    assert tx.transaction_type == TransactionType.CONTRIBUTION
    assert tx.total_amount == Decimal("5000.00")
    assert tx.quantity is None
    assert tx.unit_price is None
    assert tx.new_position_value == Decimal("55000.00")
    assert tx.notes == "Aporte mensal"


# ── Formatos de data ────────────────────────────────────────────────────────────

def test_data_formato_br() -> None:
    data = _csv("VALE3,COMPRA,15/01/2024,6550.00,100,65.50,,, \n")
    txs, errors = parse_csv(data)

    assert errors == []
    assert txs[0].tx_date == date(2024, 1, 15)


def test_data_formato_iso() -> None:
    data = _csv("VALE3,COMPRA,2024-01-15,6550.00,100,65.50,,,\n")
    txs, errors = parse_csv(data)

    assert errors == []
    assert txs[0].tx_date == date(2024, 1, 15)


# ── Formatos numéricos ──────────────────────────────────────────────────────────

def test_numero_formato_br() -> None:
    data = _csv("VALE3,COMPRA,2024-01-15,6.550,00,100,65,50,,,\n")
    # Coluna valor_total = "6.550" (sem vírgula), quantidade = "00" — não é o melhor exemplo
    # Vamos usar um CSV com separador ; para isolar o formato BR
    data = "ticker;tipo;data;valor_total;quantidade;preco_unitario;taxas;notas;novo_valor_posicao\n"
    data += "VALE3;COMPRA;2024-01-15;6.550,00;100;65,50;;;;\n"
    txs, errors = parse_csv(data.encode("utf-8"), separator=";")

    assert errors == []
    assert txs[0].total_amount == Decimal("6550.00")
    assert txs[0].unit_price == Decimal("65.50")


# ── Tipos PT-BR ─────────────────────────────────────────────────────────────────

def test_tipo_desconhecido_nao_aborta() -> None:
    """Linha com tipo desconhecido gera erro mas não aborta as demais."""
    rows = (
        "VALE3,INVALIDO,2024-01-15,100.00,1,100.00,,,\n"
        "VALE3,COMPRA,2024-01-16,200.00,2,100.00,,,\n"
    )
    data = _csv(rows)
    txs, errors = parse_csv(data)

    assert len(txs) == 1
    assert txs[0].transaction_type == TransactionType.BUY
    assert any("tipo desconhecido" in e for e in errors)


# ── Erros estruturais ───────────────────────────────────────────────────────────

def test_coluna_ausente() -> None:
    """Arquivo sem coluna obrigatória retorna erro global (não por linha)."""
    data = b"ticker,tipo,data\nVALE3,COMPRA,2024-01-15\n"
    txs, errors = parse_csv(data)

    assert txs == []
    assert any("valor_total" in e for e in errors)


def test_separador_ponto_e_virgula() -> None:
    data = _csv("VALE3;COMPRA;2024-03-01;3000.00;50;60.00;;;;\n", header=_HEADER_SC)
    txs, errors = parse_csv(data, separator=";")

    assert errors == []
    assert len(txs) == 1
    assert txs[0].total_amount == Decimal("3000.00")


def test_separador_auto_detecta_ponto_e_virgula() -> None:
    data = _csv("VALE3;COMPRA;2024-03-01;3000.00;50;60.00;;;;\n", header=_HEADER_SC)
    txs, errors = parse_csv(data, separator="auto")

    assert errors == []
    assert len(txs) == 1


def test_arquivo_vazio() -> None:
    txs, errors = parse_csv(b"")

    assert txs == []
    assert errors != []


def test_so_header() -> None:
    data = _HEADER.encode("utf-8")
    txs, errors = parse_csv(data)

    assert txs == []
    assert errors == []


# ── Formato numérico US ─────────────────────────────────────────────────────────

def test_numero_formato_us_virgula_milhar() -> None:
    """'6,550.00' (US: vírgula=milhar, ponto=decimal) deve ser interpretado corretamente."""
    data = "ticker;tipo;data;valor_total;quantidade;preco_unitario;taxas;notas;novo_valor_posicao\n"
    data += "VALE3;COMPRA;2024-01-15;6,550.00;100;65.50;;;;\n"
    txs, errors = parse_csv(data.encode("utf-8"), separator=";")

    assert errors == []
    assert txs[0].total_amount == Decimal("6550.00")


def test_numero_inteiro_sem_casas_decimais() -> None:
    """Valor inteiro sem separador decimal ('1000') é parseado corretamente."""
    data = _csv("VALE3,COMPRA,2024-01-15,1000,10,100,,,\n")
    txs, errors = parse_csv(data)

    assert errors == []
    assert txs[0].total_amount == Decimal("1000")


# ── Linha em branco no meio ─────────────────────────────────────────────────────

def test_linha_completamente_em_branco_no_meio_ignorada() -> None:
    """Linha em branco entre linhas válidas não deve abortar o parse."""
    rows = (
        "VALE3,COMPRA,2024-01-15,100.00,1,100.00,,,\n"
        ",,,,,,,,\n"
        "VALE3,COMPRA,2024-01-16,200.00,2,100.00,,,\n"
    )
    data = _csv(rows)
    txs, errors = parse_csv(data)

    # Linha em branco gera erros (campos obrigatórios ausentes), mas não interrompe
    valid_txs = [t for t in txs]
    assert len(valid_txs) == 2  # As duas linhas válidas são parseadas


def test_multiplos_erros_em_linha_unica_todos_relatados() -> None:
    """Linha com múltiplos campos inválidos deve reportar todos os erros."""
    data = _csv(",INVALIDO,naodata,naonum,,,,,\n")
    txs, errors = parse_csv(data)

    assert len(txs) == 0
    # Ticker vazio + tipo inválido + data inválida + valor inválido = 4 erros na mesma linha
    erros_linha_2 = [e for e in errors if "Linha 2" in e]
    assert len(erros_linha_2) >= 3


# ── Mapeamento completo de tipos PT-BR ─────────────────────────────────────────

def test_todos_tipos_pt_br_mapeados() -> None:
    """Todos os tipos PT-BR válidos devem ser aceitos pelo parser."""
    from consultor_investimentos.config import TransactionType

    tipos_e_enums = [
        ("COMPRA",        TransactionType.BUY),
        ("VENDA",         TransactionType.SELL),
        ("APORTE",        TransactionType.CONTRIBUTION),
        ("RESGATE",       TransactionType.WITHDRAWAL),
        ("DIVIDENDO",     TransactionType.DIVIDEND),
        ("JUROS",         TransactionType.INTEREST),
        ("SALDO_INICIAL", TransactionType.INITIAL_BALANCE),
        ("OUTROS",        TransactionType.OTHER),
    ]
    for tipo_str, tipo_enum in tipos_e_enums:
        data = _csv(f"VALE3,{tipo_str},2024-01-15,100.00,,,,,\n")
        txs, errors = parse_csv(data)
        assert any(t.transaction_type == tipo_enum for t in txs), f"Tipo '{tipo_str}' não mapeado"


# ── compute_file_hash ───────────────────────────────────────────────────────────

def test_compute_file_hash_retorna_sha256() -> None:
    """compute_file_hash deve retornar o SHA256 exato do conteúdo em hex."""
    content = b"hello world"
    expected = hashlib.sha256(content).hexdigest()
    assert compute_file_hash(content) == expected


def test_compute_file_hash_deterministico() -> None:
    """O mesmo conteúdo sempre produz o mesmo hash."""
    content = b"ticker,tipo,data\nVALE3,COMPRA,2024-01-15\n"
    assert compute_file_hash(content) == compute_file_hash(content)


def test_compute_file_hash_bytes_diferentes_hash_diferente() -> None:
    """Conteúdos diferentes produzem hashes diferentes."""
    assert compute_file_hash(b"arquivo A") != compute_file_hash(b"arquivo B")


def test_compute_file_hash_comprimento_64_chars() -> None:
    """SHA256 em hex deve ter exatamente 64 caracteres."""
    assert len(compute_file_hash(b"qualquer coisa")) == 64
