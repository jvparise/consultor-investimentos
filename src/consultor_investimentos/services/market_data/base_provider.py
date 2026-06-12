from decimal import Decimal
from typing import Protocol, runtime_checkable


@runtime_checkable
class BaseProvider(Protocol):
    def get_price(self, ticker: str) -> Decimal | None:
        ...
