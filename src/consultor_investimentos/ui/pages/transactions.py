"""Transações — registro e histórico de movimentações por ativo."""
from datetime import date
from decimal import Decimal, InvalidOperation

import streamlit as st

from consultor_investimentos.config import (
    ALLOWED_TRANSACTION_TYPES,
    AssetTrackingType,
    TransactionType,
)
from consultor_investimentos.database.connection import get_db
from consultor_investimentos.services.portfolio_service import PortfolioService
from consultor_investimentos.services.snapshot_service import SnapshotService
from consultor_investimentos.services.transaction_service import TransactionService
from consultor_investimentos.ui.components.metrics import fmt_brl, fmt_date_br, fmt_price, fmt_qty
from consultor_investimentos.ui.state import (
    CONFIRM_DELETE_TX_ID,
    ERROR_MSG,
    SUCCESS_MSG,
    TX_SELECTED_ASSET_ID,
)

_SNAPSHOT_TYPES = {TransactionType.BUY, TransactionType.SELL, TransactionType.CONTRIBUTION}

_TX_ICONS: dict[str, str] = {
    TransactionType.INITIAL_BALANCE.value: "🏁",
    TransactionType.BUY.value: "🟢",
    TransactionType.SELL.value: "🔴",
    TransactionType.CONTRIBUTION.value: "📥",
    TransactionType.WITHDRAWAL.value: "📤",
    TransactionType.DIVIDEND.value: "💰",
    TransactionType.INTEREST.value: "💰",
    TransactionType.OTHER.value: "📋",
}

# ── Flash messages ─────────────────────────────────────────────────────────────
if msg := st.session_state.pop(SUCCESS_MSG, None):
    st.success(msg)
if msg := st.session_state.pop(ERROR_MSG, None):
    st.error(msg)

st.title("💸 Transações")

# ── Carrega ativos disponíveis ─────────────────────────────────────────────────
with get_db() as session:
    asset_options = PortfolioService(session).get_active_asset_options()

if not asset_options:
    st.info(
        "Nenhum ativo cadastrado. Cadastre ativos e registre o saldo inicial em **Configurações**."
    )
    st.stop()

# ── Seleção de ativo ───────────────────────────────────────────────────────────
asset_ids = [a["id"] for a in asset_options]
asset_map = {a["id"]: a for a in asset_options}
asset_display = {a["id"]: f"{a['ticker']} — {a['name']}" for a in asset_options}

saved_id = st.session_state.get(TX_SELECTED_ASSET_ID)
default_idx = asset_ids.index(saved_id) if saved_id in asset_ids else 0

selected_id: int = st.selectbox(
    "Ativo",
    options=asset_ids,
    format_func=lambda aid: asset_display[aid],
    index=default_idx,
)
st.session_state[TX_SELECTED_ASSET_ID] = selected_id

selected_asset = asset_map[selected_id]
tracking_type = AssetTrackingType(selected_asset["tracking_type"])
is_qp = tracking_type == AssetTrackingType.QUANTITY_PRICE

badge = "📊 Quantidade × Preço" if is_qp else "📊 Valor Total"
st.caption(badge)

# ── Carrega posição atual e histórico ──────────────────────────────────────────
with get_db() as session:
    current_pos = PortfolioService(session).get_position(selected_id)
    history = TransactionService(session).list_by_asset(selected_id)

st.markdown("---")

# ── Formulário de registro ─────────────────────────────────────────────────────
st.subheader("Registrar movimentação")

available_tx_types = [
    t for t in ALLOWED_TRANSACTION_TYPES[tracking_type]
    if t != TransactionType.INITIAL_BALANCE
]

tx_type_labels = [t.value for t in available_tx_types]
tx_type_selected: str = st.radio(
    "Tipo",
    options=tx_type_labels,
    horizontal=True,
    key=f"tx_type_{selected_id}",
)
transaction_type = TransactionType(tx_type_selected)

is_buy_sell = transaction_type in (TransactionType.BUY, TransactionType.SELL)
is_value_update = transaction_type in (TransactionType.CONTRIBUTION, TransactionType.WITHDRAWAL)

# Hint de saldo disponível para venda
if transaction_type == TransactionType.SELL:
    if current_pos is not None and current_pos.quantity is not None:
        st.info(f"Saldo disponível: **{fmt_qty(current_pos.quantity)} cotas**")
    else:
        st.warning("Ativo sem cotação registrada — verifique a quantidade manualmente.")

tx_date: date = st.date_input("Data", value=date.today(), key=f"tx_date_{selected_id}")

if tx_date > date.today():
    st.warning("⚠️ Data futura — confirma que o lançamento é para uma data futura?")

# ── Campos dinâmicos ───────────────────────────────────────────────────────────
qty_val: Decimal = Decimal("0")
price_val: Decimal = Decimal("0")
total_val: Decimal = Decimal("0")
new_pos_val: Decimal | None = None

if is_buy_sell:
    col_qty, col_price = st.columns(2)
    with col_qty:
        qty_input = st.number_input(
            "Quantidade",
            min_value=0.0,
            step=1.0,
            format="%.6f",
            key=f"tx_qty_{selected_id}_{tx_type_selected}",
        )
        qty_val = Decimal(str(qty_input))
    with col_price:
        price_input = st.number_input(
            "Preço unitário (R$)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key=f"tx_price_{selected_id}_{tx_type_selected}",
        )
        price_val = Decimal(str(price_input))

    if qty_val > 0 and price_val > 0:
        total_val = (qty_val * price_val).quantize(Decimal("0.01"))
        st.metric("Total calculado", fmt_brl(total_val))
    else:
        st.caption("Preencha quantidade e preço para ver o total.")
        total_val = Decimal("0")

    fees_input = st.number_input(
        "Taxas / Corretagem (R$)",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key=f"tx_fees_{selected_id}_{tx_type_selected}",
    )
    fees_val = Decimal(str(fees_input))

