"""Configurações — Perfil, Financeiro, Alocação Alvo e Ativos Cadastrados."""
from datetime import date
from decimal import Decimal

import streamlit as st

from consultor_investimentos.config import AssetClass, AssetTrackingType, TransactionType
from consultor_investimentos.database.connection import get_db
from consultor_investimentos.services.portfolio_service import PortfolioService
from consultor_investimentos.services.settings_service import SettingsService
from consultor_investimentos.services.transaction_service import TransactionService
from consultor_investimentos.ui.components.metrics import fmt_brl, fmt_brl_private
from consultor_investimentos.utils.brl import fmt_brl_input, parse_brl
from consultor_investimentos.ui.state import (
    CONFIRM_DEACTIVATE_ASSET_ID,
    EDIT_ASSET_ID,
    SETTINGS_ASSET_STEP,
    SUCCESS_MSG,
)

_TRACKING_LABELS = {
    "QUANTITY_PRICE": "Quantidade × Preço",
    "VALUE_ONLY": "Valor Total",
}

# ── Flash messages ────────────────────────────────────────────────────────────
if msg := st.session_state.pop(SUCCESS_MSG, None):
    st.success(msg)

# ── Carrega dados em uma única sessão ─────────────────────────────────────────
with get_db() as session:
    _svc = SettingsService(session)
    settings = _svc.get_settings()
    assets = _svc.get_active_assets()
    unpriced = set(PortfolioService(session).get_portfolio_summary().unpriced_tickers)

st.title("⚙️ Configurações")
st.markdown("---")

# ── Seção: Perfil ─────────────────────────────────────────────────────────────
st.subheader("👤 Perfil")

with st.form("form_profile"):
    user_name_input = st.text_input("Nome de exibição", value=settings.user_name)
    if st.form_submit_button("💾 Salvar Perfil"):
        clean = user_name_input.strip()
        if not clean:
            st.error("Nome não pode ser vazio.")
        else:
            try:
                with get_db() as session:
                    SettingsService(session).update_settings({"user_name": clean})
                st.session_state[SUCCESS_MSG] = "Perfil atualizado."
                st.rerun()
            except Exception as e:
                st.error(str(e))

st.markdown("---")

# ── Seção: Configurações Financeiras ──────────────────────────────────────────
st.subheader("💰 Configurações Financeiras")

with st.form("form_financial"):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        contribution_input = st.text_input(
            "Aporte Mensal (R$)",
            value=fmt_brl_input(settings.monthly_contribution),
            placeholder="ex: 3.000,00",
            help="Valor que você aporta todo mês na carteira.",
        )
    with col_f2:
        expenses_input = st.text_input(
            "Gastos Mensais (R$)",
            value=fmt_brl_input(settings.monthly_expenses),
            placeholder="ex: 5.000,00",
            help="Seus gastos médios mensais — usado para calcular a meta FIRE (gastos × 300).",
        )
    if st.form_submit_button("💾 Salvar Financeiro"):
        try:
            contribution = parse_brl(contribution_input) if contribution_input.strip() else Decimal("0")
            expenses = parse_brl(expenses_input) if expenses_input.strip() else Decimal("0")
            with get_db() as session:
                SettingsService(session).update_settings({
                    "monthly_contribution": contribution,
                    "monthly_expenses": expenses,
                })
            st.session_state[SUCCESS_MSG] = "Configurações financeiras atualizadas."
            st.rerun()
        except Exception as e:
            st.error(str(e))

if settings.monthly_expenses > 0:
    fire_number = settings.monthly_expenses * 300
    st.caption(f"🔥 Meta FIRE estimada: {fmt_brl_private(fire_number)} (R$ {fmt_brl_private(settings.monthly_expenses)}/mês × 300)")

st.markdown("---")

# ── Seção: Alocação Alvo ──────────────────────────────────────────────────────
st.subheader("📊 Alocação Alvo")
st.caption("Defina o percentual alvo de cada classe. O total deve ser 0% (sem alvo) ou 100%.")

col_a1, col_a2, col_a3 = st.columns(3)
col_a4, col_a5, col_a6 = st.columns(3)
col_a7, col_a8, _ = st.columns(3)

with col_a1:
    eq_pct = st.number_input("Ações / BDRs (%)", 0.0, 100.0, float(settings.target_equity_pct), 5.0, "%.1f", key="alloc_eq")
