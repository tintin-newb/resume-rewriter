from enum import Enum
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from agents.state import AgentState

class MatchTier(str, Enum):
    IRRELEVANT = "Irrelevant"
    LOW_MATCH = "Low Match"
    AVERAGE_MATCH = "Average Match"
    HIGH_MATCH = "High Match"
    PERFECT_MATCH = "Perfect Match"


class RecruiterVerdict(BaseModel):
    match_tier: MatchTier = Field(
        ...,
        description="Categorical tier: 'Irrelevant', 'Low Match', 'Average Match', 'High Match', or 'Perfect Match'."
    )
    is_already_concise: bool = Field(
        ...,
        description="True ONLY if the resume is already punchy, dense, and has zero filler. False if it contains low-signal, peripheral, or bloated items."
    )
    sections_or_bullets_to_drop: List[str] = Field(
        default_factory=list,
        description="Specific low-impact sections, obsolete undergraduate activities, or off-target bullets to DROP completely. Leave empty ONLY if is_already_concise is True."
    )
    reordering_priority: List[str] = Field(
        ...,
        description="Explicit reordering directives: which specific bullets/projects must be moved to rank #1 and #2 within their sections to hook the recruiter in 6 seconds."
    )
    rewording_suggestions: List[str] = Field(
        ...,
        description="Pointers that need stronger action verbs, quantified scale, or technical translation."
    )
    strengths: List[str] = Field(..., description="Verified matching qualifications and transferable architectural competencies.")
    gaps: List[str] = Field(..., description="Genuine technical gaps against mandatory JD requirements.")
    is_qualified: bool = Field(..., description="True ONLY if match_tier is 'High Match' or 'Perfect Match'. Otherwise False.")
    summary: str = Field(..., description="A blunt, faithful 2-3 sentence verdict evaluating transferable technical alignment.")


RECRUITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an elite, uncompromising Principal Tech Recruiter and Systems Architect.
Your job is to evaluate candidate alignment against a Job Description into one of FIVE CATEGORIES, and provide high-impact layout and structural guidance.

1. CORE PHILOSOPHY: ARCHITECTURAL & FUNCTIONAL EQUIVALENCE > EXACT KEYWORD MATCHING
Evaluate based on systems complexity, transferable model serving/inference, and scale rather than superficial keywords.

2. THE "6-SECOND RECRUITER SCAN" (SIGNAL-TO-NOISE AUDIT):
A recruiter spends 6 seconds scanning a resume. Irrelevant or low-impact filler actively damages the candidate by pushing high-value achievements below the fold.

AUDIT FOR DENSITY VS. BLOAT:
- Low-Signal Fillers to Flag for DROPPING:
  * Outdated undergraduate hackathons, intra-college coding competitions, or student clubs.
  * Routine departmental responsibilities (e.g., student companion/freshers onboarding) if applying for mid/senior engineering roles.
  * Secondary academic projects that have zero relevance to the target JD.
  * Passive or redundant bullet points that dilute core achievements.

CONDITIONAL ACTION RULE:
- IF THE RESUME CONTAINS BLOAT (is_already_concise = False):
  * You MUST populate `sections_or_bullets_to_drop` with specific pointers or sections to eliminate entirely.
- IF THE RESUME IS ALREADY CONCISE & DENSE (is_already_concise = True):
  * Set `sections_or_bullets_to_drop` to an empty list.
  * Focus 100% of suggestions on REORDERING and REWORDING.

3. REORDERING & HIERARCHY DIRECTIVES (ALWAYS REQUIRED):
- The first 2 bullet points under EVERY job or project determine whether the candidate gets shortlisted.
- In `reordering_priority`, specify exactly which bullet points must be moved to the TOP of their section because they align most closely with the JD's core technical priorities.

4. EVALUATION TIERS:
- "Irrelevant": Fundamentally disconnected field.
- "Low Match": Lacks core technical depth and underlying architectural foundations.
- "Average Match": Foundational skills present, but significant gaps in core tooling or domain deliverables.
- "High Match": Proven mastery of underlying technical complexity, models, and scale required by JD. Minor gaps only.
- "Perfect Match": 100% technical and domain match.

CRITICAL - USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}

PRIORITY DIRECTIVE:
User instructions take ABSOLUTE PRECEDENCE over standard rules whenever a conflict arises."""),
    ("user", """--- JOB DESCRIPTION ---
{job_description}

--- CANDIDATE RESUME ---
{current_resume}

Audit the resume for architectural equivalence, conciseness, and visual hierarchy. Return the structured audit schema now.""")
])


def recruiter_node(state: AgentState) -> Dict[str, Any]:
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.0,
        num_ctx=8192,
        num_predict=2048
    ).with_structured_output(RecruiterVerdict)

    recruiter_inst = (state.get("recruiter_instructions") or "").strip()
    general_inst = (state.get("auxiliary_instructions") or "").strip()

    if recruiter_inst and general_inst:
        aux_instructions = f"[Specific Recruiter Instructions - Top Priority]:\n{recruiter_inst}\n\n[General Guidance]:\n{general_inst}"
    elif recruiter_inst:
        aux_instructions = recruiter_inst
    elif general_inst:
        aux_instructions = general_inst
    else:
        aux_instructions = "None provided. Enforce strict 6-second scan conciseness and visual prioritization."

    chain = RECRUITER_PROMPT | llm
    verdict: RecruiterVerdict = chain.invoke({
        "job_description": state["job_description"],
        "current_resume": state["current_resume"],
        "auxiliary_instructions": aux_instructions
    })

    # Package structured suggestions into unambiguous directives for the Re-writer
    structured_suggestions: List[str] = []

    if not verdict.is_already_concise and verdict.sections_or_bullets_to_drop:
        structured_suggestions.append(
            "PRUNING DIRECTIVE (DELETE THESE TO INCREASE IMPACT): " + " | ".join(verdict.sections_or_bullets_to_drop)
        )
    else:
        structured_suggestions.append("CONCISENESS DIRECTIVE: Resume is dense. Do not delete core sections; focus on prioritizing and rewording.")

    if verdict.reordering_priority:
        structured_suggestions.append(
            "REORDERING DIRECTIVE (MOVE TO TOP OF SECTIONS): " + " | ".join(verdict.reordering_priority)
        )

    if verdict.rewording_suggestions:
        structured_suggestions.append(
            "REWORDING DIRECTIVE: " + " | ".join(verdict.rewording_suggestions)
        )

    return {
        "match_tier": verdict.match_tier.value,
        "strengths": verdict.strengths,
        "gaps": verdict.gaps,
        "suggestions": structured_suggestions,
        "is_qualified": verdict.is_qualified,
        "recruiter_verdict": f"[{verdict.match_tier.value.upper()}] (Concise: {verdict.is_already_concise}) {verdict.summary}"
    }