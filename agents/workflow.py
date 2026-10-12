# agents/workflow.py
import re
from pathlib import Path
from typing import Literal, Dict, Any
from langgraph.graph import StateGraph, END
from rich.console import Console

from config.settings import settings
from agents.state import AgentState
from agents.recruiter import recruiter_node
from agents.rewriter import rewriter_node
from agents.referral import referral_node

console = Console()


def save_artifacts_node(state: AgentState) -> Dict[str, Any]:
    """Saves the final rewritten resume to the output directory."""
    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_company = re.sub(r"[^\w\-_\.]", "_", state["company"]).strip()
    safe_job_id = re.sub(r"[^\w\-_\.]", "_", state["job_id"]).strip()

    file_path = settings.OUTPUT_DIR / f"{safe_company}_{safe_job_id}_resume.md"
    file_path.write_text(state["current_resume"], encoding="utf-8")

    status = "MATCHED" if state["match_score"] >= state["min_match_score"] else "MAX_LOOPS_EXCEEDED"
    return {
        "saved_file_path": str(file_path.resolve()),
        "status": status
    }


def should_continue(state: AgentState) -> Literal["referral", "save_artifacts", "rewriter"]:
    """Conditional router based on match score and loop counters."""
    score = state["match_score"]
    threshold = state["min_match_score"]
    iteration = state["iteration"]
    max_loops = state["max_loops"]

    console.print(f"[bold magenta]▶ Iteration {iteration}: Recruiter Score = {score}/10.0 (Threshold: {threshold})[/bold magenta]")

    if score >= threshold:
        console.print("[bold green]✓ Score threshold met! Proceeding to Referral Generator...[/bold green]")
        return "referral"

    if iteration >= max_loops:
        console.print(f"[bold yellow]! Max loops ({max_loops}) reached without hitting threshold.[/bold yellow]")
        return "save_artifacts"

    console.print("[cyan]→ Passing suggestions to Re-writer agent...[/cyan]")
    return "rewriter"


def build_workflow():
    """Builds and compiles the LangGraph resume rewrite workflow."""
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("recruiter", recruiter_node)
    graph.add_node("rewriter", rewriter_node)
    graph.add_node("referral", referral_node)
    graph.add_node("save_artifacts", save_artifacts_node)

    # Define edges
    graph.set_entry_point("recruiter")

    graph.add_conditional_edges(
        "recruiter",
        should_continue,
        {
            "referral": "referral",
            "save_artifacts": "save_artifacts",
            "rewriter": "rewriter"
        }
    )

    graph.add_edge("rewriter", "recruiter")
    graph.add_edge("referral", "save_artifacts")
    graph.add_edge("save_artifacts", END)

    return graph.compile()