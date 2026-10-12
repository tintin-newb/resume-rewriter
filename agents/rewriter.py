# agents/rewriter.py
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from config.action_verbs import get_formatted_action_verbs_prompt
from agents.state import AgentState


class RewriterResult(BaseModel):
    rewritten_resume_markdown: str = Field(
        ..., 
        description="The complete, finalized rewritten resume in clean, professional Markdown."
    )
    modifications_made: List[str] = Field(..., description="Key changes made to improve alignment.")
    action_verbs_applied: List[str] = Field(..., description="Action verbs integrated from the catalog.")


REWRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Executive Resume Strategist.
Rewrite the candidate's resume to address the Recruiter audit feedback and align with the JD.

CRITICAL RULES:
1. ZERO HALLUCINATION: Rephrase and elevate existing experience, but NEVER invent new roles, tools, metrics, or technologies.
2. ACTION VERBS: Start every single accomplishment bullet point with an active verb from the provided categorized catalog.
3. STRICT MARKDOWN FORMATTING:
   - Output must be publication-grade Markdown.
   - Use `# Candidate Name` for header, followed by contact details separated by pipes (`|`).
   - Use `## Section Title` for major sections (e.g., `## Professional Summary`, `## Work Experience`, `## Technical Skills`, `## Education`, `## Projects`).
   - For job roles, use `### Role Title | Company Name | Location` and a clean date block.
   - Every accomplishment must use standard markdown dashes (`- `), NEVER raw unicode bullets (`•`, `◦`).
   - Fix all squished text artifacts (e.g., separate dates and company names with proper spacing)."""),
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

Rewrite the complete resume in professional Markdown now.""")
])


def rewriter_node(state: AgentState) -> Dict[str, Any]:
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