# agents/recruiter.py
from typing import List, Dict, Any
from pydantic import BaseModel, Field, field_validator
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
        description="Choose strictly one: 'Irrelevant', 'Low Match', 'Average Match', 'High Match', or 'Perfect Match'."
    )
    strengths: List[str] = Field(..., description="Genuine matching qualifications present in the resume.")
    gaps: List[str] = Field(..., description="Crucial missing requirements, missing tools, or domain mismatches.")
    suggestions: List[str] = Field(..., description="Directives for the Re-writer to address gaps.")
    is_qualified: bool = Field(
        ...,
        description="True ONLY if match_tier is 'High Match' or 'Perfect Match'. Otherwise False."
    )
    summary: str = Field(..., description="A blunt, faithful 2-3 sentence verdict explaining the assigned tier.")


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
        temperature=settings.RECRUITER_TEMP,
        num_ctx=8192,
        num_predict=4096
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