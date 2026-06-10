import re
from decimal import Decimal, InvalidOperation


def parse_brl(text: str) -> Decimal:
    """Converte entrada monetária BR para Decimal.

    Aceita:
      "1.000,00"  → Decimal("1000.00")
      "1000,00"   → Decimal("1000.00")
      "1000.00"   → Decimal("1000.00")
      "1000"      → Decimal("1000")
      "0,50"      → Decimal("0.50")
      "R$ 1.234,56" → Decimal("1234.56")

    Lança ValueError para entradas inválidas.
    """
    if not isinstance(text, str):
        raise ValueError(f"Esperado string, recebido {type(text).__name__}.")

    cleaned = text.strip()
    cleaned = re.sub(r"^R\$\s*", "", cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        raise ValueError("Valor não pode estar em branco.")

    if "," in cleaned:
        # Formato BR: "." é separador de milhar, "," é decimal
        cleaned = cleaned.replace(".", "").replace(",", ".")
    # Se só tem ".", trata como decimal americano (ex: "1000.00")

    # Valida que só restam dígitos, ponto e sinal opcional
    if not re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
        raise ValueError(f"Valor inválido: '{text}'.")

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Valor inválido: '{text}'.")


def fmt_brl_input(value: Decimal | None) -> str:
    """Formata um Decimal para exibição em campos text_input monetários."""
    if value is None or value == Decimal("0"):
        return ""
    formatted = f"{value:,.2f}"
    # Converte separadores: "1,000.00" → "1.000,00"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted
