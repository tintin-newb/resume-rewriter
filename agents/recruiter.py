# agents/recruiter.py
from typing import List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from agents.state import AgentState


class RecruiterVerdict(BaseModel):
    match_score: float = Field(
        ..., 
        description="A strict numeric score strictly between 1.0 and 10.0. 10.0 is perfect."
    )
    strengths: List[str] = Field(..., description="Verified matching qualifications in resume.")
    gaps: List[str] = Field(..., description="Missing or weak qualifications compared to JD.")
    suggestions: List[str] = Field(..., description="Actionable rewording, prioritization, and pruning tips.")
    is_qualified: bool = Field(..., description="Whether candidate fundamentally qualifies.")
    summary: str = Field(..., description="Direct 2-3 sentence verdict.")

    @field_validator("match_score", mode="before")
    @classmethod
    def normalize_score(cls, v: Any) -> float:
        """Normalizes 0-100 scales to 1.0-10.0 and clamps bounds."""
        try:
            val = float(v)
        except (ValueError, TypeError):
            return 5.0

        # Auto-convert percentage scale (e.g., 65.0 -> 6.5)
        if val > 10.0 and val <= 100.0:
            val = val / 10.0
        elif val > 100.0:
            val = 10.0

        return round(max(1.0, min(10.0, val)), 1)


RECRUITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an uncompromising Executive Tech Recruiter and ATS Auditor.
Evaluate the candidate's resume strictly against the Job Description (JD).

CRITICAL SCORING RULE:
- Your `match_score` MUST be a number between 1.0 and 10.0 (e.g., 5.5, 6.5, 7.8).
- NEVER give a score out of 100. If alignment is 65%, your score MUST be 6.5.
- Be objective and faithful: do not assume skills not explicitly documented."""),
    ("user", """--- JOB DESCRIPTION ---
{job_description}

--- CANDIDATE RESUME ---
{current_resume}

Provide the evaluation schema.""")
])


def recruiter_node(state: AgentState) -> Dict[str, Any]:
    """Evaluates the resume in the current state against the JD."""
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.0
    ).with_structured_output(RecruiterVerdict)

    chain = RECRUITER_PROMPT | llm
    verdict: RecruiterVerdict = chain.invoke({
        "job_description": state["job_description"],
        "current_resume": state["current_resume"]
    })

    return {
        "match_score": verdict.match_score,
        "strengths": verdict.strengths,
        "gaps": verdict.gaps,
        "suggestions": verdict.suggestions,
        "is_qualified": verdict.is_qualified,
        "recruiter_verdict": verdict.summary
    }