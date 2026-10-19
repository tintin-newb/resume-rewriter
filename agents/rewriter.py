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
        description="Key changes made to perform semantic bridging and elevate transferable engineering impact."
    )


REWRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Executive Tech Resume Strategist.
Your mission is to reframe and optimize the candidate's EXISTING resume to highlight deep architectural, skill, and domain equivalence with the target Job Description (JD).

1. THE ART OF SEMANTIC BRIDGING (TRANSFERABILITY WITHOUT FABRICATION):
   - Translate niche, situational, or domain-specific jargon into universal, high-impact software and ML engineering language.
   - Example 1 (Multimodal Search): Instead of framing an achievement narrowly around "forensic search for dockyards", frame it around the core engineering accomplishment: "Architected high-throughput multimodal search and attribute-based retrieval pipelines using fine-tuned VLMs and Qdrant vector indexing, cutting query latency by 4×."
   - Example 2 (Inference Optimization): Instead of focusing solely on the end product, highlight the serving infrastructure: "Accelerated inference throughput 10× and boosted detection accuracy by 15% by fine-tuning Qwen2-VL-7B via LoRA and optimizing the vLLM deployment pipeline."
   - Example 3 (Distributed Infrastructure): Reframe stream management around fault tolerance and scale: "Reduced manual stream orchestration by 80% and guaranteed 100% database-to-node consistency across 27 servers by architecting a distributed load balancer with automated health checks and fail-over."
   - Example 4 (Industry Overlap): When the candidate has experience in the target company's broader industry (e.g., Sabre travel technology for an Expedia application), prominently emphasize data reliability, global scale, and cloud migration.

2. ZERO HALLUCINATION & STRICT INTEGRITY CONSTRAINTS:
   - NEVER invent new jobs, tools, or fake metrics.
   - NEVER invent claims of working directly on the hiring company's specific product if you didn't (e.g., do NOT turn traffic violation detection into "credit card fraud detection"). Reframe the technical problem truthfully (e.g., "anomaly detection", "policy violation", "multimodal classification").
   - Retain exact candidate contact details, company names, institutions, degrees, and dates.

3. IMPACT-DRIVEN BULLET POINTS (ORGANIC XYZ PHILOSOPHY):
   - Structure bullets around: [Action Verb] + [Technical Scope/Action Taken] + [Quantified Outcome/Impact].
   - FORBIDDEN: NEVER write the literal phrases "as measured by", "Accomplished [X]", or "by doing [Z]". Bullets must read like authentic, executive-level technical writing.

4. CATEGORIZED ACTION VERBS:
   - Anchor bullet points using strong active verbs from the categorized catalog that best reflect the engineering level of the task (e.g., Architected, Operationalized, Deployed, Benchmarked).

CRITICAL - USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}

PRIORITY DIRECTIVE:
If user auxiliary instructions are provided above, they take ABSOLUTE PRECEDENCE and HIGHEST PRIORITY over standard resume tailoring guidelines."""),
    ("user", """--- TARGET JOB DESCRIPTION ---
{job_description}

--- RECRUITER AUDIT FEEDBACK ---
Current Match Tier: {match_tier}
Gaps Identified:
{gaps}

Improvement Suggestions:
{suggestions}

--- CATEGORIZED ACTION VERBS ---
{action_verbs_by_category}

--- BASE CANDIDATE RESUME ---
{current_resume}

Rewrite the complete resume in Markdown now. Apply semantic bridging to emphasize transferable architectural equivalence with the JD while maintaining 100% factual truth.""")
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
        aux_instructions = "None provided. Apply standard semantic bridging guidelines."

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