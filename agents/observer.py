# agents/observer.py
import json
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.exceptions import OutputParserException
from rich.console import Console
from config.settings import settings
from agents.state import AgentState

console = Console()


class SectionAction(str, Enum):
    DROP = "DROP"                # Completely delete this entire section
    KEEP_AS_IS = "KEEP_AS_IS"    # Section is already crisp/static; pass through untouched
    REVISE = "REVISE"            # Re-writer should optimize this section


class SectionAuditVerdict(BaseModel):
    action: SectionAction = Field(
        ...,
        description="Select strictly one action: 'DROP' (remove section entirely), 'KEEP_AS_IS' (pass through unchanged), or 'REVISE' (reorder/prune/reword)."
    )
    reasoning: str = Field(
        ...,
        description="A blunt, 1-2 sentence justification for this decision based on JD relevance and signal-to-noise ratio."
    )
    bullets_to_drop: List[str] = Field(
        default_factory=list,
        description="Specific bullet points inside this section to delete completely (if action is REVISE). Empty if KEEP_AS_IS or DROP."
    )
    reorder_priorities: List[str] = Field(
        default_factory=list,
        description="Specific bullet points that must be placed as #1 and #2 in this section to capture attention in 6 seconds (if action is REVISE)."
    )
    rewording_directives: List[str] = Field(
        default_factory=list,
        description="Pointers on rewording bullets using stronger action verbs, quantified scale, or translating transferable engineering (if action is REVISE)."
    )


OBSERVER_SYSTEM_PROMPT = """You are a strict recruiting manager conducting a section-by-section audit of a resume for a specific Job Description (JD).
You are evaluating ONLY ONE specific section of the resume right now.

YOUR DECISION FRAMEWORK:

1. WHEN TO CHOOSE `DROP` (PURGE ENTIRE SECTION):
   - Non-Technical / University Filler: Sections like "Position of Responsibility" (e.g., student companion, club lead, fresher mentoring) or general student duties dilute senior engineering credibility. DROP THEM.
   - Irrelevant Academic Projects: If a project shares ZERO tooling, architecture, or domain relevance with the JD (e.g., industrial drawing digitization for an enterprise LLM/Agentic role), DROP IT.
   - Outdated / Low-Signal Achievements: If an achievement section consists only of ancient undergraduate coding contests (e.g., >3-4 years old) or basic online certificates (e.g., introductory NPTEL), DROP IT.

2. WHEN TO CHOOSE `KEEP_AS_IS`:
   - Standard, dense credentials that require no rewording (e.g., standard "EDUCATION" section with degrees, GPAs, and institutions).
   - Any section that is already high-impact, concise, and requires no edits.

3. WHEN TO CHOOSE `REVISE`:
   - Work Experience or Projects that contain high-value, transferable technical experience, but need:
     * Specific weak/passive bullets pruned (`bullets_to_drop`).
     * The most JD-relevant achievements promoted to the top 2 bullets (`reorder_priorities`).
     * Technical rewording to highlight system complexity, scale, and active verbs (`rewording_directives`).

CRITICAL RULES:
- If action is `DROP`, `bullets_to_drop`, `reorder_priorities`, and `rewording_directives` should be empty.
- NEVER suggest adding tools or frameworks that do not exist in this section.
- Be decisive. If a section does not help the candidate get shortlisted for THIS specific JD, DROP it.

USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY):
{auxiliary_instructions}"""

OBSERVER_USER_PROMPT = """--- TARGET JOB DESCRIPTION ---
{job_description}

--- CURRENT SECTION BEING AUDITED ---
Section Title: {section_title}
Section Type: {section_type}

Content:
{section_content}

Audit this section against the JD. Output the SectionAuditVerdict schema now."""