with col_a2:
    fi_pct = st.number_input("Renda Fixa (%)", 0.0, 100.0, float(settings.target_fixed_pct), 5.0, "%.1f", key="alloc_fi")
with col_a3:
    etf_pct = st.number_input("ETF (%)", 0.0, 100.0, float(settings.target_etf_pct), 5.0, "%.1f", key="alloc_etf")
with col_a4:
    fii_brick_pct = st.number_input("FII Tijolo (%)", 0.0, 100.0, float(settings.target_fii_brick_pct), 5.0, "%.1f", key="alloc_fii_brick")
with col_a5:
    fii_paper_pct = st.number_input("FII Papel (%)", 0.0, 100.0, float(settings.target_fii_paper_pct), 5.0, "%.1f", key="alloc_fii_paper")
with col_a6:
    intl_pct = st.number_input("Internacional (%)", 0.0, 100.0, float(settings.target_intl_pct), 5.0, "%.1f", key="alloc_intl")
with col_a7:
    crypto_pct = st.number_input("Cripto (%)", 0.0, 100.0, float(settings.target_crypto_pct), 5.0, "%.1f", key="alloc_crypto")
with col_a8:
    other_pct = st.number_input("Outros (%)", 0.0, 100.0, float(settings.target_other_pct), 5.0, "%.1f", key="alloc_other")

alloc_total = eq_pct + fi_pct + etf_pct + fii_brick_pct + fii_paper_pct + intl_pct + crypto_pct + other_pct
if alloc_total == 0.0:
    st.info(f"Total: **0%** — nenhuma alocação alvo configurada.")
elif abs(alloc_total - 100.0) < 0.01:
    st.success(f"Total: **{alloc_total:.1f}%** ✅")
else:
    diff = 100.0 - alloc_total
    label = f"Faltam {diff:.1f}%" if diff > 0 else f"Excesso de {abs(diff):.1f}%"
    st.warning(f"Total: **{alloc_total:.1f}%** ⚠️ — {label}")

if st.button("💾 Salvar Alocação", key="btn_alloc"):
    try:
        with get_db() as session:
            SettingsService(session).update_settings({
                "target_equity_pct": Decimal(str(eq_pct)),
                "target_fixed_pct": Decimal(str(fi_pct)),
                "target_etf_pct": Decimal(str(etf_pct)),
                "target_fii_brick_pct": Decimal(str(fii_brick_pct)),
                "target_fii_paper_pct": Decimal(str(fii_paper_pct)),
                "target_intl_pct": Decimal(str(intl_pct)),
                "target_crypto_pct": Decimal(str(crypto_pct)),
                "target_other_pct": Decimal(str(other_pct)),
            })
        st.session_state[SUCCESS_MSG] = "Alocação alvo salva."
        st.rerun()
    except ValueError as e:
        st.error(str(e))

st.markdown("---")

# ── Seção: Ativos Cadastrados ──────────────────────────────────────────────────
st.subheader("📋 Ativos Cadastrados")

hdr_col, btn_col = st.columns([3, 1])
with hdr_col:
    st.caption(f"{len(assets)} ativo(s) cadastrado(s)")
with btn_col:
    if st.session_state.get(SETTINGS_ASSET_STEP) != "open":
        if st.button("➕ Novo Ativo", type="primary", use_container_width=True):
            st.session_state[SETTINGS_ASSET_STEP] = "open"
            st.session_state[EDIT_ASSET_ID] = None
            st.session_state[CONFIRM_DEACTIVATE_ASSET_ID] = None
            st.rerun()

