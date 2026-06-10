"""Testes do modo privacidade — fmt_brl_private."""
from decimal import Decimal
from unittest.mock import patch

import pytest

from consultor_investimentos.ui.components.metrics import fmt_brl_private
from consultor_investimentos.ui.state import PRIVACY_MODE


def _with_privacy(enabled: bool):
    """Context manager que simula st.session_state com privacy_mode."""
    return patch(
        "consultor_investimentos.ui.components.metrics.st.session_state",
        {PRIVACY_MODE: enabled},
    )


def test_modo_desligado_retorna_valor(monkeypatch) -> None:
    with _with_privacy(False):
        result = fmt_brl_private(Decimal("1000.00"))
    assert result == "R$ 1.000,00"


def test_modo_ligado_oculta_valor(monkeypatch) -> None:
    with _with_privacy(True):
        result = fmt_brl_private(Decimal("1000.00"))
    assert result == "R$ ••••••"


def test_modo_ligado_oculta_valor_alto() -> None:
    with _with_privacy(True):
        result = fmt_brl_private(Decimal("150000.00"))
    assert result == "R$ ••••••"


def test_modo_ligado_oculta_zero() -> None:
    with _with_privacy(True):
        result = fmt_brl_private(Decimal("0"))
    assert result == "R$ ••••••"


def test_modo_ligado_oculta_valor_negativo() -> None:
    with _with_privacy(True):
        result = fmt_brl_private(Decimal("-500.00"))
    assert result == "R$ ••••••"


def test_modo_desligado_com_show_sign() -> None:
    with _with_privacy(False):
        result = fmt_brl_private(Decimal("500.00"), show_sign=True)
    assert result == "+R$ 500,00"


def test_modo_ligado_com_show_sign_oculta() -> None:
    with _with_privacy(True):
        result = fmt_brl_private(Decimal("500.00"), show_sign=True)
    assert result == "R$ ••••••"


def test_privacy_mode_ausente_exibe_valor() -> None:
    """Sem chave no session_state, modo privacidade deve estar desligado."""
    with patch(
        "consultor_investimentos.ui.components.metrics.st.session_state",
        {},
    ):
        result = fmt_brl_private(Decimal("1234.56"))
    assert result == "R$ 1.234,56"
