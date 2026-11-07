# agents/stitcher.py
from typing import Dict, Any
from agents.state import AgentState


def advance_section_node(state: AgentState) -> Dict[str, Any]:
    """
    Called when a section is either DROPPED or KEPT_AS_IS:
    - If KEEP_AS_IS: appends the unedited original content to processed_sections.
    - If DROP: simply discards it (does not append).
    - Increments current_section_idx.
    """
    current_idx = state.get("current_section_idx", 0)
    sections = state.get("parsed_sections", [])
    action = state.get("observer_action", "KEEP_AS_IS")

    updated_processed = list(state.get("processed_sections", []))

    if current_idx < len(sections):
        target_section = sections[current_idx]
        if action == "KEEP_AS_IS":
            updated_processed.append(target_section)
        # If action == "DROP", it is deliberately omitted

    return {
        "processed_sections": updated_processed,
        "current_section_idx": current_idx + 1
    }


def stitcher_node(state: AgentState) -> Dict[str, Any]:
    """
    Deterministically concatenates the candidate header and all surviving
    processed sections into the final Markdown resume. Zero LLM involvement.
    """
    header = state.get("candidate_header", "").strip()
    processed = state.get("processed_sections", [])

    section_blocks = []
    for sec in processed:
        title = sec.get("title", "").strip()
        content = sec.get("content", "").strip()
        if content:
            section_blocks.append(f"### {title}\n{content}")

    # Assemble complete markdown with standardized dividers
    final_resume_md = header + "\n\n---\n\n" + "\n\n---\n\n".join(section_blocks)

    return {
        "final_resume": final_resume_md,
        "current_resume": final_resume_md
    }