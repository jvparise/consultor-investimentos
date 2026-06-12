"""add benchmark_history table

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'benchmark_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('benchmark_name', sa.String(10), nullable=False),
        sa.Column('reference_date', sa.Date, nullable=False),
        sa.Column('value', sa.Numeric(20, 8), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('benchmark_name', 'reference_date', name='uq_benchmark_date'),
    )
    op.create_index('ix_benchmark_history_benchmark_name', 'benchmark_history', ['benchmark_name'])


def downgrade() -> None:
    op.drop_index('ix_benchmark_history_benchmark_name', table_name='benchmark_history')
    op.drop_table('benchmark_history')