else:
    total_input = st.number_input(
        "Valor (R$)",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key=f"tx_total_{selected_id}_{tx_type_selected}",
        help="Para Resgate: valor retirado. Para Aporte: valor aplicado.",
    )
    total_val = Decimal(str(total_input))
    fees_val = Decimal("0")

    if is_value_update:
        new_pos_input = st.number_input(
            "Novo valor da posição após operação (R$) — opcional",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key=f"tx_newpos_{selected_id}_{tx_type_selected}",
            help=(
                "Se informado, registra automaticamente o preço da posição para essa data. "
                "Deixe em 0 para não atualizar."
            ),
        )
        new_pos_val = Decimal(str(new_pos_input)) if new_pos_input > 0 else None

notes_input: str | None = st.text_input(
    "Observações (opcional)",
    key=f"tx_notes_{selected_id}_{tx_type_selected}",
)
notes_val = notes_input.strip() or None

if st.button("✅ Registrar", type="primary", key=f"tx_submit_{selected_id}"):
    error: str | None = None

    if is_buy_sell:
        if qty_val <= 0:
            error = "Quantidade deve ser maior que zero."
        elif price_val <= 0:
            error = "Preço unitário deve ser maior que zero."
        else:
            final_total = total_val + fees_val
    else:
        if total_val <= 0:
            error = "Valor deve ser maior que zero."
        else:
            final_total = total_val

    if error:
        st.error(error)
    else:
        try:
            with get_db() as session:
                tx_svc = TransactionService(session)
                tx_svc.register(
                    asset_id=selected_id,
                    transaction_type=transaction_type,
                    tx_date=tx_date,
                    total_amount=final_total,
                    quantity=qty_val if is_buy_sell else None,
                    unit_price=price_val if is_buy_sell else None,
                    fees=fees_val if is_buy_sell else Decimal("0"),
                    notes=notes_val,
                    new_position_value=new_pos_val,
                )
                if transaction_type in _SNAPSHOT_TYPES:
                    SnapshotService(session).ensure_snapshot_for_today()

            ticker = selected_asset["ticker"]
            if is_buy_sell:
                detail = f"{fmt_qty(qty_val)} cotas a {fmt_price(price_val)} = {fmt_brl(total_val)}"
            else:
                detail = fmt_brl(total_val)
            st.session_state[SUCCESS_MSG] = (
                f"{ticker}: {transaction_type.value} registrada — {detail}."
            )
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Erro ao registrar transação: {exc}")

st.markdown("---")

# ── Histórico do ativo selecionado ─────────────────────────────────────────────
ticker_label = selected_asset["ticker"]
st.subheader(f"Histórico: {ticker_label}")

if not history:
    st.info("Nenhuma transação registrada para este ativo.")
    st.stop()

# Cabeçalho
hcols = st.columns([1.8, 2.2, 1.4, 1.8, 1.8, 1.4, 0.8])
labels = ["Data", "Tipo", "Qtd.", "P. Unit.", "Total", "Taxas", ""]
for col, label in zip(hcols, labels):
    col.markdown(f"**{label}**")

st.divider()

confirm_id = st.session_state.get(CONFIRM_DELETE_TX_ID)

for tx in history:
    icon = _TX_ICONS.get(tx.transaction_type, "📋")
    is_confirming = confirm_id == tx.id

    if is_confirming:
        st.warning(
            f"⚠️ Excluir **{icon} {tx.transaction_type}** de {fmt_date_br(tx.date)} "
            f"— {fmt_brl(tx.total_amount)}? Esta ação não pode ser desfeita."
        )
        c1, c2 = st.columns([1, 5])
        with c1:
            if st.button("✅ Confirmar", key=f"confirm_del_{tx.id}", type="primary"):
                try:
                    with get_db() as session:
                        TransactionService(session).delete(tx.id)
                    st.session_state.pop(CONFIRM_DELETE_TX_ID, None)
                    st.session_state[SUCCESS_MSG] = (
                        f"Transação de {fmt_date_br(tx.date)} excluída."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Erro ao excluir: {exc}")
        with c2:
            if st.button("❌ Cancelar", key=f"cancel_del_{tx.id}"):
                st.session_state.pop(CONFIRM_DELETE_TX_ID, None)
                st.rerun()
        continue

    row = st.columns([1.8, 2.2, 1.4, 1.8, 1.8, 1.4, 0.8])
    row[0].write(fmt_date_br(tx.date))
    row[1].write(f"{icon} {tx.transaction_type}")
    row[2].write(fmt_qty(tx.quantity))
    row[3].write(fmt_price(tx.unit_price))
    row[4].write(fmt_brl(tx.total_amount))
    fees_str = fmt_brl(tx.fees) if tx.fees and tx.fees > 0 else "—"
    row[5].write(fees_str)

    if not tx.can_delete:
        row[6].write("🔒")
    else:
        if row[6].button("🗑️", key=f"del_{tx.id}", help="Excluir transação"):
            st.session_state[CONFIRM_DELETE_TX_ID] = tx.id
            st.rerun()
