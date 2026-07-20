"""outputs.coverage

Revision ID: 0005_output_coverage
Revises: 0004_outputs
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_output_coverage"
down_revision: str | None = "0004_outputs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outputs", sa.Column("coverage", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("outputs", "coverage")
