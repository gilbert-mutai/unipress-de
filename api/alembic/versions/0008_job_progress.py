"""jobs: worker-reported progress

Generation reported a single stage, so the UI could only show an indeterminate
spinner for what is often a minute of work. The worker now reports real
sub-phases, writing, verifying sentence n of m, scoring coverage, and this
column carries the resulting 0-100 so the percentage on screen reflects work
actually completed rather than elapsed time.

Revision ID: 0008_job_progress
Revises: 0007_title_verdict
Create Date: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_job_progress"
down_revision: str | None = "0007_title_verdict"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("progress", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("detail", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "detail")
    op.drop_column("jobs", "progress")
