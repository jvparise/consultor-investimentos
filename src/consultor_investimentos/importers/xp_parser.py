"""Parser para extratos da XP Investimentos (CSV e XLSX).

Formato XP esperado (colunas detectadas de forma flexível, sem ordem fixa):
  Data | Movimentação | Ativo | Quantidade | Preço | Valor Financeiro | Observação

Retorna o mesmo contrato de CsvParser:
  (list[ImportTransaction], list[str])

Erros de linha são acumulados sem interromper o processamento.
Erros estruturais (arquivo vazio, colunas obrigatórias ausentes) interrompem.
"""
from __future__ import annotations

import csv
import io
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from consultor_investimentos.config import TransactionType
from consultor_investimentos.importers.csv_parser import compute_file_hash  # noqa: F401 — re-export
from consultor_investimentos.services.dto import ImportTransaction

__all__ = ["XPParser", "compute_file_hash"]

# ── Normalização de headers ────────────────────────────────────────────────────


def _norm(s: str) -> str:
    """Remove acentos, converte para minúsculas e colapsa espaços."""
    ascii_str = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(ascii_str.strip().lower().split())


# Candidatos normalizados para cada campo (sem acentos, minúsculas)
_COL_DATE  = {"data", "date", "data liquidacao", "data negociacao"}
_COL_TYPE  = {"movimentacao", "tipo", "type", "operacao", "lancamento", "descricao", "historico"}
_COL_TICK  = {"ativo", "ticker", "papel", "codigo", "codigo do ativo", "ativo/fundo", "produto"}
_COL_QTY   = {"quantidade", "qtd", "qty", "quantity", "cotas", "quantidade de ativos"}
_COL_PRICE = {"preco", "price", "preco unitario", "valor unitario", "cotacao", "pu"}
_COL_TOTAL = {
    "valor financeiro", "valor", "total", "financeiro", "bruto", "montante",
    "valor total", "valor bruto", "net", "valor liquido",
}
_COL_NOTES = {"observacao", "obs", "notas", "notes", "complemento", "informacoes"}

# ── Mapeamento tipo XP → TransactionType ──────────────────────────────────────

_XP_TYPE_MAP: dict[str, TransactionType] = {
    "compra": TransactionType.BUY,
    "venda": TransactionType.SELL,
    "dividendo": TransactionType.DIVIDEND,
    "dividendos": TransactionType.DIVIDEND,
    "juros sobre capital proprio": TransactionType.INTEREST,
    "jcp": TransactionType.INTEREST,
    "juros": TransactionType.INTEREST,
    "cupom": TransactionType.INTEREST,
    "aporte": TransactionType.CONTRIBUTION,
    "aplicacao": TransactionType.CONTRIBUTION,
    "deposito": TransactionType.CONTRIBUTION,
    "credito": TransactionType.CONTRIBUTION,
    "resgate": TransactionType.WITHDRAWAL,
    "retirada": TransactionType.WITHDRAWAL,
    "debito": TransactionType.WITHDRAWAL,
    "saldo inicial": TransactionType.INITIAL_BALANCE,
    "rendimento": TransactionType.INTEREST,
    "rendimentos": TransactionType.INTEREST,
    "outros": TransactionType.OTHER,
    "outro": TransactionType.OTHER,
}

# ── Helpers de parsing ─────────────────────────────────────────────────────────


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: str) -> Decimal | None:
    # Remove R$, %, espaços
    value = value.strip().lstrip("R$").strip().replace(" ", "")
    if not value or value in ("-", "—", "n/a", ""):
        return None
    if "," in value and "." in value:
        # Detecta formato pelo último separador
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _find_col(headers: list[str], candidates: set[str]) -> str | None:
    """Retorna o nome original do header que coincide com um dos candidatos (normalizado)."""
    for h in headers:
        if _norm(h) in candidates:
            return h
    return None


# ── Classe pública ─────────────────────────────────────────────────────────────


