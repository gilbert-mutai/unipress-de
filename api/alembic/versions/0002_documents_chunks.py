"""documents + chunks tables; jobs.document_id

Revision ID: 0002_documents_chunks
Revises: 0001_initial
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_documents_chunks"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_key", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_status", "documents", ["status"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=200), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])

    op.add_column(
        "jobs",
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_jobs_document_id", "jobs", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_document_id", table_name="jobs")
    op.drop_column("jobs", "document_id")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_table("documents")
