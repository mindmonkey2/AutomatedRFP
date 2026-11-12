"""Database engine and tenant-scoped sessions.

Tenant isolation is enforced twice:
1. Every query in the app filters on org_id.
2. Postgres row-level security (see the initial migration) hides other tenants' rows.
   The policies read the `app.org_id` setting, which `bind_org` sets for the current
   transaction. With no org bound, tenant tables return no rows (fail closed).
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

_SET_ORG = text("SELECT set_config('app.org_id', :org, true)")


@event.listens_for(Session, "after_begin")
def _apply_org(session: Session, _transaction, connection) -> None:
    """Re-apply the tenant setting at the start of every transaction (it is transaction-local)."""
    org = session.info.get("org_id")
    if org is not None:
        connection.execute(_SET_ORG, {"org": str(org)})


def bind_org(session: Session, org_id: int) -> None:
    session.info["org_id"] = org_id
    if session.in_transaction():
        session.execute(_SET_ORG, {"org": str(org_id)})


@contextmanager
def org_session(org_id: int) -> Iterator[Session]:
    """Session for background jobs, scoped to one organization."""
    with SessionLocal() as s:
        bind_org(s, org_id)
        yield s


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def check_role() -> None:
    """Warn loudly if the app role would bypass row-level security."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    if row.rolsuper or row.rolbypassrls:
        log.warning(
            "Database role is a superuser or has BYPASSRLS: row-level security is NOT enforced. "
            "Connect as a regular role (see README)."
        )
