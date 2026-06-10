"""migrate asset_class FIIs to FII Tijolo

Revision ID: a1b2c3d4e5f6
Revises: 6690aa5c7f86
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6690aa5c7f86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE assets SET asset_class='FII Tijolo' WHERE asset_class='FIIs'")
    op.execute(
        "UPDATE portfolio_snapshot_details "
        "SET asset_class='FII Tijolo' WHERE asset_class='FIIs'"
    )


def downgrade() -> None:
    op.execute("UPDATE assets SET asset_class='FIIs' WHERE asset_class='FII Tijolo'")
    op.execute(
        "UPDATE portfolio_snapshot_details "
        "SET asset_class='FIIs' WHERE asset_class='FII Tijolo'"
    )
