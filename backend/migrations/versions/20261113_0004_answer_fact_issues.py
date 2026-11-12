"""answers.fact_issues: figures and names in an answer that its sources do not contain

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("answers", sa.Column("fact_issues", sa.JSON(), nullable=False, server_default="[]"))
    op.alter_column("answers", "fact_issues", server_default=None)


def downgrade() -> None:
    op.drop_column("answers", "fact_issues")
