"""outputs: the title's verdict, confidence, rationale and claim citations

The headline is the most-read line in a published output, so it is claim-bound and
verified like any factual sentence rather than left as unchecked prose.

Revision ID: 0007_title_verdict
Revises: 0006_scene_fields
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_title_verdict"
down_revision: str | None = "0006_scene_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outputs", sa.Column("title_claim_ids", sa.JSON(), nullable=True))
    op.add_column("outputs", sa.Column("title_verdict", sa.String(length=20), nullable=True))
    op.add_column("outputs", sa.Column("title_confidence", sa.Float(), nullable=True))
    op.add_column("outputs", sa.Column("title_rationale", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("outputs", "title_rationale")
    op.drop_column("outputs", "title_confidence")
    op.drop_column("outputs", "title_verdict")
    op.drop_column("outputs", "title_claim_ids")
