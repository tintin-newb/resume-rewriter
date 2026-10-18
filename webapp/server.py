import os
import shutil
import time
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config.settings import (
    settings, 
    get_active_env_file, 
    save_home_env_config, 
    reload_settings, 
    APP_UPLOADS_DIR
)
from bootstrap import SystemBootstrap
from db.operations import get_applications_history, get_application_by_id
from webapp.pipeline_runner import create_pipeline_task, active_tasks, sanitize_filename

app = FastAPI(
    title="Agentic Resume Rewriter Web UI",
    version="1.0.0",
    description="Interactive Web Dashboard for Resume Tailoring and History Tracking"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Assets directory located inside webapp/assets
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ASSETS_HTML_DIR = ASSETS_DIR / "html"
ASSETS_CSS_DIR = ASSETS_DIR / "css"
ASSETS_JS_DIR = ASSETS_DIR / "js"

ASSETS_HTML_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_CSS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_JS_DIR.mkdir(parents=True, exist_ok=True)

# Mount static assets
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


@app.get("/")
async def root():
    index_file = ASSETS_HTML_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return FileResponse(index_file)


# --- System & Environment Configuration Endpoints ---

class ConfigUpdateRequest(BaseModel):
    OLLAMA_BASE_URL: Optional[str] = None
    OLLAMA_MODEL: Optional[str] = None
    REWRITER_TEMP: Optional[float] = None
    REFERRAL_TEMP: Optional[float] = None
    RECRUITER_TEMP: Optional[float] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[int] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    MIN_MATCH_SCORE: Optional[float] = None
    MAX_LOOPS: Optional[int] = None


@app.get("/api/config")
async def get_config():
    env_path = get_active_env_file()
    return {
        "env_file_path": str(env_path.resolve()),
        "settings": {
            "OLLAMA_BASE_URL": settings.OLLAMA_BASE_URL,
            "OLLAMA_MODEL": settings.OLLAMA_MODEL,
            "REWRITER_TEMP": settings.REWRITER_TEMP,
            "REFERRAL_TEMP": settings.REFERRAL_TEMP,
            "RECRUITER_TEMP": settings.RECRUITER_TEMP,
            "POSTGRES_HOST": settings.POSTGRES_HOST,
            "POSTGRES_PORT": settings.POSTGRES_PORT,
            "POSTGRES_DB": settings.POSTGRES_DB,
            "POSTGRES_USER": settings.POSTGRES_USER,
            "POSTGRES_PASSWORD": settings.POSTGRES_PASSWORD,
            "MIN_MATCH_SCORE": settings.MIN_MATCH_SCORE,
            "MAX_LOOPS": settings.MAX_LOOPS,
            "OUTPUT_DIR": str(settings.OUTPUT_DIR),
            "UPLOADS_DIR": str(APP_UPLOADS_DIR)
        }
    }


@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No configuration parameters provided.")

    saved_path = save_home_env_config(updates)
    return {
        "status": "success",
        "message": f"Configuration successfully updated in {saved_path}",
        "env_file_path": str(saved_path.resolve()),
        "settings": {
            "OLLAMA_BASE_URL": settings.OLLAMA_BASE_URL,
            "OLLAMA_MODEL": settings.OLLAMA_MODEL,
            "REWRITER_TEMP": settings.REWRITER_TEMP,
            "REFERRAL_TEMP": settings.REFERRAL_TEMP,
            "RECRUITER_TEMP": settings.RECRUITER_TEMP,
            "POSTGRES_HOST": settings.POSTGRES_HOST,
            "POSTGRES_PORT": settings.POSTGRES_PORT,
            "POSTGRES_DB": settings.POSTGRES_DB,
            "POSTGRES_USER": settings.POSTGRES_USER,
            "MIN_MATCH_SCORE": settings.MIN_MATCH_SCORE,
            "MAX_LOOPS": settings.MAX_LOOPS,
        }
    }


@app.post("/api/config/test")
async def test_system_connections(payload: Optional[Dict[str, Any]] = None):
    # Optionally test with transient overrides
    if payload:
        for k, v in payload.items():
            if hasattr(settings, k) and v is not None:
                setattr(settings, k, v)

    bootstrap = SystemBootstrap()
    pg_ok, pg_msg = bootstrap.check_postgres()
    ollama_ok, ollama_msg = bootstrap.check_ollama_and_model()

    return {
        "postgres": {"ok": pg_ok, "message": pg_msg},
        "ollama": {"ok": ollama_ok, "message": ollama_msg},
        "all_healthy": pg_ok and ollama_ok
    }


# --- Generation & Pipeline Endpoints ---

@app.post("/api/generate")
async def start_generation(
    resume: UploadFile = File(...),
    company: str = Form(...),
    job_id: str = Form(...),
    role: str = Form(...),
    url: Optional[str] = Form(None),
    jd_text: Optional[str] = Form(None),
    auxiliary_instructions: Optional[str] = Form(None),
    force: bool = Form(False),
    min_score: Optional[float] = Form(None),
    max_loops: Optional[int] = Form(None),
    skip_bootstrap: bool = Form(False)
):
    if not company.strip() or not job_id.strip() or not role.strip():
        raise HTTPException(status_code=400, detail="Company, Job ID, and Role are required.")

    if not url and not jd_text:
        raise HTTPException(status_code=400, detail="Either Job URL or Job Description text must be provided.")

    # Save uploaded resume to ~/.resume-rewriter/uploads/
    APP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(resume.filename or "uploaded_resume.pdf")
    timestamp = int(time.time())
    dest_path = APP_UPLOADS_DIR / f"{timestamp}_{safe_name}"

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save resume upload: {str(e)}")

    payload = {
        "company": company.strip(),
        "job_id": job_id.strip(),
        "role": role.strip(),
        "url": url.strip() if url else None,
        "jd_text": jd_text.strip() if jd_text else None,
        "auxiliary_instructions": auxiliary_instructions.strip() if auxiliary_instructions else None,
        "force": force,
        "min_score": min_score,
        "max_loops": max_loops,
        "skip_bootstrap": skip_bootstrap,
        "source_resume_path": str(dest_path.resolve())
    }

    task = create_pipeline_task(payload)
    return {
        "status": "started",
        "task_id": task.task_id,
        "source_resume_path": str(dest_path.resolve())
    }


@app.get("/api/generate/stream/{task_id}")
async def stream_generation(task_id: str):
    task = active_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Generation task not found.")

    return StreamingResponse(
        task.stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/generate/status/{task_id}")
async def get_generation_status(task_id: str):
    task = active_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Generation task not found.")

    return {
        "task_id": task.task_id,
        "status": task.status,
        "result": task.final_result,
        "error": task.error_message
    }


# --- History & Document Endpoints ---

@app.get("/api/history")
async def get_history(
    offset: int = Query(0, ge=0),
    limit: int = Query(15, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    try:
        data = get_applications_history(offset=offset, limit=limit, search=search)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")


@app.get("/api/history/{app_id}")
async def get_history_detail(app_id: int):
    try:
        record = get_application_by_id(app_id)
        if not record:
            raise HTTPException(status_code=404, detail="Application record not found.")
        return record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")


@app.get("/api/document/{doc_type}/{app_id}")
async def get_document(doc_type: str, app_id: int):
    if doc_type not in ("source", "rewritten"):
        raise HTTPException(status_code=400, detail="Invalid doc_type. Must be 'source' or 'rewritten'.")

    record = get_application_by_id(app_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application record not found.")

    path_str = record.get("source_resume_path") if doc_type == "source" else record.get("rewritten_resume_path")
    if not path_str:
        raise HTTPException(status_code=404, detail=f"No {doc_type} resume file path recorded for this entry.")

    doc_path = Path(path_str)
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found on disk at: {path_str}")

    suffix = doc_path.suffix.lower()
    if suffix == ".pdf":
        return FileResponse(doc_path, media_type="application/pdf", filename=doc_path.name)
    else:
        # Markdown / text
        content = doc_path.read_text(encoding="utf-8", errors="replace")
        return JSONResponse({
            "filename": doc_path.name,
            "extension": suffix,
            "content": content
        })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webapp.server:app", host="0.0.0.0", port=8000, reload=True)
