"""output_sentences: video-scene fields (timecode, on_screen, visual)

Revision ID: 0006_scene_fields
Revises: 0005_output_coverage
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_scene_fields"
down_revision: str | None = "0005_output_coverage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("output_sentences", sa.Column("timecode", sa.String(length=40), nullable=True))
    op.add_column("output_sentences", sa.Column("on_screen", sa.Text(), nullable=True))
    op.add_column("output_sentences", sa.Column("visual", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("output_sentences", "visual")
    op.drop_column("output_sentences", "on_screen")
    op.drop_column("output_sentences", "timecode")
