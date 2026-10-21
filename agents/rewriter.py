# agents/rewriter.py
from typing import Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config.settings import settings
from config.action_verbs import get_formatted_action_verbs_prompt
from agents.state import AgentState


REWRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Executive Tech Resume Strategist.
Your mission is to reframe, visually prioritize, and surgically PRUNE the candidate's resume to match the target Job Description (JD).

1. EXECUTION OF RECRUITER DIRECTIVES:
   - PRUNING DIRECTIVE: You MUST completely delete and remove ONLY the specific bullet points, undergraduate activities, or non-essential sections named in the directive.
   - SURGICAL RETENTION: Do NOT delete or drop any achievement or metric that was NOT targeted by the pruning directive. Keep all core experience intact.
   - REORDERING DIRECTIVE: Promote the specified high-impact achievements to rank #1 and #2 under their respective roles to capture attention in the first 6 seconds.
   - CONCISENESS DIRECTIVE: If marked concise, do not delete sections; focus on reordering and rewording.

2. CLOSED-WORLD SKILLS (NO JARGON INJECTION):
   - The `## SKILLS` section is a CLOSED-WORLD LIST.
   - DO NOT add any tool or platform that does not exist in the candidate's resume (NEVER add Apache Spark, Databricks, Ray, or Delta Lake).
   - DO NOT invent new skill category subheadings. Retain the candidate's existing categories (*Languages*, *Area of Expertise*, *Tools & Frameworks*), prioritizing JD-relevant terms toward the front of each line.

3. IMPACT-DRIVEN REWORDING (GOOGLE XYZ):
   - Format: [Strong Action Verb] + [Technical Scope/Action Taken] + [Quantified Outcome/Impact].
   - FORBIDDEN: NEVER write "as measured by", "Accomplished [X]", or "by doing [Z]".
   - Translate situational jargon into universal software/ML engineering language without fabricating claims.

4. OUTPUT SPECIFICATION:
   - Output ONLY the finalized Markdown resume starting directly with `# Candidate Name`.
   - Do NOT wrap in JSON. Do NOT include markdown code fences (```). Do NOT include conversational commentary.

CRITICAL - USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}"""),
    ("user", """--- TARGET JOB DESCRIPTION ---
{job_description}

--- RECRUITER AUDIT DIRECTIVES ---
Current Match Tier: {match_tier}
Directives:
{suggestions}

--- CATEGORIZED ACTION VERBS ---
{action_verbs_by_category}

--- CANDIDATE RESUME ---
{current_resume}

Rewrite, reorder, and surgically prune the resume in pure Markdown now according to the directives.""")
])


def rewriter_node(state: AgentState) -> Dict[str, Any]:
    """Generates a pruned, prioritized, and tailored Markdown resume with fast token prefill."""
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
        aux_instructions = "None provided. Apply standard surgical pruning, reordering, and semantic bridging."

    chain = REWRITER_PROMPT | llm | StrOutputParser()

    raw_markdown: str = chain.invoke({
        "job_description": state["job_description"],
        "match_tier": state.get("match_tier", "Low Match"),
        "suggestions": "\n".join(f"- {s}" for s in state["suggestions"]),
        "action_verbs_by_category": get_formatted_action_verbs_prompt(),
        "auxiliary_instructions": aux_instructions,
        "current_resume": state["current_resume"]
    })

    cleaned = raw_markdown.strip()
    if cleaned.startswith("```markdown"):
        cleaned = cleaned[len("```markdown"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return {
        "current_resume": cleaned,
        "modifications_made": [
            "Executed Recruiter pruning & reordering directives",
            "Enforced closed-world skills baseline",
            "Applied semantic bridging to experience"
        ],
        "iteration": state["iteration"] + 1
    }