"""
db_service.py
-------------
Fetches resume JSON from the PostgreSQL `resumes` table.

Table schema:
    id           INT
    version_name TEXT
    content      JSONB
"""

import psycopg2
import psycopg2.extras  # for RealDictCursor / automatic JSONB → dict
from app.core.config import settings
from app.core.logging import get_logger

ALLOWED_STATUSES = ("applied", "interview", "rejected")
logger = get_logger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resumes (
    id BIGSERIAL PRIMARY KEY,
    version_name TEXT NOT NULL UNIQUE,
    content JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE resumes
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE resumes
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_resumes_version_name ON resumes(version_name);
CREATE INDEX IF NOT EXISTS idx_resumes_updated_at ON resumes(updated_at DESC);

CREATE TABLE IF NOT EXISTS applications (
    id BIGSERIAL PRIMARY KEY,
    job_title TEXT NOT NULL,
    company TEXT NOT NULL,
    job_description TEXT NOT NULL,
    match_score DOUBLE PRECISION,
    resume_version TEXT,
    cover_letter TEXT,
    status TEXT NOT NULL DEFAULT 'applied',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT applications_status_check CHECK (
        status IN ('applied', 'interview', 'rejected')
    )
);

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_applications_created_at ON applications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_company ON applications(company);

CREATE TABLE IF NOT EXISTS application_logs (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT REFERENCES applications(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_application_logs_app_id ON application_logs(application_id);
CREATE INDEX IF NOT EXISTS idx_application_logs_created_at ON application_logs(created_at DESC);
"""

SCHEMA_VERSION = 1
SCHEMA_DESCRIPTION = "initial schema for resumes, applications, and application_logs"


def _get_connection():
    """Open and return a psycopg2 connection using environment variables."""
    return psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )


def check_database_connection() -> None:
    conn = None
    try:
        logger.info("db startup check start")
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        logger.info("db startup check ok")
    except psycopg2.Error as exc:
        logger.error(
            "db startup check failed",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"error": str(exc)},
        )
        raise RuntimeError("Database connectivity check failed during startup") from exc
    finally:
        if conn is not None:
            conn.close()


def init_database() -> None:
    conn = None
    try:
        logger.info("db init start", extra={"schema_version": SCHEMA_VERSION})
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            cur.execute(
                """
                INSERT INTO schema_migrations (version, description)
                VALUES (%s, %s)
                ON CONFLICT (version) DO NOTHING
                """,
                (SCHEMA_VERSION, SCHEMA_DESCRIPTION),
            )
        conn.commit()
        logger.info("db init complete", extra={"schema_version": SCHEMA_VERSION})
    except psycopg2.Error as exc:
        if conn is not None:
            conn.rollback()
        logger.error(
            "db init failed",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"error": str(exc), "schema_version": SCHEMA_VERSION},
        )
        raise RuntimeError("Database schema initialization failed during startup") from exc
    finally:
        if conn is not None:
            conn.close()


def get_resume_by_version(version_name: str) -> dict | None:
    """
    Fetch the content of a resume by its version name.

    Parameters
    ----------
    version_name : str
        The version identifier stored in the `version_name` column
        (e.g. "base_v2").

    Returns
    -------
    dict | None
        The resume content as a Python dict, or None if not found /
        an error occurred.
    """
    conn = None
    try:
        logger.info("db call start: get_resume_by_version")
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT content FROM resumes WHERE version_name = %s",
                (version_name,),
            )
            row = cur.fetchone()

        if row is None:
            logger.info("db call end: get_resume_by_version")
            return None

        # psycopg2 automatically deserialises JSONB → dict when using the
        # default cursor; row[0] is already a Python dict.
        logger.info("db call end: get_resume_by_version")
        return row[0]

    except psycopg2.OperationalError as e:
        logger.error("db call error: get_resume_by_version (%s)", e)
        return None
    except psycopg2.Error as e:
        logger.error("db call error: get_resume_by_version (%s)", e)
        return None
    finally:
        if conn is not None:
            conn.close()


def get_all_applications(limit: int = 10, offset: int = 0) -> list[dict]:
    """
    Fetch applications ordered by newest first with pagination.
    """
    conn = None
    try:
        logger.info("db call start: get_all_applications")
        conn = _get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    job_title,
                    company,
                    status,
                    created_at
                FROM applications
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
        logger.info("db call end: get_all_applications")
        return list(rows)
    except psycopg2.Error as e:
        logger.error("db call error: get_all_applications (%s)", e)
        raise RuntimeError(f"Failed to fetch applications: {e}") from e
    finally:
        if conn is not None:
            conn.close()


def save_application(data: dict) -> int:
    conn = None
    try:
        logger.info("db call start: save_application")
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO applications (
                    job_title,
                    company,
                    job_description,
                    match_score,
                    resume_version,
                    cover_letter,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    data["job_title"],
                    data["company"],
                    data["job_description"],
                    data.get("match_score"),
                    data.get("resume_version"),
                    data.get("cover_letter"),
                    data.get("status", "applied"),
                ),
            )
            row = cur.fetchone()
        conn.commit()
        logger.info("db call end: save_application")
        return row[0]
    except KeyError as e:
        if conn is not None:
            conn.rollback()
        logger.error("db call error: save_application (%s)", e)
        raise ValueError(f"Missing required field: {e.args[0]}") from e
    except psycopg2.Error as e:
        if conn is not None:
            conn.rollback()
        logger.error("db call error: save_application (%s)", e)
        raise RuntimeError(f"Failed to save application: {e}") from e
    finally:
        if conn is not None:
            conn.close()


def update_status(application_id: int, status: str) -> None:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid status: {status}. Allowed: {ALLOWED_STATUSES}")

    conn = None
    try:
        logger.info("db call start: update_status")
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE applications
                SET status = %s
                WHERE id = %s
                """,
                (status, application_id),
            )
            updated = cur.rowcount
        if updated == 0:
            conn.rollback()
            raise ValueError("Application not found")
        conn.commit()
        logger.info("db call end: update_status")
    except psycopg2.Error as e:
        if conn is not None:
            conn.rollback()
        logger.error("db call error: update_status (%s)", e)
        raise RuntimeError(f"Failed to update status: {e}") from e
    finally:
        if conn is not None:
            conn.close()


def get_application_by_id(application_id: int) -> dict:
    conn = None
    try:
        logger.info("db call start: get_application_by_id")
        conn = _get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    job_title,
                    company,
                    job_description,
                    match_score,
                    resume_version,
                    cover_letter,
                    status,
                    created_at
                FROM applications
                WHERE id = %s
                """,
                (application_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise ValueError("Application not found")
        logger.info("db call end: get_application_by_id")
        return dict(row)
    except ValueError:
        raise
    except psycopg2.Error as e:
        logger.error("db call error: get_application_by_id (%s)", e)
        raise RuntimeError(f"Failed to fetch application: {e}") from e
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# Quick smoke test — run with:  python app/services/tracker/db_service.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    version = settings.RESUME_VERSION
    logger.info("db smoke test start: get_resume_by_version (%s)", version)

    result = get_resume_by_version(version)

    if result is None:
        logger.info("db smoke test result: resume not found (%s)", version)
    else:
        import json
        logger.info("db smoke test result: %s", json.dumps(result, indent=2))
