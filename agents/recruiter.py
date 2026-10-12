# agents/recruiter.py
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from agents.state import AgentState


class RecruiterVerdict(BaseModel):
    match_score: float = Field(..., description="Score 1.0 to 10.0 indicating JD alignment.")
    strengths: List[str] = Field(..., description="Verified matching qualifications in resume.")
    gaps: List[str] = Field(..., description="Missing or weak qualifications compared to JD.")
    suggestions: List[str] = Field(..., description="Actionable rewording, prioritization, and pruning tips.")
    is_qualified: bool = Field(..., description="Whether candidate fundamentally qualifies.")
    summary: str = Field(..., description="Direct 2-3 sentence verdict.")


RECRUITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an uncompromising Executive Tech Recruiter and ATS Auditor.
Evaluate the candidate's resume strictly against the Job Description (JD).
DO NOT assume skills not explicitly documented. Produce a blunt and faithful assessment."""),
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