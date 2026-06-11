"""create exchange_rates table

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-06-11 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'exchange_rates',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('currency', sa.String(3), nullable=False, unique=True),
        sa.Column('rate', sa.Numeric(12, 6), nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('exchange_rates')
