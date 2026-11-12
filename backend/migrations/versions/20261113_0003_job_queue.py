"""durable job queue (jobs table) and solicitation file progress

Background work used to run inside the API process and was lost on a restart. Jobs are now
rows in Postgres, claimed by workers with FOR UPDATE SKIP LOCKED (see app/jobs.py).

Row-level security: an API request sees only its organization's jobs, like every other table.
A worker claims jobs for all organizations, so the policy also admits sessions that set
app.worker = 'on'; the job's own work then runs in a session bound to the job's organization.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

ORG_SETTING = "NULLIF(current_setting('app.org_id', true), '')::integer"
WORKER = "current_setting('app.worker', true) = 'on'"


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_by", sa.String(100), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_org_id", "jobs", ["org_id"])
    op.create_index("ix_jobs_claim", "jobs", ["status", "run_after"])
    op.create_index("uq_jobs_live_target", "jobs", ["kind", "target_id"], unique=True,
                    postgresql_where=sa.text("status IN ('queued', 'running')"))
    op.execute("ALTER TABLE jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE jobs FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON jobs "
        f"USING (org_id = {ORG_SETTING} OR {WORKER}) WITH CHECK (org_id = {ORG_SETTING} OR {WORKER})"
    )
    op.add_column("solicitation_files", sa.Column("progress", sa.String(200), nullable=True))

    # Work that was pending under the old in-process runner gets a job, so nothing is stranded.
    op.execute("""
        DO $$
        DECLARE o integer;
        BEGIN
          PERFORM set_config('app.worker', 'on', true);
          FOR o IN SELECT id FROM organizations LOOP
            PERFORM set_config('app.org_id', o::text, true);
            INSERT INTO jobs (org_id, kind, target_id, status, attempts, max_attempts, run_after, created_at)
              SELECT org_id, 'ingest_document', id, 'queued', 0, 3, now(), now()
              FROM library_documents WHERE status IN ('queued', 'processing');
            INSERT INTO jobs (org_id, kind, target_id, status, attempts, max_attempts, run_after, created_at)
              SELECT org_id, 'process_file', id, 'queued', 0, 3, now(), now()
              FROM solicitation_files WHERE status IN ('queued', 'processing');
            INSERT INTO jobs (org_id, kind, target_id, status, attempts, max_attempts, run_after, created_at)
              SELECT org_id, 'draft_answer', requirement_id, 'queued', 0, 3, now(), now()
              FROM answers WHERE status IN ('queued', 'drafting');
          END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.drop_column("solicitation_files", "progress")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON jobs")
    op.drop_index("uq_jobs_live_target", table_name="jobs")
    op.drop_index("ix_jobs_claim", table_name="jobs")
    op.drop_index("ix_jobs_org_id", table_name="jobs")
    op.drop_table("jobs")
