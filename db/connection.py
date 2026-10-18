from contextlib import contextmanager
from typing import Generator
import psycopg
from psycopg.rows import dict_row
from config.settings import settings


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """
    Context manager providing a PostgreSQL connection.
    Automatically handles commit on success and rollback on exceptions.
    """
    conn = psycopg.connect(
        settings.postgres_dsn,
        row_factory=dict_row,
        connect_timeout=5
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def test_connection() -> tuple[bool, str]:
    """
    Verifies that Postgres is reachable and that the schema has been initialized.
    Used during bootstrap health checks.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'job_applications'
                    );
                """)
                table_exists = cur.fetchone()["exists"]

        if not table_exists:
            return False, "Connected to DB, but table 'job_applications' does not exist. Run schema.sql."
        return True, "Connected (Table 'job_applications' is present)"

    except Exception as e:
        return False, f"PostgreSQL connection failed: {str(e)}"