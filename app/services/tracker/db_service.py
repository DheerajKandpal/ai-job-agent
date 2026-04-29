"""
db_service.py
-------------
Fetches resume JSON from the PostgreSQL `resumes` table.

Table schema:
    id           INT
    version_name TEXT
    content      JSONB
"""

import os
import psycopg2
import psycopg2.extras  # for RealDictCursor / automatic JSONB → dict

ALLOWED_STATUSES = ("applied", "interview", "rejected")


def _get_connection():
    """Open and return a psycopg2 connection using environment variables."""
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "ai_job_agent")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "anil#9506")

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )


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
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT content FROM resumes WHERE version_name = %s",
                (version_name,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        # psycopg2 automatically deserialises JSONB → dict when using the
        # default cursor; row[0] is already a Python dict.
        return row[0]

    except psycopg2.OperationalError as e:
        print(f"[db_service] Connection error: {e}")
        return None
    except psycopg2.Error as e:
        print(f"[db_service] Query error: {e}")
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
        return list(rows)
    except psycopg2.Error as e:
        raise RuntimeError(f"Failed to fetch applications: {e}") from e
    finally:
        if conn is not None:
            conn.close()


def save_application(data: dict) -> int:
    conn = None
    try:
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
        return row[0]
    except KeyError as e:
        if conn is not None:
            conn.rollback()
        raise ValueError(f"Missing required field: {e.args[0]}") from e
    except psycopg2.Error as e:
        if conn is not None:
            conn.rollback()
        raise RuntimeError(f"Failed to save application: {e}") from e
    finally:
        if conn is not None:
            conn.close()


def update_status(application_id: int, status: str) -> None:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid status: {status}. Allowed: {ALLOWED_STATUSES}")

    conn = None
    try:
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
    except psycopg2.Error as e:
        if conn is not None:
            conn.rollback()
        raise RuntimeError(f"Failed to update status: {e}") from e
    finally:
        if conn is not None:
            conn.close()


def get_application_by_id(application_id: int) -> dict:
    conn = None
    try:
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
        return dict(row)
    except ValueError:
        raise
    except psycopg2.Error as e:
        raise RuntimeError(f"Failed to fetch application: {e}") from e
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# Quick smoke test — run with:  python app/services/tracker/db_service.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    version = "base_v2"
    print(f"[db_service] Fetching resume: '{version}' ...")

    result = get_resume_by_version(version)

    if result is None:
        print(f"[db_service] Resume '{version}' not found (or an error occurred).")
    else:
        import json
        print(json.dumps(result, indent=2))
