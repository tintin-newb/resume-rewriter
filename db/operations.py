# db/operations.py
from typing import Optional, Dict, Any
import psycopg
from config.settings import settings


def get_existing_application(company: str, job_id: str) -> Optional[Dict[str, Any]]:
    """Checks if a job posting has already been evaluated."""
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, company, job_id, role, match_score, status, rewritten_resume_path, referral_message
                FROM job_applications
                WHERE LOWER(company) = LOWER(%s) AND LOWER(job_id) = LOWER(%s)
            """, (company, job_id))
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "company": row[1],
                    "job_id": row[2],
                    "role": row[3],
                    "match_score": float(row[4]) if row[4] else None,
                    "status": row[5],
                    "rewritten_resume_path": row[6],
                    "referral_message": row[7]
                }
    return None


def save_application_state(state: Dict[str, Any]) -> None:
    """Inserts or updates the job application state upon pipeline completion."""
    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO job_applications (
                    company, job_id, role, job_url, job_description, 
                    match_score, status, rewritten_resume_path, referral_message, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (company, job_id) DO UPDATE SET
                    match_score = EXCLUDED.match_score,
                    status = EXCLUDED.status,
                    rewritten_resume_path = EXCLUDED.rewritten_resume_path,
                    referral_message = EXCLUDED.referral_message,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                state["company"],
                state["job_id"],
                state["role"],
                state.get("job_url"),
                state["job_description"],
                state.get("match_score"),
                state.get("status"),
                state.get("saved_file_path"),
                state.get("referral_message")
            ))
            conn.commit()