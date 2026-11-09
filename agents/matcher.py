# agents/matcher.py
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


class FinalMatchVerdict(BaseModel):
    match_tier: MatchTier = Field(
        ...,
        description="Categorical tier based strictly on the evaluation rubric."
    )
    summary: str = Field(
        default="",  # Prevents pipeline crash if model omits the key
        description="A blunt, realistic 2-3 sentence hiring manager assessment explaining the assigned tier."
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Top 3-4 genuine matching qualifications and transferable architectural competencies."
    )
    gaps: List[str] = Field(
        default_factory=list,
        description="Top 2-3 genuine technical gaps or missing seniority requirements against the JD."
    )


MATCHER_SYSTEM_PROMPT = """You are a Principal Technical Recruiter evaluating a finalized, tailored resume against a target Job Description (JD).
Your job is to provide an objective, holistic assessment of whether this candidate should be shortlisted for a technical interview.

EVALUATION TIERS:
1. "Irrelevant": Completely unrelated discipline.
2. "Low Match": Lacks core technical foundations or has a severe experience deficit (e.g. <50% of required years).
3. "Average Match": Transferable skills present, but notable gaps in central production deliverables.
4. "High Match": Proven mastery of underlying technical complexity, models, or systems scale demanded by the JD. Minor gaps are learnable.
5. "Perfect Match": 100% technical and domain match.

CRITICAL INSTRUCTION:
You MUST provide all schema fields: `match_tier`, `summary`, `strengths`, and `gaps`.

USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}"""

MATCHER_USER_PROMPT = """--- TARGET JOB DESCRIPTION ---
{job_description}

--- FINAL TAILORED CANDIDATE RESUME ---
{final_resume}

Evaluate the candidate's holistic alignment against the JD. Output all fields of the FinalMatchVerdict schema now."""


def matcher_node(state: AgentState) -> Dict[str, Any]:
    """
    Evaluates the final stitched resume against the JD to assign the final match tier.
    """
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.0,
        num_ctx=8192,
        num_predict=1536,
        reasoning=settings.reasoning,
    ).with_structured_output(FinalMatchVerdict)

    recruiter_inst = (state.get("recruiter_instructions") or "").strip()
    general_inst = (state.get("auxiliary_instructions") or "").strip()
    if recruiter_inst and general_inst:
        aux_text = f"{recruiter_inst}\n{general_inst}"
    elif recruiter_inst:
        aux_text = recruiter_inst
    elif general_inst:
        aux_text = general_inst
    else:
        aux_text = "None provided. Apply standard strict screening."

    prompt = ChatPromptTemplate.from_messages([
        ("system", MATCHER_SYSTEM_PROMPT),
        ("user", MATCHER_USER_PROMPT),
    ])

    chain = prompt | llm

    resume_text = state.get("final_resume") or state.get("current_resume") or ""

    verdict: FinalMatchVerdict = chain.invoke({
        "job_description": state["job_description"],
        "final_resume": resume_text,
        "auxiliary_instructions": aux_text,
    })

    # Robust fallback: If summary was left blank by the LLM, synthesize one automatically
    final_summary = verdict.summary.strip()
    if not final_summary:
        if verdict.gaps:
            final_summary = f"Candidate evaluated as {verdict.match_tier.value}. Key areas of concern: {'; '.join(verdict.gaps[:2])}."
        else:
            final_summary = f"Candidate demonstrates alignment evaluated at {verdict.match_tier.value} tier."

    return {
        "match_tier": verdict.match_tier.value,
        "strengths": verdict.strengths,
        "gaps": verdict.gaps,
        "recruiter_verdict": f"[{verdict.match_tier.value.upper()}] {final_summary}"
    }