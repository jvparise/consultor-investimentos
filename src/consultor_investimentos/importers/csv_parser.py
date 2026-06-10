"""Parser CSV puro — sem acesso a banco de dados."""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from consultor_investimentos.config import TransactionType
from consultor_investimentos.services.dto import ImportTransaction

def compute_file_hash(data: bytes) -> str:
    """SHA256 do conteúdo bruto do arquivo — identificador para detecção de duplicatas."""
    return hashlib.sha256(data).hexdigest()


_TYPE_MAP: dict[str, TransactionType] = {
    "COMPRA": TransactionType.BUY,
    "VENDA": TransactionType.SELL,
    "APORTE": TransactionType.CONTRIBUTION,
    "RESGATE": TransactionType.WITHDRAWAL,
    "DIVIDENDO": TransactionType.DIVIDEND,
    "JUROS": TransactionType.INTEREST,
    "SALDO_INICIAL": TransactionType.INITIAL_BALANCE,
    "OUTROS": TransactionType.OTHER,
}

_REQUIRED_COLS = {"ticker", "tipo", "data", "valor_total"}


def _detect_separator(text: str) -> str:
    first_line = text.split("\n", 1)[0]
    return ";" if first_line.count(";") >= first_line.count(",") else ","


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: str) -> Decimal | None:
    value = value.strip()
    if not value:
        return None
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            # BR: "6.550,00" — ponto = milhar, vírgula = decimal
            value = value.replace(".", "").replace(",", ".")
        else:
            # US: "6,550.00" — vírgula = milhar, ponto = decimal
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def parse_csv(
    data: bytes,
    separator: str = "auto",
    encoding: str = "utf-8",
) -> tuple[list[ImportTransaction], list[str]]:
    """Parse arquivo CSV de importação.

    Returns:
        Tupla (transações válidas, erros de parse). Postura leniente: extrai o máximo
        possível e reporta erros por linha sem abortar silenciosamente.
    """
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        return [], [f"Falha ao decodificar arquivo com encoding '{encoding}'"]

    if not text.strip():
        return [], ["Arquivo vazio"]

    if separator == "auto":
        separator = _detect_separator(text)

    reader = csv.DictReader(io.StringIO(text), delimiter=separator)

    if not reader.fieldnames:
        return [], ["Cabeçalho não encontrado"]

    fieldnames_lower = {col.strip().lower() for col in reader.fieldnames}
    missing = _REQUIRED_COLS - fieldnames_lower
    if missing:
        return [], [f"Colunas obrigatórias ausentes: {', '.join(sorted(missing))}"]

    rows = list(reader)
    if not rows:
        return [], []

    transactions: list[ImportTransaction] = []
    errors: list[str] = []

    for row_num, row in enumerate(rows, start=2):
        norm = {
            (k.strip().lower() if k else ""): (v.strip() if v else "")
            for k, v in row.items()
            if k is not None
        }

        ticker_val = norm.get("ticker", "").upper()
        tipo_raw = norm.get("tipo", "").upper()
        data_raw = norm.get("data", "")
        valor_raw = norm.get("valor_total", "")

        row_errors: list[str] = []

        if not ticker_val:
            row_errors.append("ticker vazio")

        tx_type: TransactionType | None = None
        if not tipo_raw:
            row_errors.append("tipo vazio")
        elif tipo_raw not in _TYPE_MAP:
            row_errors.append(f"tipo desconhecido: '{tipo_raw}'")
        else:
            tx_type = _TYPE_MAP[tipo_raw]

        tx_date: date | None = None
        if not data_raw:
            row_errors.append("data vazia")
        else:
            tx_date = _parse_date(data_raw)
            if tx_date is None:
                row_errors.append(f"data inválida: '{data_raw}'")

        total_amount: Decimal | None = None
        if not valor_raw:
            row_errors.append("valor_total vazio")
        else:
            total_amount = _parse_decimal(valor_raw)
            if total_amount is None:
                row_errors.append(f"valor_total inválido: '{valor_raw}'")

        if row_errors:
            errors.extend(f"Linha {row_num}: {e}" for e in row_errors)
            continue

        quantity = _parse_decimal(norm.get("quantidade", ""))
        unit_price = _parse_decimal(norm.get("preco_unitario", ""))
        fees_raw = norm.get("taxas", "")
        fees = _parse_decimal(fees_raw) if fees_raw else Decimal("0")
        if fees is None:
            fees = Decimal("0")
        new_pos_raw = norm.get("novo_valor_posicao", "")
        new_position_value = _parse_decimal(new_pos_raw) if new_pos_raw else None
        notes_raw = norm.get("notas", "")
        notes = notes_raw or None

        transactions.append(
            ImportTransaction(
                ticker=ticker_val,
                transaction_type=tx_type,  # type: ignore[arg-type]
                tx_date=tx_date,  # type: ignore[arg-type]
                total_amount=total_amount,  # type: ignore[arg-type]
                quantity=quantity,
                unit_price=unit_price,
                fees=fees,
                notes=notes,
                new_position_value=new_position_value,
                row_number=row_num,
            )
        )

    return transactions, errors
