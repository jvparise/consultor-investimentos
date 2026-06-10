"""Serviço de importação em lote via CSV."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from consultor_investimentos.config import ALLOWED_TRANSACTION_TYPES, AssetTrackingType, TransactionType
from consultor_investimentos.repositories.asset_repository import AssetRepository
from consultor_investimentos.repositories.contribution_repository import ContributionRepository
from consultor_investimentos.repositories.import_log_repository import ImportLogRepository
from consultor_investimentos.services.dto import ImportResult, ImportRowResult, ImportTransaction
from consultor_investimentos.services.transaction_service import TransactionService


class ImportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._asset_repo = AssetRepository(session)
        self._tx_service = TransactionService(session)
        self._contrib_repo = ContributionRepository(session)
        self._log_repo = ImportLogRepository(session)

    def validate(
        self,
        transactions: list[ImportTransaction],
        file_hash: str | None = None,
    ) -> ImportResult:
        """Valida lote sem escrever no banco.

        Se file_hash for fornecido, verifica idempotência antes de qualquer outra
        validação financeira. Retorna ImportResult com is_duplicate=True caso o arquivo
        já tenha sido importado com sucesso anteriormente.
        """
        if file_hash and self._log_repo.has_successful_import(file_hash):
            return ImportResult(
                total_rows=len(transactions),
                valid_rows=0,
                error_rows=1,
                rows=[
                    ImportRowResult(
                        row_number=0,
                        ticker="—",
                        transaction_type="—",
                        tx_date=None,
                        total_amount=None,
                        status="error",
                        message="Este arquivo já foi importado anteriormente.",
                    )
                ],
                is_duplicate=True,
            )

        sorted_txs = sorted(transactions, key=lambda t: t.tx_date)

        unique_tickers = {tx.ticker for tx in sorted_txs}
        asset_cache: dict[str, object] = {}
        running_qty: dict[str, Decimal] = {}

        for ticker in unique_tickers:
            asset = self._asset_repo.get_by_ticker(ticker)
            asset_cache[ticker] = asset
            if asset is not None and AssetTrackingType(asset.tracking_type) == AssetTrackingType.QUANTITY_PRICE:
                running_qty[ticker] = self._calc_current_qty(asset.id)
            else:
                running_qty[ticker] = Decimal("0")

        rows: list[ImportRowResult] = []

        for tx in sorted_txs:
            asset = asset_cache.get(tx.ticker)

            if asset is None:
                rows.append(ImportRowResult(
                    row_number=tx.row_number,
                    ticker=tx.ticker,
                    transaction_type=tx.transaction_type.value,
                    tx_date=tx.tx_date,
                    total_amount=tx.total_amount,
                    status="error",
                    message=f"Ativo '{tx.ticker}' não encontrado",
                ))
                continue

            allowed = ALLOWED_TRANSACTION_TYPES.get(AssetTrackingType(asset.tracking_type), [])
            if tx.transaction_type not in allowed:
                rows.append(ImportRowResult(
                    row_number=tx.row_number,
                    ticker=tx.ticker,
                    transaction_type=tx.transaction_type.value,
                    tx_date=tx.tx_date,
                    total_amount=tx.total_amount,
                    status="error",
                    message=(
                        f"Tipo '{tx.transaction_type.value}' não permitido para "
                        f"ativo com rastreamento {asset.tracking_type}"
                    ),
                ))
                continue

            if tx.transaction_type == TransactionType.SELL:
                current_qty = running_qty.get(tx.ticker, Decimal("0"))
                sell_qty = tx.quantity or Decimal("0")
                if sell_qty > current_qty:
                    rows.append(ImportRowResult(
                        row_number=tx.row_number,
                        ticker=tx.ticker,
                        transaction_type=tx.transaction_type.value,
                        tx_date=tx.tx_date,
                        total_amount=tx.total_amount,
                        status="error",
                        message=f"Venda de {sell_qty} excede saldo disponível ({current_qty})",
                    ))
                    continue
                running_qty[tx.ticker] = current_qty - sell_qty
            elif tx.transaction_type in (TransactionType.BUY, TransactionType.INITIAL_BALANCE):
                qty = tx.quantity or Decimal("0")
                running_qty[tx.ticker] = running_qty.get(tx.ticker, Decimal("0")) + qty

            rows.append(ImportRowResult(
                row_number=tx.row_number,
                ticker=tx.ticker,
                transaction_type=tx.transaction_type.value,
                tx_date=tx.tx_date,
                total_amount=tx.total_amount,
                status="ok",
            ))

        error_rows = sum(1 for r in rows if r.status == "error")
        return ImportResult(
            total_rows=len(rows),
            valid_rows=len(rows) - error_rows,
            error_rows=error_rows,
            rows=rows,
        )

    def commit(
        self,
        transactions: list[ImportTransaction],
        file_hash: str | None = None,
        file_name: str | None = None,
    ) -> ImportResult:
        """Registra lote no banco em ordem cronológica.

        All-or-nothing: qualquer erro propaga exceção. O rollback é responsabilidade
        do get_db() do chamador — audit log também é desfeito em caso de falha.

        Se file_hash for fornecido, cria registro de audit log após o commit bem-sucedido,
        dentro da mesma sessão (atomicidade garantida).
        """
        sorted_txs = sorted(transactions, key=lambda t: t.tx_date)
        rows: list[ImportRowResult] = []

        for tx in sorted_txs:
            asset = self._asset_repo.get_by_ticker(tx.ticker)
            if asset is None:
                raise ValueError(f"Ativo '{tx.ticker}' não encontrado")

            self._tx_service.register(
                asset_id=asset.id,
                transaction_type=tx.transaction_type,
                tx_date=tx.tx_date,
                total_amount=tx.total_amount,
                quantity=tx.quantity,
                unit_price=tx.unit_price,
                fees=tx.fees,
                notes=tx.notes,
                new_position_value=tx.new_position_value,
            )

            rows.append(ImportRowResult(
                row_number=tx.row_number,
                ticker=tx.ticker,
                transaction_type=tx.transaction_type.value,
                tx_date=tx.tx_date,
                total_amount=tx.total_amount,
                status="ok",
            ))

        result = ImportResult(
            total_rows=len(rows),
            valid_rows=len(rows),
            error_rows=0,
            rows=rows,
        )

        if file_hash is not None:
            self._log_repo.create(
                file_hash=file_hash,
                status="success",
                total_rows=result.total_rows,
                valid_rows=result.valid_rows,
                error_rows=0,
                file_name=file_name,
            )

        return result

    def _calc_current_qty(self, asset_id: int) -> Decimal:
        """Quantidade líquida atual: soma de BUY/INITIAL_BALANCE menos SELL."""
        txs = self._contrib_repo.get_by_asset(asset_id)
        qty = Decimal("0")
        for tx in txs:
            tt = TransactionType(tx.transaction_type)
            if tt in (TransactionType.INITIAL_BALANCE, TransactionType.BUY):
                qty += tx.quantity or Decimal("0")
            elif tt == TransactionType.SELL:
                qty -= tx.quantity or Decimal("0")
        return qty
