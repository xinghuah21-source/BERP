"""user baseline fields

Revision ID: 5a2f9e2d1b4c
Revises: 2b8b9c2c0a5a
Create Date: 2026-04-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5a2f9e2d1b4c"
down_revision: Union[str, None] = "2b8b9c2c0a5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("baseline_arousal", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("baseline_valence", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("baseline_calibrated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "baseline_calibrated_at")
    op.drop_column("users", "baseline_valence")
    op.drop_column("users", "baseline_arousal")
