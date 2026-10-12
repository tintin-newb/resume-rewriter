# agents/rewriter.py
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from config.action_verbs import get_formatted_action_verbs_prompt
from agents.state import AgentState


class RewriterResult(BaseModel):
    rewritten_resume_markdown: str = Field(..., description="Rewritten resume in clean Markdown.")
    modifications_made: List[str] = Field(..., description="Changes applied.")
    categories_leveraged: List[str] = Field(..., description="Action verb categories utilized.")


REWRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Executive Resume Strategist.
Rewrite the candidate's resume to address the Recruiter audit feedback and align with the JD.

CRITICAL INSTRUCTIONS FOR ACTION VERBS:
1. You are provided with ACTION VERBS CLASSIFIED BY FUNCTIONAL CATEGORY.
2. CONTEXT-MATCH VERBS TO BULLETS:
   - For leadership, ownership, or team coordination bullets: use [LEADERSHIP & MANAGEMENT].
   - For architecture, coding, and systems: use [TECHNICAL & ENGINEERING].
   - For measurable outcomes and results: use [ACCOMPLISHMENTS & HIGH IMPACT].
   - For data analysis, metrics, and investigation: use [RESEARCH & INVESTIGATION].
   - For cross-functional collaboration: use [COMMUNICATION & COLLABORATION].
3. ZERO HALLUCINATION: Rephrase and elevate existing experience, but NEVER invent new roles, tools, metrics, or technologies."""),
    ("user", """--- TARGET JOB DESCRIPTION ---
{job_description}

--- RECRUITER AUDIT FEEDBACK ---
Score: {match_score}/10.0
Gaps:
{gaps}

Suggestions:
{suggestions}

--- CATEGORIZED ACTION VERBS ---
{action_verbs_by_category}

--- CURRENT RESUME ---
{current_resume}

Rewrite the resume in Markdown, selecting verbs appropriate to each bullet point's functional context.""")
])


def rewriter_node(state: AgentState) -> Dict[str, Any]:
    """Rewrites the resume using in-memory categorized action verbs."""
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.2
    ).with_structured_output(RewriterResult)

    chain = REWRITER_PROMPT | llm
    result: RewriterResult = chain.invoke({
        "job_description": state["job_description"],
        "match_score": state["match_score"],
        "gaps": "\n".join(f"- {g}" for g in state["gaps"]),
        "suggestions": "\n".join(f"- {s}" for s in state["suggestions"]),
        "action_verbs_by_category": get_formatted_action_verbs_prompt(),
        "current_resume": state["current_resume"]
    })

    return {
        "current_resume": result.rewritten_resume_markdown,
        "modifications_made": result.modifications_made,
        "iteration": state["iteration"] + 1
    }