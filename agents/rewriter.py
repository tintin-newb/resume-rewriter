from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
try:
    from config.action_verbs import get_formatted_action_verbs_prompt
except ImportError:
    from config.actions_verbs import get_formatted_action_verbs_prompt
from agents.state import AgentState


class RewriterResult(BaseModel):
    rewritten_resume_markdown: str = Field(
        ...,
        description="The complete, finalized rewritten resume in clean, professional Markdown."
    )
    modifications_made: List[str] = Field(
        ...,
        description="Key changes made to elevate candidate bullet points into organic impact statements."
    )


REWRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Executive Tech Resume Strategist.
Optimize the candidate's EXISTING resume to match the target Job Description (JD).

1. IMPACT-DRIVEN BULLET POINTS (GOOGLE "XYZ" PHILOSOPHY):
   - Format: [Action Verb] + [Technical Scope/Action] + [Quantified Outcome/Impact].
   - FORBIDDEN: NEVER literally write the words "as measured by", "Accomplished [X]", or "by doing [Z]".
   - Bullets must read naturally, convincingly, and professionally.

2. STRICT PROHIBITION ON METRIC CROSS-CONTAMINATION:
   - NEVER transfer metrics from academic projects to professional jobs. Metrics belong strictly to the job or project where they occurred.

3. FIDELITY & IDENTITY CONSTRAINTS:
   - Retain exact candidate name, email, phone, links, company names, institutions, and dates.
   - ZERO HALLUCINATION: Rephrase existing accomplishments to emphasize transferable elements, but NEVER invent new roles, tools, or fake metrics.

4. ACTION VERBS:
   - Anchor bullets with strong active verbs chosen from the appropriate category in the provided catalog.

CRITICAL - USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}

PRIORITY DIRECTIVE:
If user auxiliary instructions are provided above, they take ABSOLUTE PRECEDENCE and HIGHEST PRIORITY over standard resume tailoring guidelines, action verb rules, or structural constraints whenever a conflict arises. Always honor the user's specific guidance (e.g. emphasis, tone, omissions, or highlighting specific achievements)."""),
    ("user", """--- TARGET JOB DESCRIPTION ---
{job_description}

--- RECRUITER AUDIT FEEDBACK ---
Current Match Tier: {match_tier}
Gaps:
{gaps}

Suggestions:
{suggestions}

--- CATEGORIZED ACTION VERBS ---
{action_verbs_by_category}

--- BASE CANDIDATE RESUME ---
{current_resume}

Rewrite the complete resume in Markdown now.""")
])


def rewriter_node(state: AgentState) -> Dict[str, Any]:
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.1,
        num_ctx=8192,
        num_predict=4096
    ).with_structured_output(RewriterResult)

    rewriter_inst = (state.get("rewriter_instructions") or "").strip()
    general_inst = (state.get("auxiliary_instructions") or "").strip()

    if rewriter_inst and general_inst:
        aux_instructions = f"[Specific Re-writer Instructions - Top Priority]:\n{rewriter_inst}\n\n[General Guidance]:\n{general_inst}"
    elif rewriter_inst:
        aux_instructions = rewriter_inst
    elif general_inst:
        aux_instructions = general_inst
    else:
        aux_instructions = "None provided. Apply standard tailoring guidelines."

    chain = REWRITER_PROMPT | llm
    result: RewriterResult = chain.invoke({
        "job_description": state["job_description"],
        "match_tier": state.get("match_tier", "Low Match"),
        "gaps": "\n".join(f"- {g}" for g in state["gaps"]),
        "suggestions": "\n".join(f"- {s}" for s in state["suggestions"]),
        "action_verbs_by_category": get_formatted_action_verbs_prompt(),
        "auxiliary_instructions": aux_instructions,
        "current_resume": state["current_resume"]
    })

    return {
        "current_resume": result.rewritten_resume_markdown,
        "modifications_made": result.modifications_made,
        "iteration": state["iteration"] + 1
    }