# ── Formulário de criação ─────────────────────────────────────────────────────
if st.session_state.get(SETTINGS_ASSET_STEP) == "open":
    with st.container(border=True):
        st.markdown("**➕ Novo Ativo**")

        na_ticker = st.text_input("Ticker *", placeholder="ex: VALE3", key="na_ticker")
        na_name = st.text_input("Nome *", placeholder="ex: Vale S.A.", key="na_name")

        na_class_val = st.selectbox(
            "Classe *",
            options=[cls.value for cls in AssetClass],
            key="na_class",
        )
        na_class = AssetClass(na_class_val)
        is_cash = na_class == AssetClass.CASH

        if is_cash:
            st.info("ℹ️ Caixa/Liquidez usa automaticamente **Valor Total**.")
            na_tracking = AssetTrackingType.VALUE_ONLY
        else:
            na_tracking_label = st.radio(
                "Tipo de Rastreamento *",
                options=["Quantidade × Preço unitário", "Valor Total da posição"],
                key="na_tracking",
                horizontal=True,
            )
            na_tracking = (
                AssetTrackingType.QUANTITY_PRICE
                if na_tracking_label == "Quantidade × Preço unitário"
                else AssetTrackingType.VALUE_ONLY
            )

        na_notes = st.text_area("Observações", max_chars=200, key="na_notes", placeholder="(opcional)")

        st.markdown("---")
        with_balance = st.checkbox("📈 Registrar saldo inicial agora", key="na_with_balance")

        na_bal_date: date | None = None
        na_bal_qty: float = 0.0
        na_bal_unit: float = 0.0
        na_bal_total: float = 0.0

        if with_balance:
            na_bal_date = st.date_input("Data do saldo", value=date.today(), key="na_bal_date")
            if na_tracking == AssetTrackingType.QUANTITY_PRICE:
                c1, c2 = st.columns(2)
                with c1:
                    na_bal_qty = st.number_input("Quantidade", min_value=0.0, step=1.0, format="%.6f", key="na_qty")
                with c2:
                    na_bal_unit = st.text_input("Preço unitário (R$)", placeholder="ex: 62,50", key="na_unit")
                try:
                    unit_val = parse_brl(na_bal_unit) if na_bal_unit.strip() else Decimal("0")
                except ValueError:
                    unit_val = Decimal("0")
                if na_bal_qty > 0 and unit_val > 0:
                    total_calc = Decimal(str(na_bal_qty)) * unit_val
                    st.caption(f"Total calculado: **{fmt_brl_private(total_calc)}**")
            else:
                na_bal_total = st.text_input(
                    "Valor total da posição (R$)", placeholder="ex: 10.000,00", key="na_total"
                )

        c_save, c_cancel = st.columns(2)
        with c_save:
            create_clicked = st.button("✅ Criar Ativo", type="primary", use_container_width=True, key="na_submit")
        with c_cancel:
            cancel_clicked = st.button("✖️ Cancelar", use_container_width=True, key="na_cancel")

        if cancel_clicked:
            st.session_state[SETTINGS_ASSET_STEP] = None
            st.rerun()

        if create_clicked:
            ticker_clean = na_ticker.upper().strip()
            name_clean = na_name.strip()
            errors: list[str] = []

            # Parse dos campos monetários
            parsed_unit: Decimal = Decimal("0")
            parsed_total: Decimal = Decimal("0")
            if with_balance and na_bal_date:
                if na_tracking == AssetTrackingType.QUANTITY_PRICE:
                    try:
                        parsed_unit = parse_brl(na_bal_unit) if na_bal_unit.strip() else Decimal("0")
                    except ValueError:
                        errors.append(f"Preço unitário inválido: '{na_bal_unit}'.")
                else:
                    try:
                        parsed_total = parse_brl(na_bal_total) if na_bal_total.strip() else Decimal("0")
                    except ValueError:
                        errors.append(f"Valor total inválido: '{na_bal_total}'.")

            if not ticker_clean:
                errors.append("Ticker obrigatório.")
            if not name_clean:
                errors.append("Nome obrigatório.")
            if with_balance and na_bal_date:
                if na_tracking == AssetTrackingType.QUANTITY_PRICE and (na_bal_qty <= 0 or parsed_unit <= 0):
                    errors.append("Quantidade e preço unitário devem ser maiores que zero.")
                if na_tracking == AssetTrackingType.VALUE_ONLY and parsed_total <= 0:
                    errors.append("Valor total do saldo inicial deve ser maior que zero.")

            if errors:
                for err in errors:
                    st.error(err)
            else:
                try:
                    with get_db() as session:
                        asset_id = SettingsService(session).create_asset(
                            ticker=ticker_clean,
                            name=name_clean,
                            asset_class=na_class,
                            tracking_type=na_tracking,
                            notes=na_notes.strip() or None,
                        )
                        if with_balance and na_bal_date:
                            if na_tracking == AssetTrackingType.QUANTITY_PRICE:
                                qty_d = Decimal(str(na_bal_qty))
                                TransactionService(session).register(
                                    asset_id=asset_id,
                                    transaction_type=TransactionType.INITIAL_BALANCE,
                                    tx_date=na_bal_date,
                                    total_amount=qty_d * parsed_unit,
                                    quantity=qty_d,
                                    unit_price=parsed_unit,
                                )
                            else:
                                TransactionService(session).register(
                                    asset_id=asset_id,
                                    transaction_type=TransactionType.INITIAL_BALANCE,
                                    tx_date=na_bal_date,
                                    total_amount=parsed_total,
                                )
                    st.session_state[SUCCESS_MSG] = f"Ativo {ticker_clean} criado com sucesso!"
                    st.session_state[SETTINGS_ASSET_STEP] = None
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

