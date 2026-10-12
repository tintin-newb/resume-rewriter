# agents/rewriter.py
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from agents.state import AgentState


class RewriterResult(BaseModel):
    rewritten_resume_markdown: str = Field(..., description="Rewritten resume in clean Markdown.")
    modifications_made: List[str] = Field(..., description="Changes applied.")
    action_verbs_applied: List[str] = Field(..., description="Action verbs from the bank used.")


REWRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Executive Resume Strategist.
Rewrite the resume to address the Recruiter audit feedback and align with the JD.
RULES:
1. ZERO HALLUCINATION: Do NOT invent skills, dates, metrics, or technologies not in the base resume.
2. ACTION VERBS: Start accomplishment bullets with strong action verbs from the provided bank.
3. OUTPUT: Strictly valid Markdown."""),
    ("user", """--- TARGET JOB DESCRIPTION ---
{job_description}

--- RECRUITER AUDIT FEEDBACK ---
Score: {match_score}/10.0
Gaps: {gaps}
Suggestions: {suggestions}

--- ACTION VERBS BANK ---
{action_verbs}

--- CURRENT RESUME ---
{current_resume}

Rewrite the resume now.""")
])


def rewriter_node(state: AgentState) -> Dict[str, Any]:
    """Rewrites the resume using recruiter feedback and action verbs."""
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.2
    ).with_structured_output(RewriterResult)

    verb_sample = ", ".join(state["action_verbs"][:100]) if state["action_verbs"] else "Engineered, Spearheaded, Accelerated"
    
    chain = REWRITER_PROMPT | llm
    result: RewriterResult = chain.invoke({
        "job_description": state["job_description"],
        "match_score": state["match_score"],
        "gaps": "\n".join(f"- {g}" for g in state["gaps"]),
        "suggestions": "\n".join(f"- {s}" for s in state["suggestions"]),
        "action_verbs": verb_sample,
        "current_resume": state["current_resume"]
    })

    return {
        "current_resume": result.rewritten_resume_markdown,
        "modifications_made": result.modifications_made,
        "iteration": state["iteration"] + 1
    }