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
    ("system", """You are an elite, uncompromising Executive Tech Recruiter and ATS Auditor.
Your job is to classify candidate alignment against a Job Description into one of FIVE CATEGORIES.

DO NOT BE POLITE. Grade with cold, realistic hiring-manager objectivity.

THE 5 CATEGORICAL EVALUATION TIERS:
1. "Irrelevant":
   - Candidate is in a completely different domain or discipline.

2. "Low Match":
   - Candidate knows the base programming language (e.g., Python), but their primary daily expertise is in the WRONG subfield.
   - Example: A Computer Vision / Edge AI / DeepStream engineer applying for a Data/ETL developer role that requires daily Pandas/NumPy pipelines and data lake ingestion.
   - Or lacks critical mandatory requirements (e.g., fails required minimum years of experience).

3. "Average Match":
   - Candidate has adjacent or foundational skills, but has substantial gaps in mandatory day-to-day tooling or core deliverables.

4. "High Match":
   - Strong candidate. Possesses 80%+ of mandatory requirements, verified commercial experience with the core tech stack, and clear domain relevance. Minor gaps only.

5. "Perfect Match":
   - Flawless fit. Checks 100% of required and nice-to-have criteria with exact industry background.

CRITICAL INSTRUCTION:
- If a candidate's background is primarily Computer Vision / Edge AI and the JD specifically demands a Data/ETL Developer with heavy Pandas/NumPy and 3-5 years exp, classify as 'Low Match' or 'Average Match'. DO NOT select 'High Match'."""),
    ("user", """--- JOB DESCRIPTION ---
{job_description}

--- CANDIDATE RESUME ---
{current_resume}

Select the exact categorical match_tier and provide the evaluation schema.""")
])


def recruiter_node(state: AgentState) -> Dict[str, Any]:
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.0,
        num_ctx=8192,
        num_predict=2048
    ).with_structured_output(RecruiterVerdict)

    chain = RECRUITER_PROMPT | llm
    verdict: RecruiterVerdict = chain.invoke({
        "job_description": state["job_description"],
        "current_resume": state["current_resume"]
    })

    return {
        "match_tier": verdict.match_tier.value,
        "strengths": verdict.strengths,
        "gaps": verdict.gaps,
        "suggestions": verdict.suggestions,
        "is_qualified": verdict.is_qualified,
        "recruiter_verdict": f"[{verdict.match_tier.value.upper()}] {verdict.summary}"
    }