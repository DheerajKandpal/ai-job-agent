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
