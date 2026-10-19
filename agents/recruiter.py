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
    strengths: List[str] = Field(..., description="Verified matching qualifications present in the resume.")
    gaps: List[str] = Field(..., description="Missing core qualifications, domain gaps, or tool discrepancies.")
    suggestions: List[str] = Field(..., description="Actionable rewording and restructuring guidance for the Re-writer.")
    is_qualified: bool = Field(
        ...,
        description="True ONLY if match_tier is 'High Match' or 'Perfect Match'. Otherwise False."
    )
    summary: str = Field(..., description="A blunt, faithful 2-3 sentence verdict explaining the assigned tier.")


RECRUITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an elite, uncompromising Executive Tech Recruiter and ATS Auditor.
Your job is to objectively evaluate candidate alignment against a Job Description into one of FIVE CATEGORIES.

DO NOT BE POLITE. Grade with cold, realistic hiring-manager objectivity.

EVALUATION TIERS AND CALIBRATION:
1. "Irrelevant":
   - The candidate's discipline or career track is completely unrelated to the role.

2. "Low Match":
   - Domain Misalignment: The candidate has technical skills, but their primary day-to-day specialization is in a distant, non-adjacent engineering or technical subfield with no shared foundational or abstract domain (even if they share common programming languages or generic tools).
   - EXCEPTION FOR ABSTRACT / SPECIALIZED DOMAINS: DO NOT classify as "Low Match" if the required skills or domain knowledge are specialized versions, subfields, or concrete applications of a closely related abstract domain that the candidate already possesses (e.g., General Systems Programming <-> Distributed Storage, Backend Engineering <-> Data Engineering, Machine Learning <-> NLP/LLMs, Cloud Infrastructure <-> Site Reliability/DevOps). Such transferable abstract-to-specialized alignment must be graded as "Average Match" or higher!
   - Core Deficiencies: Fails mandatory minimum requirements such as required years of commercial experience in the primary domain, or lacks the central production stack with no transferable foundational counterpart.

3. "Average Match":
   - The candidate has adjacent or transferable experience, or their background is in a closely related abstract domain where the required skills are specialized versions (or vice versa).
   - While they may exhibit gaps in specific niche tools, specialized production frameworks, or commercial domain nuances, their abstract domain competence provides a strong transferable bridge. Needs tailoring to highlight this domain alignment.

4. "High Match":
   - Strong candidate. Possesses 80%+ of core requirements, verified hands-on commercial experience in the primary domain, and clear relevance. Minor gaps only.

5. "Perfect Match":
   - Rare, exemplary fit. Meets 100% of required and nice-to-have criteria with exact industry and architectural background.

GENERIC CALIBRATION PRINCIPLE:
- Never award 'High Match' or 'Perfect Match' simply because a candidate shares a programming language or generic technical baseline. 
- Distinguish between true domain misalignment versus specialized instances of an abstract domain: If the role requires daily production mastery of a specialized subfield and the candidate has deep experience in the foundational or abstract domain, treat this as transferable experience ("Average Match" or higher), NOT "Low Match". Reserve "Low Match" only for candidates lacking both the specialization and the abstract domain foundations.

CRITICAL - USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}

PRIORITY DIRECTIVE:
If user auxiliary instructions are provided above, they take ABSOLUTE PRECEDENCE and HIGHEST PRIORITY over any default evaluation rules, standard tier thresholds, or calibration principles whenever a conflict arises. Always adhere strictly to the user's explicit guidance."""),
    ("user", """--- JOB DESCRIPTION ---
{job_description}

--- CANDIDATE RESUME ---
{current_resume}

Select the exact categorical match_tier and provide the audit schema now.""")
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
        aux_instructions = "None provided. Apply standard strict evaluation."

    chain = RECRUITER_PROMPT | llm
    verdict: RecruiterVerdict = chain.invoke({
        "job_description": state["job_description"],
        "current_resume": state["current_resume"],
        "auxiliary_instructions": aux_instructions
    })

    return {
        "match_tier": verdict.match_tier.value,
        "strengths": verdict.strengths,
        "gaps": verdict.gaps,
        "suggestions": verdict.suggestions,
        "is_qualified": verdict.is_qualified,
        "recruiter_verdict": f"[{verdict.match_tier.value.upper()}] {verdict.summary}"
    }