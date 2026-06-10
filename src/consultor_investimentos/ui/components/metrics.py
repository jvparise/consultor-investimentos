"""Formatadores de valores financeiros para exibição na UI."""
from decimal import Decimal


def fmt_brl(value: Decimal | float | int, show_sign: bool = False) -> str:
    """Formata valor em reais: R$ 1.234,56 ou -R$ 1.234,56."""
    v = float(value)
    neg = v < 0
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sign = "+" if show_sign and not neg and v != 0 else ("-" if neg else "")
    return f"{sign}R$ {s}"


def fmt_pct(value: Decimal | float, decimals: int = 2, show_sign: bool = True) -> str:
    """Formata percentual: +12,34% ou -3,50%."""
    v = float(value)
    sign = "+" if show_sign and v >= 0 else ""
    fmt = f"{v:.{decimals}f}".replace(".", ",")
    return f"{sign}{fmt}%"


def fmt_months(n: int | None, prefix: str = "") -> str:
    """Converte número de meses para texto legível."""
    if n is None:
        return "Inatingível"
    if n == 0:
        return "Já atingido ✓"
    label = "mês" if n == 1 else "meses"
    return f"{prefix}{n} {label}"


def fmt_date_br(d: object) -> str:
    """Formata data no padrão brasileiro: 09/06/2026."""
    if d is None:
        return "—"
    return d.strftime("%d/%m/%Y")


def fmt_qty(value: Decimal | None) -> str:
    """Formata quantidade: 100 → '100', 100.5 → '100,5'. None → '—'."""
    if value is None:
        return "—"
    v = float(value)
    if v == int(v):
        return f"{int(v):,}".replace(",", ".")
    s = f"{v:,.6f}".rstrip("0").replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def fmt_price(value: Decimal | None) -> str:
    """None → '—', caso contrário fmt_brl."""
    if value is None:
        return "—"
    return fmt_brl(value)
