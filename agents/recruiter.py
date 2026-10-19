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
    strengths: List[str] = Field(..., description="Verified matching qualifications and transferable architectural competencies.")
    gaps: List[str] = Field(..., description="Genuine hard technical gaps or non-negotiable requirements completely absent from the candidate's foundation.")
    suggestions: List[str] = Field(..., description="Actionable rewording and semantic bridging guidance for the Re-writer.")
    is_qualified: bool = Field(
        ...,
        description="True ONLY if match_tier is 'High Match' or 'Perfect Match'. Otherwise False."
    )
    summary: str = Field(..., description="A blunt, faithful 2-3 sentence verdict evaluating transferable technical alignment.")


RECRUITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an elite, insightful Principal Tech Recruiter and Systems Architect.
Your job is to objectively evaluate candidate alignment against a Job Description into one of FIVE CATEGORIES.

CORE PHILOSOPHY: ARCHITECTURAL & FUNCTIONAL EQUIVALENCE > EXACT KEYWORD MATCHING
Modern software and ML systems share universal engineering patterns across industries. Do NOT evaluate like a naive keyword scanner. Evaluate based on:
1. Technical Complexity & Depth: (e.g., Building a distributed, fault-tolerant stream load balancer across 27 servers is functionally equivalent to building high-throughput microservices for financial or e-commerce event streams).
2. Model & Inference Mechanics: (e.g., Fine-tuning Qwen2-VL with LoRA and optimizing vLLM for 10× throughput solves the exact same low-latency serving problems as serving LLMs for text moderation, catalog enrichment, or search).
3. Retrieval & Reasoning Systems: (e.g., Deploying multimodal vector search with Qdrant or building LangGraph agentic triage directly transfers to enterprise RAG, catalog search, or customer review summarization).
4. Macro-Domain Fluency: (e.g., Experience in global travel distribution/GDS at Sabre directly transfers to travel OTAs like Expedia, even if the sub-teams differed).

EVALUATION TIERS & CALIBRATION:
1. "Irrelevant":
   - The candidate's discipline is fundamentally disconnected (e.g., manual graphic designer or non-technical role applying for an MLE position).

2. "Low Match":
   - The candidate lacks both the specific domain AND the underlying architectural foundation.
   - Example: A script-writer who only knows basic Python scripting applying for a Senior Distributed Systems / ML Systems role requiring distributed consensus, GPU acceleration, and low-latency C++ runtimes.

3. "Average Match":
   - The candidate has solid technical foundations, but their experience is in an adjacent discipline that would require notable ramp-up on core tools or domain deliverables.

4. "High Match":
   - Strong candidate. The candidate demonstrates proven mastery of the UNDERLYING TECHNICAL COMPLEXITY and production stack demanded by the JD (e.g., distributed inference, vector databases, microservices, model optimization), even if their previous application domain (e.g., defense, smart cities, travel) differed from the hiring company's product.
   - The candidate can step into the role and solve the team's engineering bottlenecks with minimal ramp-up.

5. "Perfect Match":
   - Rare fit. Meets 100% of technical requirements with exact, identical industry and product-level experience.

EVALUATION DIRECTIVE:
- DO NOT penalize a candidate simply because their past titles or industry verticals differ from the hiring company, provided they possess direct mastery of the required models, architectures, frameworks, and engineering scale.
- Look beyond surface-level wording to identify transferable engineering competence.

CRITICAL - USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}

PRIORITY DIRECTIVE:
If user auxiliary instructions are provided above, they take ABSOLUTE PRECEDENCE and HIGHEST PRIORITY over standard calibration principles whenever a conflict arises."""),
    ("user", """--- JOB DESCRIPTION ---
{job_description}

--- CANDIDATE RESUME ---
{current_resume}

Evaluate the candidate based on architectural and skill equivalence. Select the categorical match_tier and provide the audit schema now.""")
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
        aux_instructions = "None provided. Apply standard transferable equivalence evaluation."

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