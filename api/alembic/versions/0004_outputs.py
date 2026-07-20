"""outputs + output_sentences tables

Revision ID: 0004_outputs
Revises: 0003_claims
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_outputs"
down_revision: str | None = "0003_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outputs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("output_type", sa.String(length=20), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_outputs_document_id", "outputs", ["document_id"])

    op.create_table(
        "output_sentences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "output_id",
            sa.String(length=36),
            sa.ForeignKey("outputs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("claim_ids", sa.JSON(), nullable=True),
        sa.Column("section", sa.String(length=40), nullable=True),
        sa.Column("verdict", sa.String(length=20), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
    )
    op.create_index("ix_output_sentences_output_id", "output_sentences", ["output_id"])


def downgrade() -> None:
    op.drop_index("ix_output_sentences_output_id", table_name="output_sentences")
    op.drop_table("output_sentences")
    op.drop_index("ix_outputs_document_id", table_name="outputs")
    op.drop_table("outputs")