def observer_node(state: AgentState) -> Dict[str, Any]:
    """
    Audits the current section pointed to by state['current_section_idx'].
    Decides whether to DROP, KEEP_AS_IS, or REVISE the section.
    Uses adaptive num_predict (1024 -> 2048 -> 4096) across 2 re-attempts
    if output parsing fails.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", OBSERVER_SYSTEM_PROMPT),
        ("user", OBSERVER_USER_PROMPT),
    ])

    current_idx = state.get("current_section_idx", 0)
    sections = state.get("parsed_sections", [])

    if not sections or current_idx >= len(sections):
        # Boundary safety: No sections left to process
        return {
            "observer_action": "KEEP_AS_IS",
            "section_directives": []
        }

    target_section = sections[current_idx]

    # Assemble user guidance overrides
    recruiter_inst = (state.get("recruiter_instructions") or "").strip()
    general_inst = (state.get("auxiliary_instructions") or "").strip()
    if recruiter_inst and general_inst:
        aux_text = f"{recruiter_inst}\n{general_inst}"
    elif recruiter_inst:
        aux_text = recruiter_inst
    elif general_inst:
        aux_text = general_inst
    else:
        aux_text = "None provided. Apply standard strict 6-second scan pruning."

    predict_sequence = [1024, 2048, 4096]
    verdict: Optional[SectionAuditVerdict] = None
    last_exception: Optional[Exception] = None

    for attempt, predict_tokens in enumerate(predict_sequence):
        num_ctx = max(4096, predict_tokens * 2)
        llm = ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,
            num_ctx=num_ctx,
            num_predict=predict_tokens,
            reasoning=settings.reasoning,
        ).with_structured_output(SectionAuditVerdict)

        chain = prompt | llm

        try:
            verdict = chain.invoke({
                "job_description": state["job_description"],
                "section_title": target_section.get("title", ""),
                "section_type": target_section.get("section_type", "other"),
                "section_content": target_section.get("content", ""),
                "auxiliary_instructions": aux_text,
            })
            if verdict is not None:
                break
        except (OutputParserException, json.JSONDecodeError, ValueError) as exc:
            last_exception = exc
            if attempt < len(predict_sequence) - 1:
                next_tokens = predict_sequence[attempt + 1]
                console.print(
                    f"  [yellow]⚠ Observer parsing failed at num_predict={predict_tokens} on '{target_section.get('title', 'section')}'. "
                    f"Doubling to num_predict={next_tokens} (re-attempt {attempt + 1}/2)...[/yellow]"
                )
            else:
                console.print(
                    f"  [red]✗ All 2 re-attempts failed up to num_predict={predict_tokens} on '{target_section.get('title', 'section')}'.[/red]"
                )
                raise last_exception

    if verdict is None:
        if last_exception is not None:
            raise last_exception
        return {
            "observer_action": "KEEP_AS_IS",
            "section_directives": []
        }

    # Assemble concrete directives for this section
    directives: List[str] = []
    if verdict.action == SectionAction.REVISE:
        if verdict.bullets_to_drop:
            directives.append("PRUNE BULLETS:\n" + "\n".join(f"  - [DELETE]: {b}" for b in verdict.bullets_to_drop))
        if verdict.reorder_priorities:
            directives.append("REORDER BULLETS:\n" + "\n".join(f"  - [MOVE TO TOP]: {r}" for r in verdict.reorder_priorities))
        if verdict.rewording_directives:
            directives.append("REWORDING:\n" + "\n".join(f"  - {w}" for w in verdict.rewording_directives))
    elif verdict.action == SectionAction.KEEP_AS_IS:
        directives.append("SECTION ACTION: KEEP_AS_IS")
        if verdict.reasoning:
            directives.append(f"REASONING: {verdict.reasoning}")
        directives.append("INSPECTION DIRECTIVE: Verify all pointers against the word limit constraint. Rephrase any pointer that exceeds the word limit or can be made more impactful while preserving factual fidelity.")

    return {
        "observer_action": verdict.action.value,
        "section_directives": directives
    }