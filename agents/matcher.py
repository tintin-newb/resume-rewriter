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
    is_qualified: bool = Field(
        ...,
        description="True ONLY if match_tier is 'High Match' or 'Perfect Match'. Otherwise False."
    )
    strengths: List[str] = Field(
        ...,
        description="Top 3-4 genuine matching qualifications and transferable architectural competencies."
    )
    gaps: List[str] = Field(
        ...,
        description="Top 2-3 genuine technical gaps or missing seniority requirements against the JD."
    )
    summary: str = Field(
        ...,
        description="A blunt, realistic 2-3 sentence hiring manager assessment explaining the assigned tier."
    )


MATCHER_SYSTEM_PROMPT = """You are a Principal Technical Recruiter evaluating a finalized, tailored resume against a target Job Description (JD).
Your job is to provide an objective, holistic assessment of whether this candidate should be shortlisted for a technical interview.

EVALUATION TIERS:
1. "Irrelevant":
   - Completely unrelated discipline (e.g., Marketing, Sales, or Graphic Design applying for an ML/SWE role).

2. "Low Match":
   - Lacks core technical foundations and possesses neither the primary tools nor transferable architectural equivalents.
   - Significant experience deficit (commercial experience is less than 50% of the required minimum).

3. "Average Match":
   - The candidate has adjacent technical skills, but has notable gaps in central production deliverables or core toolchains that will require substantial ramp-up.

4. "High Match":
   - Strong candidate. The candidate demonstrates proven mastery of the underlying technical complexity, models, or systems scale demanded by the JD (even if previous applications were in a parallel domain). Meets or closely approaches the seniority requirement. Minor gaps are easily learnable on the job.

5. "Perfect Match":
   - Rare 1:1 Fit: Meets 100% of required and preferred skills with identical domain, stack, and industry experience.

USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}"""

MATCHER_USER_PROMPT = """--- TARGET JOB DESCRIPTION ---
{job_description}

--- FINAL TAILORED CANDIDATE RESUME ---
{final_resume}

Evaluate the candidate's holistic alignment against the JD. Output the FinalMatchVerdict schema now."""


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

    return {
        "match_tier": verdict.match_tier.value,
        "is_qualified": verdict.is_qualified,
        "strengths": verdict.strengths,
        "gaps": verdict.gaps,
        "recruiter_verdict": f"[{verdict.match_tier.value.upper()}] {verdict.summary}"
    }