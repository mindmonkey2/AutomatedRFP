"""requirements.changed_by_file_id: SET NULL when the file is deleted

Without it, deleting a bid that has an addendum failed: the requirements the addendum
changed still pointed at the addendum file.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

FK = "requirements_changed_by_file_id_fkey"


def upgrade() -> None:
    op.drop_constraint(FK, "requirements", type_="foreignkey")
    op.create_foreign_key(FK, "requirements", "solicitation_files", ["changed_by_file_id"], ["id"],
                          ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint(FK, "requirements", type_="foreignkey")
    op.create_foreign_key(FK, "requirements", "solicitation_files", ["changed_by_file_id"], ["id"])
