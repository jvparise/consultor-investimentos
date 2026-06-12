from decimal import Decimal
from enum import Enum


class Currency(str, Enum):
    BRL = "BRL"
    USD = "USD"
    EUR = "EUR"


class AssetClass(str, Enum):
    EQUITY = "Ações"
    ETF = "ETF"
    FII_BRICK = "FII Tijolo"
    FII_PAPER = "FII Papel"
    FIXED_INCOME = "Renda Fixa"
    INTERNATIONAL = "Internacional"
    CRYPTO = "Cripto"
    CASH = "Caixa / Liquidez"
    OTHER = "Outros"


class IncomeType(str, Enum):
    VARIABLE = "Renda Variável"
    FIXED = "Renda Fixa"
    HYBRID = "Híbrido"


class AssetTrackingType(str, Enum):
    QUANTITY_PRICE = "Quantidade × Preço"
    VALUE_ONLY = "Valor Total"


class TransactionType(str, Enum):
    INITIAL_BALANCE = "Saldo Inicial"
    BUY = "Compra"
    SELL = "Venda"
    CONTRIBUTION = "Aporte"
    WITHDRAWAL = "Resgate"
    DIVIDEND = "Dividendo / Rendimento"
    INTEREST = "Juros / Cupom"
    OTHER = "Outro"


# Tipos de transação permitidos por AssetTrackingType
ALLOWED_TRANSACTION_TYPES: dict[AssetTrackingType, list[TransactionType]] = {
    AssetTrackingType.QUANTITY_PRICE: [
        TransactionType.INITIAL_BALANCE,
        TransactionType.BUY,
        TransactionType.SELL,
        TransactionType.DIVIDEND,
        TransactionType.OTHER,
    ],
    AssetTrackingType.VALUE_ONLY: [
        TransactionType.INITIAL_BALANCE,
        TransactionType.CONTRIBUTION,
        TransactionType.WITHDRAWAL,
        TransactionType.DIVIDEND,
        TransactionType.INTEREST,
        TransactionType.OTHER,
    ],
}


class Benchmark(str, Enum):
    CDI = "CDI"
    SELIC = "SELIC"
    IPCA = "IPCA"
    IBOV = "IBOV"
    SP500 = "SP500"


class SnapshotType(str, Enum):
    MANUAL = "Manual"
    CALCULATED = "Calculado"
    INCOMPLETE = "Incompleto"


class RiskProfile(str, Enum):
    CONSERVATIVE = "Conservador"
    MODERATE = "Moderado"
    AGGRESSIVE = "Agressivo"


class ProjectionScenario(str, Enum):
    CONSERVATIVE = "Conservador"
    MODERATE = "Moderado"
    AGGRESSIVE = "Otimista"


SCENARIO_ANNUAL_RATES: dict[ProjectionScenario, Decimal] = {
    ProjectionScenario.CONSERVATIVE: Decimal("0.07"),
    ProjectionScenario.MODERATE: Decimal("0.10"),
    ProjectionScenario.AGGRESSIVE: Decimal("0.13"),
}

SCENARIO_LABELS: dict[ProjectionScenario, str] = {
    ProjectionScenario.CONSERVATIVE: "Conservador — 7% a.a.",
    ProjectionScenario.MODERATE: "Moderado — 10% a.a.",
    ProjectionScenario.AGGRESSIVE: "Otimista — 13% a.a.",
}

# Regra dos 4%: patrimônio necessário = gastos mensais × 12 / 0.04 = gastos × 300
FIRE_MULTIPLIER = Decimal("300")

# Projeção: máximo de 600 meses (50 anos) antes de declarar "inatingível"
MAX_PROJECTION_MONTHS = 600

RENTABILITY_DISCLAIMER = (
    "Rentabilidade calculada pelo método simplificado: "
    "(Valor Atual − Total Aportado) ÷ Total Aportado. "
    "Não considera o timing dos aportes (não é TWR)."
)

# Mapeamento de classe para cor nos gráficos
ASSET_CLASS_COLORS: dict[AssetClass, str] = {
    AssetClass.EQUITY: "#2196F3",
    AssetClass.ETF: "#00BCD4",
    AssetClass.FII_BRICK: "#4CAF50",
    AssetClass.FII_PAPER: "#8BC34A",
    AssetClass.FIXED_INCOME: "#FF9800",
    AssetClass.INTERNATIONAL: "#9C27B0",
    AssetClass.CRYPTO: "#F44336",
    AssetClass.CASH: "#607D8B",
    AssetClass.OTHER: "#795548",
}
