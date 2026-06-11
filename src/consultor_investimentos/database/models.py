from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consultor_investimentos.database.connection import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(30), nullable=False)
    income_type: Mapped[str] = mapped_column(String(20), nullable=False)
    tracking_type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="asset", cascade="all, delete-orphan"
    )
    prices: Mapped[list["AssetPrice"]] = relationship(
        "AssetPrice", back_populates="asset", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Asset {self.ticker} ({self.asset_class})>"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("assets.id"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # Nullable: apenas QUANTITY_PRICE usa estes campos
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 6))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 6))

    # Sempre preenchido:
    # - QUANTITY_PRICE: qty × unit_price (já deduzindo fees)
    # - VALUE_ONLY: valor total da posição / aporte / resgate
    # - DIVIDEND / INTEREST: valor recebido
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    fees: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    asset: Mapped["Asset"] = relationship("Asset", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction {self.transaction_type} {self.total_amount} em {self.date}>"


class AssetPrice(Base):
    __tablename__ = "asset_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("assets.id"), nullable=False
    )
    price_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Semântica por tracking_type do ativo:
    # - QUANTITY_PRICE → preço unitário por cota/ação
    # - VALUE_ONLY     → valor TOTAL da posição nesta data
    price: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)

    source: Mapped[str] = mapped_column(String(10), default="MANUAL")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    asset: Mapped["Asset"] = relationship("Asset", back_populates="prices")

    __table_args__ = (UniqueConstraint("asset_id", "price_date", name="uq_asset_price_date"),)

    def __repr__(self) -> str:
        return f"<AssetPrice asset_id={self.asset_id} {self.price_date} {self.price}>"


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    total_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    snapshot_type: Mapped[str] = mapped_column(
        String(15), default="CALCULATED"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    details: Mapped[list["PortfolioSnapshotDetail"]] = relationship(
        "PortfolioSnapshotDetail",
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PortfolioSnapshot {self.snapshot_date} R${self.total_value}>"


class PortfolioSnapshotDetail(Base):
    __tablename__ = "portfolio_snapshot_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("portfolio_snapshots.id"), nullable=False
    )
    asset_class: Mapped[str] = mapped_column(String(30), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    snapshot: Mapped["PortfolioSnapshot"] = relationship(
        "PortfolioSnapshot", back_populates="details"
    )

    def __repr__(self) -> str:
        return f"<SnapshotDetail {self.asset_class} {self.percentage}%>"


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    def __repr__(self) -> str:
        return f"<Goal '{self.name}' R${self.target_value}>"


class ImportLog(Base):
    __tablename__ = "import_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # 'success' | 'failed'
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    def __repr__(self) -> str:
        return f"<ImportLog {self.file_hash[:8]}... {self.status}>"


class UserSettings(Base):
    __tablename__ = "user_settings"

    # Single-user: sempre id=1. get_or_create() garante isso.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    user_name: Mapped[str] = mapped_column(String(100), default="Investidor")
    monthly_contribution: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0")
    )
    monthly_expenses: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0")
    )
    risk_profile: Mapped[str] = mapped_column(String(15), default="Moderado")

    # Percentuais alvo de alocação por classe (soma deve ser 0 ou 100)
    target_equity_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )
    target_fixed_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )
    target_etf_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )
    target_fii_brick_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )
    target_fii_paper_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )
    target_intl_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )
    target_crypto_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )
    target_other_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_user_settings_single_row"),
    )

    def __repr__(self) -> str:
        return f"<UserSettings user='{self.user_name}'>"


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currency: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ExchangeRate {self.currency}={self.rate}>"
