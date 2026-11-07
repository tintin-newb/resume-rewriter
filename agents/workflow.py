import re
from pathlib import Path
from typing import Literal, Dict, Any
from langgraph.graph import StateGraph, END
from rich.console import Console

from config.settings import settings
from agents.state import AgentState
from agents.extractor import extractor_node
from agents.observer import observer_node
from agents.rewriter import rewriter_node
from agents.stitcher import advance_section_node, stitcher_node
from agents.matcher import matcher_node
from agents.referral import referral_node

console = Console()


def save_artifacts_node(state: AgentState) -> Dict[str, Any]:
    """Saves the final stitched resume to disk."""
    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_company = re.sub(r"[^\w\-_\.]", "_", state["company"]).strip()
    safe_job_id = re.sub(r"[^\w\-_\.]", "_", state["job_id"]).strip()

    file_path = settings.OUTPUT_DIR / f"{safe_company}_{safe_job_id}_resume.md"
    resume_content = state.get("final_resume") or state.get("current_resume") or ""
    file_path.write_text(resume_content, encoding="utf-8")

    status = "MATCHED" if state.get("match_tier") in ["High Match", "Perfect Match"] else "REVIEW_COMPLETE"
    return {
        "saved_file_path": str(file_path.resolve()),
        "status": status
    }


def route_section_action(state: AgentState) -> Literal["rewriter", "advance_section"]:
    """Routes based on the Recruiter-Observer's section verdict."""
    action = state.get("observer_action", "KEEP_AS_IS")
    if action == "REVISE":
        return "rewriter"
    return "advance_section"


def route_section_loop(state: AgentState) -> Literal["observer", "stitcher"]:
    """Checks whether more sections remain to be processed."""
    current_idx = state.get("current_section_idx", 0)
    total_sections = len(state.get("parsed_sections", []))

    if current_idx < total_sections:
        return "observer"
    return "stitcher"


def route_matcher_verdict(state: AgentState) -> Literal["referral", "save_artifacts"]:
    """Routes based on holistic qualification tier."""
    tier = state.get("match_tier", "Low Match")
    if tier in ["High Match", "Perfect Match"]:
        return "referral"
    return "save_artifacts"


def build_workflow():
    """Builds and compiles the modular section-by-section StateGraph."""
    graph = StateGraph(AgentState)

    # 1. Register Nodes
    graph.add_node("extractor", extractor_node)
    graph.add_node("observer", observer_node)
    graph.add_node("rewriter", rewriter_node)
    graph.add_node("advance_section", advance_section_node)
    graph.add_node("stitcher", stitcher_node)
    graph.add_node("matcher", matcher_node)
    graph.add_node("referral", referral_node)
    graph.add_node("save_artifacts", save_artifacts_node)

    # 2. Define Flow & Transitions
    graph.set_entry_point("extractor")
    graph.add_edge("extractor", "observer")

    # Observer routes to rewriter if REVISE, else to advance_section
    graph.add_conditional_edges(
        "observer",
        route_section_action,
        {
            "rewriter": "rewriter",
            "advance_section": "advance_section"
        }
    )

    # Both rewriter and advance_section check if more sections remain
    graph.add_conditional_edges(
        "rewriter",
        route_section_loop,
        {
            "observer": "observer",
            "stitcher": "stitcher"
        }
    )

    graph.add_conditional_edges(
        "advance_section",
        route_section_loop,
        {
            "observer": "observer",
            "stitcher": "stitcher"
        }
    )

    # Stitcher routes to Matcher
    graph.add_edge("stitcher", "matcher")

    # Matcher routes to Referral if passed, else directly to saving
    graph.add_conditional_edges(
        "matcher",
        route_matcher_verdict,
        {
            "referral": "referral",
            "save_artifacts": "save_artifacts"
        }
    )

    graph.add_edge("referral", "save_artifacts")
    graph.add_edge("save_artifacts", END)

    return graph.compile()