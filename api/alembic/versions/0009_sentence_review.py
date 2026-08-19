"""output_sentences: the reviewer's decision, and an edited replacement

Accept/flag lived in browser state, so a reload lost it and the export ignored
it — a reviewer could strike a sentence and still find it in the PDF. The
decision belongs with the sentence: it is what makes the publish render
trustworthy, and it is the human half of a human-in-the-loop system.

`edited_text` holds a reviewer's rewrite. It deliberately does not overwrite
`text`: the generated sentence and its verdict stay on record, so what the model
produced remains auditable next to what was published.

Revision ID: 0009_sentence_review
Revises: 0008_job_progress
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_sentence_review"
down_revision: str | None = "0008_job_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # "accepted" | "flagged"; NULL means the reviewer has not ruled on it.
    op.add_column("output_sentences", sa.Column("decision", sa.String(length=10), nullable=True))
    op.add_column("output_sentences", sa.Column("edited_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("output_sentences", "edited_text")
    op.drop_column("output_sentences", "decision")
