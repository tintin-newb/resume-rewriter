# agents/rewriter.py
from typing import Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config.settings import settings
try:
    from config.action_verbs import get_formatted_action_verbs_prompt
except ImportError:
    from config.actions_verbs import get_formatted_action_verbs_prompt
from agents.state import AgentState


REWRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Executive Tech Resume Strategist.
Your mission is to reframe, optimize, and PRUNE the candidate's EXISTING resume to highlight deep architectural alignment with the target Job Description (JD).

1. STRICT CLOSED-WORLD SKILLS ENFORCEMENT (ZERO JARGON INJECTION):
   - The `## SKILLS` section is a STRICT CLOSED-WORLD LIST.
   - You are STRICTLY FORBIDDEN from adding any skill, tool, framework, database, or library to `## SKILLS` that does not exist in the BASE RESUME (e.g., NEVER add Apache Spark, Databricks, Ray, or Delta Lake simply because they appear in the JD).
   - Only re-organize, highlight, or categorize the candidate's GENUINE existing skills.

2. ACTIVE PRUNING & CONCISION (REMOVE IRRELEVANT SECTIONS):
   - Review the candidate's base experience against the JD. 
   - OMIT or compress bullet points and peripheral sections that have no bearing on the target role (e.g., outdated undergraduate coding competitions, unrelated QA scripts, or non-technical awards) if they clutter the resume.
   - Keep the resume dense, punchy, and focused on high-signal engineering accomplishments.

3. SEMANTIC BRIDGING (TRANSFERABILITY WITHOUT FABRICATION):
   - Translate niche situational jargon into universal software/ML engineering language.
   - Highlight transferable system mechanics (e.g., distributed inference, high-throughput streaming, multimodal retrieval, low-latency optimization) that match the JD's technical complexity.
   - ZERO HALLUCINATION: Never invent new projects, fake metrics, or unearned claims.

4. ORGANIC IMPACT BULLETS (GOOGLE "XYZ" PHILOSOPHY):
   - Format: [Action Verb] + [Technical Scope/Action Taken] + [Quantified Outcome/Impact].
   - FORBIDDEN: NEVER write the literal phrases "as measured by", "Accomplished [X]", or "by doing [Z]".
   - Anchor bullets using strong active verbs from the categorized catalog.

5. OUTPUT SPECIFICATION:
   - Output ONLY the finalized, publication-ready Markdown resume.
   - Do NOT wrap in JSON. Do NOT include introductory remarks or conversational commentary. Start directly with `# Candidate Name`.

CRITICAL - USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}"""),
    ("user", """--- TARGET JOB DESCRIPTION ---
{job_description}

--- RECRUITER AUDIT FEEDBACK ---
Current Match Tier: {match_tier}
Gaps Identified:
{gaps}

Improvement & Pruning Suggestions:
{suggestions}

--- CATEGORIZED ACTION VERBS ---
{action_verbs_by_category}

--- BASE CANDIDATE RESUME ---
{current_resume}

Rewrite and prune the complete resume in pure Markdown now. Adhere strictly to the Closed-World Skills rule and omit irrelevant points.""")
])


def rewriter_node(state: AgentState) -> Dict[str, Any]:
    """Generates a clean, pruned, and tailored Markdown resume with zero JSON fragility."""
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.1,
        num_ctx=8192,
        num_predict=4096
    )

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

    # Using StrOutputParser guarantees clean Markdown without JSON serialization bugs
    chain = REWRITER_PROMPT | llm | StrOutputParser()

    raw_markdown: str = chain.invoke({
        "job_description": state["job_description"],
        "match_tier": state.get("match_tier", "Low Match"),
        "gaps": "\n".join(f"- {g}" for g in state["gaps"]),
        "suggestions": "\n".join(f"- {s}" for s in state["suggestions"]),
        "action_verbs_by_category": get_formatted_action_verbs_prompt(),
        "auxiliary_instructions": aux_instructions,
        "current_resume": state["current_resume"]
    })

    # Clean up any potential markdown block markers
    cleaned_markdown = raw_markdown.strip()
    if cleaned_markdown.startswith("```markdown"):
        cleaned_markdown = cleaned_markdown[len("```markdown"):].strip()
    elif cleaned_markdown.startswith("```"):
        cleaned_markdown = cleaned_markdown[len("```"):].strip()
    if cleaned_markdown.endswith("```"):
        cleaned_markdown = cleaned_markdown[:-3].strip()

    return {
        "current_resume": cleaned_markdown,
        "modifications_made": ["Pruned irrelevant bullets", "Aligned skills strictly to verified baseline", "Applied semantic bridging to experience"],
        "iteration": state["iteration"] + 1
    }