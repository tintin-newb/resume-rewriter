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
    modifications_made: List[str] = Field(
        ...,
        description="Key changes made to elevate candidate bullet points into organic impact statements."
    )


REWRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Executive Tech Resume Strategist.
Optimize the candidate's EXISTING resume to match the target Job Description (JD).

1. IMPACT-DRIVEN BULLET POINTS (THE GOOGLE "XYZ" PHILOSOPHY):
   - Every accomplishment must follow the spirit of Google's XYZ formula: [Action Verb] + [Technical Scope/Action] + [Quantified Outcome/Impact].
   - FORBIDDEN PHRASING: NEVER literally write the words "as measured by", "Accomplished [X]", or "by doing [Z]". That is an internal framework, NOT visible resume text.
   - Bullets must read naturally and professionally.
   * POOR (Robotic): "Accomplished stream orchestration, as measured by 80% reduction, by architecting a load balancer."
   * EXCELLENT (Organic): "Reduced manual stream orchestration by 80% and ensured 100% database-to-node consistency by architecting a distributed NVIDIA DeepStream load balancer with automated failover."
   * EXCELLENT (Organic): "Boosted traffic violation detection accuracy by 15% and accelerated inference throughput 10× by fine-tuning Qwen2-VL-7B using LoRA and optimizing vLLM deployment."

2. STRICT PROHIBITION ON METRIC CROSS-CONTAMINATION:
   - NEVER steal metrics from academic projects to insert into professional work experience (e.g., do NOT attach UCF-101 or ROUGE scores to Griffyn Robotech or Sabre Corp).
   - Metrics belong strictly to the job or project where they originally occurred.

3. CANDIDATE IDENTITY & INSTITUTION INTEGRITY:
   - CANDIDATE NAME: Retain the exact candidate name, email, phone, and links from the base resume.
   - Retain exact company names, locations, degree titles, and dates.

4. CATEGORIZED ACTION VERBS:
   - Anchor bullet points with strong active verbs chosen from the appropriate category in the provided catalog.

5. OUTPUT FORMAT:
   - Complete, publication-grade Markdown from top to bottom. Do NOT abbreviate."""),
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

Rewrite the complete resume in Markdown now. Ensure bullets flow naturally with organic impact (NO "as measured by" phrasing).""")
])


def rewriter_node(state: AgentState) -> Dict[str, Any]:
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=settings.REWRITER_TEMP,
        num_ctx=8192,
        num_predict=4096
    ).with_structured_output(RewriterResult)

    chain = REWRITER_PROMPT | llm
    result: RewriterResult = chain.invoke({
        "job_description": state["job_description"],
        "match_tier": state.get("match_tier", "Low Match"),  # <-- String enum
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