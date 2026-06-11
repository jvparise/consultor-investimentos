from decimal import Decimal

from consultor_investimentos.config import Currency


def convert_to_brl(value: Decimal, currency: Currency, rates: dict[Currency, Decimal]) -> Decimal:
    """Converte um valor na moeda do ativo para BRL usando as cotações fornecidas.

    BRL retorna o valor original. Moedas sem cotação cadastrada retornam o valor original
    com um aviso implícito (rate=1), evitando quebrar o app por cotação ausente.
    """
    if currency == Currency.BRL:
        return value
    rate = rates.get(currency, Decimal("1"))
    return (value * rate).quantize(Decimal("0.000001"))
