"""add target_etf_pct, target_fii_brick_pct, target_fii_paper_pct; drop target_fii_pct

Revision ID: f7e8d9c0b1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-10 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'f7e8d9c0b1a2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('user_settings') as batch_op:
        batch_op.add_column(sa.Column('target_etf_pct', sa.Numeric(5, 2), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('target_fii_brick_pct', sa.Numeric(5, 2), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('target_fii_paper_pct', sa.Numeric(5, 2), nullable=False, server_default='0'))

    op.execute("UPDATE user_settings SET target_fii_brick_pct = target_fii_pct")

    with op.batch_alter_table('user_settings') as batch_op:
        batch_op.drop_column('target_fii_pct')


def downgrade() -> None:
    with op.batch_alter_table('user_settings') as batch_op:
        batch_op.add_column(sa.Column('target_fii_pct', sa.Numeric(5, 2), nullable=False, server_default='0'))

    op.execute("UPDATE user_settings SET target_fii_pct = target_fii_brick_pct")

    with op.batch_alter_table('user_settings') as batch_op:
        batch_op.drop_column('target_etf_pct')
        batch_op.drop_column('target_fii_brick_pct')
        batch_op.drop_column('target_fii_paper_pct')
