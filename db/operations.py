# db/operations.py
from typing import Optional, Dict, Any
from db.connection import get_db_connection


def get_existing_application(company: str, job_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, company, job_id, role, job_url, job_description, match_tier, status, 
                       source_resume_path, rewritten_resume_path, recruiter_verdict, referral_message,
                       created_at, updated_at
                FROM job_applications
                WHERE LOWER(company) = LOWER(%s) AND LOWER(job_id) = LOWER(%s);
            """, (company, job_id))
            row = cur.fetchone()
            if row:
                return dict(row)
    return None


def save_application_state(state: Dict[str, Any]) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO job_applications (
                    company, job_id, role, job_url, job_description, 
                    match_tier, status, source_resume_path, rewritten_resume_path, 
                    recruiter_verdict, referral_message, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (company, job_id) DO UPDATE SET
                    role = EXCLUDED.role,
                    job_url = EXCLUDED.job_url,
                    job_description = EXCLUDED.job_description,
                    match_tier = EXCLUDED.match_tier,
                    status = EXCLUDED.status,
                    source_resume_path = COALESCE(EXCLUDED.source_resume_path, job_applications.source_resume_path),
                    rewritten_resume_path = EXCLUDED.rewritten_resume_path,
                    recruiter_verdict = EXCLUDED.recruiter_verdict,
                    referral_message = EXCLUDED.referral_message,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                state["company"],
                state["job_id"],
                state["role"],
                state.get("job_url"),
                state["job_description"],
                state.get("match_tier"),
                state.get("status"),
                state.get("source_resume_path"),
                state.get("saved_file_path") or state.get("rewritten_resume_path"),
                state.get("recruiter_verdict"),
                state.get("referral_message")
            ))


def get_applications_history(offset: int = 0, limit: int = 15, search: Optional[str] = None) -> Dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            where_clause = ""
            params = []
            if search and search.strip():
                term = f"%{search.strip().lower()}%"
                where_clause = "WHERE LOWER(company) LIKE %s OR LOWER(role) LIKE %s OR LOWER(job_id) LIKE %s"
                params = [term, term, term]

            count_query = f"SELECT COUNT(*) as total FROM job_applications {where_clause};"
            cur.execute(count_query, params)
            total = cur.fetchone()["total"]

            fetch_query = f"""
                SELECT id, company, job_id, role, job_url, match_tier, status, 
                       source_resume_path, rewritten_resume_path, recruiter_verdict, referral_message,
                       created_at, updated_at
                FROM job_applications
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s;
            """
            cur.execute(fetch_query, params + [limit, offset])
            rows = [dict(r) for r in cur.fetchall()]
            return {
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": (offset + len(rows)) < total,
                "items": rows
            }


def get_application_by_id(app_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, company, job_id, role, job_url, job_description, match_tier, status, 
                       source_resume_path, rewritten_resume_path, recruiter_verdict, referral_message,
                       created_at, updated_at
                FROM job_applications
                WHERE id = %s;
            """, (app_id,))
            row = cur.fetchone()
            if row:
                return dict(row)
    return None