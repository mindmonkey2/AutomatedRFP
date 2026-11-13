"""search by meaning: chunk_embeddings (if pgvector is installed); dedupe only queued jobs

chunk_embeddings needs the pgvector extension, which only a superuser can install (the setup
scripts do: deploy/postgres-init.*). Without it this migration skips the table and the app keeps
using keyword search; once the extension exists, the table is created at startup when
RFP_EMBEDDING_PROVIDER is set.

The jobs uniqueness rule now covers queued jobs only: a running job must not stop new work for
the same target from being queued (an embedding job could otherwise miss passages added while it
runs, and a forced redraft would be dropped).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-13
"""
import logging

import sqlalchemy as sa
from alembic import op

from app.embeddings import create_schema

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    op.drop_index("uq_jobs_live_target", table_name="jobs")
    op.create_index("uq_jobs_queued_target", "jobs", ["kind", "target_id"], unique=True,
                    postgresql_where=sa.text("status = 'queued'"))
    if not create_schema(op.get_bind()):
        log.warning("pgvector is not installed: skipping chunk_embeddings (search by meaning stays off). "
                    "To enable it later, run as a superuser: CREATE EXTENSION vector;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunk_embeddings")
    op.drop_index("uq_jobs_queued_target", table_name="jobs")
    op.create_index("uq_jobs_live_target", "jobs", ["kind", "target_id"], unique=True,
                    postgresql_where=sa.text("status IN ('queued', 'running')"))
