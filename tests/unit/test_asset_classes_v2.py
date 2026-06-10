"""Testes das novas classes ETF, FII Tijolo e FII Papel (Feature 7 — Stage 2)."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from consultor_investimentos.config import AssetClass, AssetTrackingType, IncomeType, TransactionType
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.holding_repository import HoldingRepository
from consultor_investimentos.repositories.settings_repository import SettingsRepository
from consultor_investimentos.services.portfolio_service import PortfolioService
from consultor_investimentos.services.settings_service import SettingsService


# ── helpers ──────────────────────────────────────────────────────────────────

def _add_asset(
    session: Session,
    ticker: str,
    asset_class: AssetClass,
    cost: Decimal,
    price: Decimal,
) -> int:
    """Cria ativo VALUE_ONLY com custo e preço atual — suficiente para testar alocação."""
    asset = AssetRepository(session).create(
        ticker=ticker,
        name=f"Ativo {ticker}",
        asset_class=asset_class,
        income_type=IncomeType.VARIABLE,
        tracking_type=AssetTrackingType.VALUE_ONLY,
    )
    ContributionRepository(session).create(
        asset_id=asset.id,
        transaction_type=TransactionType.INITIAL_BALANCE,
        date=date(2025, 1, 2),
        total_amount=cost,
    )
    HoldingRepository(session).upsert(
        asset_id=asset.id,
        price_date=date(2025, 6, 1),
        price=price,
    )
    return asset.id


def _settings_with_all_classes(session: Session) -> None:
    SettingsRepository(session).update({
        "target_equity_pct": Decimal("30"),
        "target_etf_pct": Decimal("10"),
        "target_fii_brick_pct": Decimal("15"),
        "target_fii_paper_pct": Decimal("5"),
        "target_fixed_pct": Decimal("20"),
        "target_intl_pct": Decimal("10"),
        "target_crypto_pct": Decimal("5"),
        "target_other_pct": Decimal("5"),
    })


# ── Alocação por classe ────────────────────────────────────────────────────────

def test_etf_aparece_separado_de_equity(session: Session) -> None:
    _add_asset(session, "VALE3", AssetClass.EQUITY, Decimal("10000"), Decimal("10000"))
    _add_asset(session, "BOVA11", AssetClass.ETF, Decimal("5000"), Decimal("5000"))

    summary = PortfolioService(session).get_portfolio_summary()
    classes = {a.asset_class for a in summary.allocation}

    assert AssetClass.EQUITY in classes
    assert AssetClass.ETF in classes
    equity_val = next(a.total_value for a in summary.allocation if a.asset_class == AssetClass.EQUITY)
    etf_val = next(a.total_value for a in summary.allocation if a.asset_class == AssetClass.ETF)
    assert equity_val == Decimal("10000.00")
    assert etf_val == Decimal("5000.00")


def test_fii_brick_e_fii_paper_aparecem_separados(session: Session) -> None:
    _add_asset(session, "HGLG11", AssetClass.FII_BRICK, Decimal("8000"), Decimal("8000"))
    _add_asset(session, "KNCR11", AssetClass.FII_PAPER, Decimal("4000"), Decimal("4000"))

    summary = PortfolioService(session).get_portfolio_summary()
    classes = {a.asset_class for a in summary.allocation}

    assert AssetClass.FII_BRICK in classes
    assert AssetClass.FII_PAPER in classes
    assert AssetClass.EQUITY not in classes

    brick_val = next(a.total_value for a in summary.allocation if a.asset_class == AssetClass.FII_BRICK)
    paper_val = next(a.total_value for a in summary.allocation if a.asset_class == AssetClass.FII_PAPER)
    assert brick_val == Decimal("8000.00")
    assert paper_val == Decimal("4000.00")


def test_etf_fii_brick_fii_paper_nao_aparecem_mesclados(session: Session) -> None:
    _add_asset(session, "BOVA11", AssetClass.ETF, Decimal("5000"), Decimal("5000"))
    _add_asset(session, "HGLG11", AssetClass.FII_BRICK, Decimal("5000"), Decimal("5000"))
    _add_asset(session, "KNCR11", AssetClass.FII_PAPER, Decimal("5000"), Decimal("5000"))

    summary = PortfolioService(session).get_portfolio_summary()
    assert len(summary.allocation) == 3
    assert sum(a.total_value for a in summary.allocation) == Decimal("15000.00")


def test_portfolio_pct_correto_para_etf(session: Session) -> None:
    _add_asset(session, "VALE3", AssetClass.EQUITY, Decimal("6000"), Decimal("6000"))
    _add_asset(session, "BOVA11", AssetClass.ETF, Decimal("4000"), Decimal("4000"))

    summary = PortfolioService(session).get_portfolio_summary()
    etf_alloc = next(a for a in summary.allocation if a.asset_class == AssetClass.ETF)

    assert etf_alloc.percentage == Decimal("40.00")


# ── Settings: get_target_pct ──────────────────────────────────────────────────

def test_get_target_pct_etf(session: Session) -> None:
    _settings_with_all_classes(session)
    svc = SettingsService(session)
    dto = svc.get_settings()

    assert svc.get_target_pct(dto, AssetClass.ETF) == 10.0


def test_get_target_pct_fii_brick(session: Session) -> None:
    _settings_with_all_classes(session)
    svc = SettingsService(session)
    dto = svc.get_settings()

    assert svc.get_target_pct(dto, AssetClass.FII_BRICK) == 15.0


def test_get_target_pct_fii_paper(session: Session) -> None:
    _settings_with_all_classes(session)
    svc = SettingsService(session)
    dto = svc.get_settings()

    assert svc.get_target_pct(dto, AssetClass.FII_PAPER) == 5.0


def test_get_target_pct_cash_retorna_zero(session: Session) -> None:
    svc = SettingsService(session)
    dto = svc.get_settings()
    assert svc.get_target_pct(dto, AssetClass.CASH) == 0.0


# ── Settings repository: campos novos ─────────────────────────────────────────

def test_settings_repo_aceita_etf_fii_brick_fii_paper(session: Session) -> None:
    repo = SettingsRepository(session)
    updated = repo.update({
        "target_equity_pct": Decimal("30"),
        "target_etf_pct": Decimal("10"),
        "target_fii_brick_pct": Decimal("15"),
        "target_fii_paper_pct": Decimal("5"),
        "target_fixed_pct": Decimal("20"),
        "target_intl_pct": Decimal("10"),
        "target_crypto_pct": Decimal("5"),
        "target_other_pct": Decimal("5"),
    })

    assert updated.target_etf_pct == Decimal("10")
    assert updated.target_fii_brick_pct == Decimal("15")
    assert updated.target_fii_paper_pct == Decimal("5")


def test_settings_repo_rejeita_soma_com_fii_old_field(session: Session) -> None:
    """Nenhuma referência a target_fii_pct deve existir — chave ignorada como desconhecida."""
    repo = SettingsRepository(session)
    repo.get_or_create()

    updated = repo.update({
        "target_equity_pct": Decimal("100"),
        "target_fii_pct": Decimal("0"),
    })
    assert updated.target_equity_pct == Decimal("100")


def test_settings_dto_contem_campos_novos(session: Session) -> None:
    _settings_with_all_classes(session)
    dto = SettingsService(session).get_settings()

    assert hasattr(dto, "target_etf_pct")
    assert hasattr(dto, "target_fii_brick_pct")
    assert hasattr(dto, "target_fii_paper_pct")
    assert not hasattr(dto, "target_fii_pct")


# ── Configuração de alocação completa ─────────────────────────────────────────

def test_alocacao_com_tres_categorias_fii_soma_100(session: Session) -> None:
    repo = SettingsRepository(session)
    updated = repo.update({
        "target_equity_pct": Decimal("40"),
        "target_etf_pct": Decimal("10"),
        "target_fii_brick_pct": Decimal("10"),
        "target_fii_paper_pct": Decimal("10"),
        "target_fixed_pct": Decimal("20"),
        "target_intl_pct": Decimal("5"),
        "target_crypto_pct": Decimal("0"),
        "target_other_pct": Decimal("5"),
    })

    total = sum([
        updated.target_equity_pct,
        updated.target_etf_pct,
        updated.target_fii_brick_pct,
        updated.target_fii_paper_pct,
        updated.target_fixed_pct,
        updated.target_intl_pct,
        updated.target_crypto_pct,
        updated.target_other_pct,
    ])
    assert total == Decimal("100")


def test_alocacao_invalida_com_novas_classes_levanta_value_error(session: Session) -> None:
    repo = SettingsRepository(session)
    repo.get_or_create()

    with pytest.raises(ValueError, match="Soma dos percentuais"):
        repo.update({
            "target_equity_pct": Decimal("40"),
            "target_etf_pct": Decimal("10"),
            "target_fii_brick_pct": Decimal("15"),
        })


# ── AssetClass enum ───────────────────────────────────────────────────────────

def test_asset_class_nao_tem_fii_legado() -> None:
    members = {c.name for c in AssetClass}
    assert "FII" not in members
    assert "ETF" in members
    assert "FII_BRICK" in members
    assert "FII_PAPER" in members


def test_asset_class_valores_string_corretos() -> None:
    assert AssetClass.ETF.value == "ETF"
    assert AssetClass.FII_BRICK.value == "FII Tijolo"
    assert AssetClass.FII_PAPER.value == "FII Papel"


def test_criar_ativo_etf_com_qp(session: Session) -> None:
    svc = SettingsService(session)
    asset_id = svc.create_asset(
        ticker="BOVA11",
        name="iShares Ibovespa ETF",
        asset_class=AssetClass.ETF,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    assert isinstance(asset_id, int)
    assert asset_id > 0


def test_criar_ativo_fii_brick_com_qp(session: Session) -> None:
    svc = SettingsService(session)
    asset_id = svc.create_asset(
        ticker="HGLG11",
        name="CSHG Logística FII",
        asset_class=AssetClass.FII_BRICK,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    assert isinstance(asset_id, int)


def test_criar_ativo_fii_paper_com_qp(session: Session) -> None:
    svc = SettingsService(session)
    asset_id = svc.create_asset(
        ticker="KNCR11",
        name="Kinea CRI",
        asset_class=AssetClass.FII_PAPER,
        tracking_type=AssetTrackingType.QUANTITY_PRICE,
    )
    assert isinstance(asset_id, int)