# ── Lista de ativos ────────────────────────────────────────────────────────────
if not assets:
    if st.session_state.get(SETTINGS_ASSET_STEP) != "open":
        st.info("Nenhum ativo cadastrado. Clique em **➕ Novo Ativo** para começar.")
else:
    for asset in assets:
        asset_id = asset["id"]
        ticker = asset["ticker"]
        is_unpriced = ticker in unpriced
        edit_open = st.session_state.get(EDIT_ASSET_ID) == asset_id
        confirm_deact = st.session_state.get(CONFIRM_DEACTIVATE_ASSET_ID) == asset_id

        with st.container(border=True):
            # Linha de cabeçalho do ativo
            col_ticker, col_info, col_actions = st.columns([2, 4, 3])

            with col_ticker:
                badge = "⚠️" if is_unpriced else "✅"
                st.markdown(f"**{badge} {ticker}**")

            with col_info:
                tracking_label = _TRACKING_LABELS.get(asset["tracking_type"], asset["tracking_type"])
                st.caption(f"{asset['name']}")
                st.caption(f"{asset['asset_class']} · {tracking_label}")

            with col_actions:
                ac1, ac2 = st.columns(2)
                with ac1:
                    edit_label = "✖️ Fechar" if edit_open else "✏️ Editar"
                    if st.button(edit_label, key=f"edit_btn_{asset_id}", use_container_width=True):
                        if edit_open:
                            st.session_state[EDIT_ASSET_ID] = None
                        else:
                            st.session_state[EDIT_ASSET_ID] = asset_id
                            st.session_state[CONFIRM_DEACTIVATE_ASSET_ID] = None
                            st.session_state[SETTINGS_ASSET_STEP] = None
                        st.rerun()

                with ac2:
                    if not confirm_deact:
                        if st.button("🗑️", key=f"deact_btn_{asset_id}", help="Desativar ativo", use_container_width=True):
                            st.session_state[CONFIRM_DEACTIVATE_ASSET_ID] = asset_id
                            st.session_state[EDIT_ASSET_ID] = None
                            st.rerun()
                    else:
                        if st.button("✅ Confirmar", key=f"deact_ok_{asset_id}", type="primary", use_container_width=True):
                            try:
                                with get_db() as session:
                                    SettingsService(session).deactivate_asset(asset_id)
                                st.session_state[SUCCESS_MSG] = f"Ativo {ticker} desativado."
                                st.session_state[CONFIRM_DEACTIVATE_ASSET_ID] = None
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))

            # Confirmação de desativação
            if confirm_deact:
                st.warning(
                    f"⚠️ Desativar **{ticker}**? O ativo será removido da carteira e das projeções. "
                    "O histórico de transações é preservado."
                )
                if st.button("Cancelar", key=f"deact_cancel_{asset_id}"):
                    st.session_state[CONFIRM_DEACTIVATE_ASSET_ID] = None
                    st.rerun()

            # Formulário de edição inline
            if edit_open:
                with st.form(f"form_edit_{asset_id}"):
                    new_name = st.text_input("Nome", value=asset["name"])
                    new_notes = st.text_area("Observações", value=asset["notes"], max_chars=200)
                    if is_unpriced:
                        st.warning("Ativo sem preço registrado. Atualize o preço em **Carteira**.")
                    if st.form_submit_button("💾 Salvar", type="primary"):
                        if not new_name.strip():
                            st.error("Nome não pode ser vazio.")
                        else:
                            try:
                                with get_db() as session:
                                    SettingsService(session).update_asset(
                                        asset_id=asset_id,
                                        name=new_name.strip(),
                                        notes=new_notes.strip(),
                                    )
                                st.session_state[SUCCESS_MSG] = f"{ticker} atualizado."
                                st.session_state[EDIT_ASSET_ID] = None
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