class XPParser:
    """Converte extratos XP Investimentos (CSV ou XLSX) para ImportTransaction."""

    def parse(
        self,
        content: bytes,
        encoding: str = "utf-8",
    ) -> tuple[list[ImportTransaction], list[str]]:
        """Detecta formato e delega para o parser adequado.

        Retorno: (transações, erros_de_parse).
        Erros estruturais: lista vazia + mensagem de erro.
        Erros de linha: adicionados à lista de erros; processamento continua.
        """
        # Magic bytes: XLSX é ZIP (começa com PK)
        if content[:2] == b"PK":
            return self._parse_xlsx(content)
        return self._parse_csv(content, encoding)

    def _parse_csv(
        self, content: bytes, encoding: str
    ) -> tuple[list[ImportTransaction], list[str]]:
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            return [], [f"Falha ao decodificar arquivo com encoding '{encoding}'"]

        if not text.strip():
            return [], ["Arquivo vazio"]

        first_line = text.split("\n", 1)[0]
        sep = ";" if first_line.count(";") >= first_line.count(",") else ","

        reader = csv.DictReader(io.StringIO(text), delimiter=sep)
        if not reader.fieldnames:
            return [], ["Cabeçalho não encontrado"]

        headers = list(reader.fieldnames)
        rows = list(reader)
        return self._convert_rows(rows, headers, start_row=2)

    def _parse_xlsx(
        self, content: bytes
    ) -> tuple[list[ImportTransaction], list[str]]:
        try:
            import openpyxl
        except ImportError:
            return [], ["Pacote 'openpyxl' não instalado. Execute: uv add openpyxl"]

        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
        except Exception as exc:
            return [], [f"Erro ao abrir arquivo XLSX: {exc}"]

        rows_raw = list(ws.iter_rows(values_only=True))
        if not rows_raw:
            return [], ["Arquivo XLSX vazio"]

        headers = [str(h).strip() if h is not None else "" for h in rows_raw[0]]
        dicts = [
            {headers[i]: (str(cell).strip() if cell is not None else "") for i, cell in enumerate(row)}
            for row in rows_raw[1:]
        ]
        return self._convert_rows(dicts, headers, start_row=2)

    def _convert_rows(
        self,
        rows: list[dict],
        headers: list[str],
        start_row: int,
    ) -> tuple[list[ImportTransaction], list[str]]:
        col_date  = _find_col(headers, _COL_DATE)
        col_type  = _find_col(headers, _COL_TYPE)
        col_tick  = _find_col(headers, _COL_TICK)
        col_qty   = _find_col(headers, _COL_QTY)
        col_price = _find_col(headers, _COL_PRICE)
        col_total = _find_col(headers, _COL_TOTAL)
        col_notes = _find_col(headers, _COL_NOTES)

        missing: list[str] = []
        if col_date  is None: missing.append("data")
        if col_type  is None: missing.append("movimentação/tipo")
        if col_tick  is None: missing.append("ativo/ticker")
        if col_total is None: missing.append("valor financeiro/total")
        if missing:
            return [], [f"Colunas obrigatórias não encontradas no extrato XP: {', '.join(missing)}"]

        transactions: list[ImportTransaction] = []
        errors: list[str] = []

        for idx, row in enumerate(rows):
            row_num = start_row + idx

            # Ignora linhas completamente vazias
            if all(not str(v).strip() for v in row.values()):
                continue

            row_errors: list[str] = []

            ticker_val = str(row.get(col_tick, "") or "").strip().upper()
            tipo_raw   = str(row.get(col_type, "") or "").strip()
            data_raw   = str(row.get(col_date, "") or "").strip()
            total_raw  = str(row.get(col_total, "") or "").strip()

            if not ticker_val:
                row_errors.append("ativo/ticker vazio")

            tx_type: TransactionType | None = None
            tipo_norm = _norm(tipo_raw)
            if not tipo_raw:
                row_errors.append("tipo de movimentação vazio")
            elif tipo_norm not in _XP_TYPE_MAP:
                errors.append(
                    f"Linha {row_num}: tipo desconhecido '{tipo_raw}' — linha ignorada (sem mapeamento)"
                )
                continue
            else:
                tx_type = _XP_TYPE_MAP[tipo_norm]

            tx_date: date | None = None
            if not data_raw:
                row_errors.append("data vazia")
            else:
                tx_date = _parse_date(data_raw)
                if tx_date is None:
                    row_errors.append(f"data inválida: '{data_raw}'")

            total_amount: Decimal | None = None
            if not total_raw:
                row_errors.append("valor vazio")
            else:
                total_amount = _parse_decimal(total_raw)
                if total_amount is None:
                    row_errors.append(f"valor inválido: '{total_raw}'")

            if row_errors:
                errors.extend(f"Linha {row_num}: {e}" for e in row_errors)
                continue

            qty_raw   = str(row.get(col_qty,   "") or "").strip() if col_qty   else ""
            price_raw = str(row.get(col_price, "") or "").strip() if col_price else ""
            notes_raw = str(row.get(col_notes, "") or "").strip() if col_notes else ""

            transactions.append(
                ImportTransaction(
                    ticker=ticker_val,
                    transaction_type=tx_type,  # type: ignore[arg-type]
                    tx_date=tx_date,            # type: ignore[arg-type]
                    total_amount=total_amount,  # type: ignore[arg-type]
                    quantity=_parse_decimal(qty_raw)   if qty_raw   else None,
                    unit_price=_parse_decimal(price_raw) if price_raw else None,
                    notes=notes_raw or None,
                    row_number=row_num,
                )
            )

        return transactions, errors
