"""add currency column to assets

Revision ID: c1d2e3f4a5b6
Revises: f7e8d9c0b1a2
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'f7e8d9c0b1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('assets') as batch_op:
        batch_op.add_column(sa.Column('currency', sa.String(3), nullable=False, server_default='BRL'))


def downgrade() -> None:
    with op.batch_alter_table('assets') as batch_op:
        batch_op.drop_column('currency')
