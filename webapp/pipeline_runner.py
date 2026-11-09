# webapp/pipeline_runner.py
import asyncio
import json
import re
import time
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, AsyncGenerator

from config.settings import settings, APP_UPLOADS_DIR
from bootstrap import SystemBootstrap
from parsers.resume_parser import ResumeParser
from scrapers.jd_scraper import JDScraper
from db.operations import get_existing_application, save_application_state
from agents.workflow import build_workflow
from agents.state import AgentState

# In-memory storage for tasks and their active event streams
active_tasks: Dict[str, Any] = {}


def _json_default(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default json code (e.g. datetime, Path)."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


class PipelineTask:
    def __init__(self, task_id: str, payload: Dict[str, Any]):
        self.task_id = task_id
        self.payload = payload
        self.queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.events_history: list[Dict[str, Any]] = []
        self.status = "PENDING"
        self.final_result: Optional[Dict[str, Any]] = None
        self.error_message: Optional[str] = None

    async def emit(self, event_type: str, data: Dict[str, Any]):
        event = {
            "task_id": self.task_id,
            "type": event_type,
            "timestamp": time.time(),
            "data": data
        }
        self.events_history.append(event)
        await self.queue.put(event)

    async def stream_events(self) -> AsyncGenerator[str, None]:
        # First send any historical events already queued
        for prev in self.events_history:
            yield f"data: {json.dumps(prev, default=_json_default)}\n\n"

        while True:
            event = await self.queue.get()
            yield f"data: {json.dumps(event, default=_json_default)}\n\n"
            if event["type"] in ("complete", "error", "cached"):
                break


def sanitize_filename(filename: str) -> str:
    return re.sub(r"[^\w\-\.]", "_", filename).strip()


async def run_pipeline_job(task: PipelineTask):
    task.status = "RUNNING"
    p = task.payload
    company = p["company"].strip()
    job_id = p["job_id"].strip()
    role = p["role"].strip()
    url = p.get("url")
    jd_text = p.get("jd_text")
    force = bool(p.get("force", False))
    skip_bootstrap = bool(p.get("skip_bootstrap", False))
    source_resume_path = p.get("source_resume_path")

    try:
        # Step 1: Pre-Flight Bootstrap Check
        await task.emit("step", {
            "step": "bootstrap",
            "title": "Pre-Flight System Check",
            "status": "in_progress",
            "message": "Validating PostgreSQL and Ollama readiness..."
        })

        if not skip_bootstrap:
            bootstrap = SystemBootstrap()
            pg_ok, pg_msg = bootstrap.check_postgres()
            ollama_ok, ollama_msg = bootstrap.check_ollama_and_model()

            if not pg_ok or not ollama_ok:
                err = f"Bootstrap verification failed. PostgreSQL: {pg_msg}. Ollama: {ollama_msg}"
                await task.emit("step", {
                    "step": "bootstrap",
                    "title": "Pre-Flight System Check",
                    "status": "failed",
                    "error": err,
                    "details": {"postgres": pg_msg, "ollama": ollama_msg}
                })
                task.status = "FAILED"
                task.error_message = err
                await task.emit("error", {"error": err})
                return

        await task.emit("step", {
            "step": "bootstrap",
            "title": "Pre-Flight System Check",
            "status": "completed",
            "message": "PostgreSQL and Ollama services are online and ready."
        })

        # Step 2: Idempotency / Deduplication Check
        await task.emit("step", {
            "step": "dedup",
            "title": "Checking Database Cache",
            "status": "in_progress",
            "message": f"Checking existing records for {company} ({job_id})..."
        })

        existing = None
        try:
            existing = get_existing_application(company=company, job_id=job_id)
        except Exception as e:
            # PostgreSQL error during dedup check is non-fatal if user allowed skip_bootstrap
            pass

        if existing and not force:
            await task.emit("step", {
                "step": "dedup",
                "title": "Cached Record Found",
                "status": "completed",
                "is_cached": True,
                "record": existing,
                "message": f"Cached run exists for {company} ({job_id}). Use 'Force Re-run' to overwrite."
            })
            task.status = "CACHED"
            task.final_result = existing
            await task.emit("cached", {"record": existing})
            return

        await task.emit("step", {
            "step": "dedup",
            "title": "Database Verification",
            "status": "completed",
            "is_cached": False,
            "message": "Proceeding with fresh modular section-by-section optimization."
        })

        # Step 3: Ingestion
        await task.emit("step", {
            "step": "ingestion",
            "title": "Parsing Ingested Content",
            "status": "in_progress",
            "message": "Parsing base resume and extracting job description..."
        })

        job_description = ""
        if url and url.strip():
            scraper = JDScraper()
            try:
                job_description = await asyncio.to_thread(scraper.scrape, url.strip())
            except Exception as e:
                err = f"Failed to scrape job URL: {str(e)}"
                await task.emit("step", {"step": "ingestion", "status": "failed", "error": err})
                task.status = "FAILED"
                await task.emit("error", {"error": err})
                return
        elif jd_text and jd_text.strip():
            job_description = jd_text.strip()
        else:
            err = "Job description is missing. Provide a URL or text."
            await task.emit("step", {"step": "ingestion", "status": "failed", "error": err})
            task.status = "FAILED"
            await task.emit("error", {"error": err})
            return

        resume_path = Path(source_resume_path)
        if not resume_path.exists():
            err = f"Source resume file not found at {source_resume_path}"
            await task.emit("step", {"step": "ingestion", "status": "failed", "error": err})
            task.status = "FAILED"
            await task.emit("error", {"error": err})
            return

        parser = ResumeParser()
        try:
            raw_resume_text = await asyncio.to_thread(parser.parse, resume_path)
        except Exception as e:
            err = f"Failed to parse resume: {str(e)}"
            await task.emit("step", {"step": "ingestion", "status": "failed", "error": err})
            task.status = "FAILED"
            await task.emit("error", {"error": err})
            return

        await task.emit("step", {
            "step": "ingestion",
            "title": "Content Ingested",
            "status": "completed",
            "message": f"Resume parsed ({len(raw_resume_text)} chars). JD loaded ({len(job_description)} chars)."
        })

        # Step 4: State Initialization
        auxiliary_instructions = (task.payload.get("auxiliary_instructions") or "").strip()
        recruiter_instructions = (task.payload.get("recruiter_instructions") or "").strip()
        rewriter_instructions = (task.payload.get("rewriter_instructions") or "").strip()
        referral_instructions = (task.payload.get("referral_instructions") or "").strip()
        word_limit_param = task.payload.get("word_limit")
        active_word_limit = int(word_limit_param) if word_limit_param is not None else settings.WORD_LIMIT

        initial_state: AgentState = {
            "company": company,
            "job_id": job_id,
            "role": role,
            "job_url": url,
            "job_description": job_description,
            "raw_resume_text": raw_resume_text,
            "candidate_header": "",
            "parsed_sections": [],
            "auxiliary_instructions": auxiliary_instructions or None,
            "recruiter_instructions": recruiter_instructions or None,
            "rewriter_instructions": rewriter_instructions or None,
            "referral_instructions": referral_instructions or None,
            "current_section_idx": 0,
            "processed_sections": [],
            "final_resume": "",
            "word_limit": active_word_limit,
            "observer_action": None,
            "section_directives": [],
            "match_tier": "Pending",
            "strengths": [],
            "gaps": [],
            "recruiter_verdict": "",
            "referral_message": None,
            "source_resume_path": str(resume_path.resolve()),
            "saved_file_path": None,
            "status": "PROCESSING"
        }

        # Step 5: Streaming LangGraph Execution
        workflow = build_workflow()
        final_state = dict(initial_state)

        def node_stream_generator():
            for ev in workflow.stream(initial_state):
                yield ev

        iterator = node_stream_generator()

        while True:
            try:
                event = await asyncio.to_thread(lambda: next(iterator, None))
                if event is None:
                    break

                for node_name, node_output in event.items():
                    final_state.update(node_output)

                    if node_name == "extractor":
                        sections = node_output.get("parsed_sections", [])
                        sections_summary = [
                            {"title": s.get("title", ""), "section_type": s.get("section_type", "other")}
                            for s in sections
                        ]
                        await task.emit("step", {
                            "step": "extractor",
                            "title": "Resume Layout Normalization & Extraction",
                            "status": "completed",
                            "data": {
                                "total_sections": len(sections),
                                "sections": sections_summary,
                                "candidate_header": node_output.get("candidate_header", "")
                            }
                        })

                    elif node_name == "observer":
                        action = node_output.get("observer_action", "KEEP_AS_IS")
                        idx = final_state.get("current_section_idx", 0)
                        sections = final_state.get("parsed_sections", [])
                        sec = sections[idx] if idx < len(sections) else {"title": f"Section {idx + 1}", "section_type": "other"}
                        directives = node_output.get("section_directives", [])
                        
                        await task.emit("step", {
                            "step": "observer",
                            "title": f"Observer Audit: {sec.get('title', 'Section')}",
                            "status": "completed",
                            "data": {
                                "section_index": idx,
                                "total_sections": len(sections),
                                "section_title": sec.get("title", ""),
                                "section_type": sec.get("section_type", "other"),
                                "action": action,
                                "directives": directives
                            }
                        })

                    elif node_name == "rewriter":
                        idx = max(0, final_state.get("current_section_idx", 1) - 1)
                        sections = final_state.get("parsed_sections", [])
                        sec = sections[idx] if idx < len(sections) else {"title": f"Section {idx + 1}"}
                        
                        await task.emit("step", {
                            "step": "rewriter",
                            "title": f"Section Re-writer: {sec.get('title', 'Section')}",
                            "status": "completed",
                            "data": {
                                "section_index": idx,
                                "total_sections": len(sections),
                                "section_title": sec.get("title", ""),
                                "processed_count": len(final_state.get("processed_sections", []))
                            }
                        })

                    elif node_name == "advance_section":
                        pass  # Section advance handled cleanly without UI clutter

                    elif node_name == "stitcher":
                        surviving = len(final_state.get("processed_sections", []))
                        total = len(final_state.get("parsed_sections", []))
                        await task.emit("step", {
                            "step": "stitcher",
                            "title": "Resume Reassembly & Stitching",
                            "status": "completed",
                            "data": {
                                "surviving_count": surviving,
                                "total_count": total
                            }
                        })

                    elif node_name == "matcher":
                        tier = node_output.get("match_tier", "Low Match")
                        await task.emit("step", {
                            "step": "matcher",
                            "title": "Recruiter-Matcher Holistic Evaluation",
                            "status": "completed",
                            "data": {
                                "match_tier": tier,
                                "recruiter_verdict": node_output.get("recruiter_verdict", ""),
                                "strengths": node_output.get("strengths", [])[:5],
                                "gaps": node_output.get("gaps", [])[:5]
                            }
                        })

                    elif node_name == "referral":
                        await task.emit("step", {
                            "step": "referral",
                            "title": "Targeted Referral Note Generator",
                            "status": "completed",
                            "data": {
                                "referral_message": node_output.get("referral_message")
                            }
                        })

                    elif node_name == "save_artifacts":
                        await task.emit("step", {
                            "step": "save_artifacts",
                            "title": "Final Resume Exported",
                            "status": "completed",
                            "data": {
                                "saved_file_path": node_output.get("saved_file_path"),
                                "status": node_output.get("status")
                            }
                        })

            except StopIteration:
                break
            except Exception as e:
                err = f"Pipeline execution error: {str(e)}"
                await task.emit("error", {"error": err})
                task.status = "FAILED"
                return

        # Step 6: Save to PostgreSQL
        final_state["source_resume_path"] = str(resume_path.resolve())
        try:
            save_application_state(final_state)
            await task.emit("step", {
                "step": "persistence",
                "title": "PostgreSQL Record Saved",
                "status": "completed",
                "message": "Persisted tailored resume, audit verdicts, and match tier to database."
            })
        except Exception as e:
            await task.emit("step", {
                "step": "persistence",
                "title": "PostgreSQL Persistence Notice",
                "status": "warning",
                "message": f"Database save warning: {str(e)}"
            })

        task.status = "COMPLETED"
        task.final_result = final_state
        await task.emit("complete", {
            "result": {
                "company": final_state["company"],
                "job_id": final_state["job_id"],
                "role": final_state["role"],
                "match_tier": final_state.get("match_tier"),
                "status": final_state.get("status"),
                "saved_file_path": final_state.get("saved_file_path"),
                "source_resume_path": final_state.get("source_resume_path"),
                "recruiter_verdict": final_state.get("recruiter_verdict"),
                "referral_message": final_state.get("referral_message")
            }
        })

    except Exception as e:
        task.status = "FAILED"
        task.error_message = str(e)
        await task.emit("error", {"error": str(e)})


def create_pipeline_task(payload: Dict[str, Any]) -> PipelineTask:
    task_id = str(uuid.uuid4())
    task = PipelineTask(task_id, payload)
    active_tasks[task_id] = task
    asyncio.create_task(run_pipeline_job(task))
    return task
