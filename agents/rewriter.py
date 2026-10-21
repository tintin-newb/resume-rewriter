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

1. ABSOLUTE EMPLOYMENT PRESERVATION (NEVER DELETE A COMPANY):
   - You are STRICTLY FORBIDDEN from deleting any employer, job title, or employment period under `### WORK EXPERIENCE`.
   - Every single company present in the candidate's resume (e.g., Griffyn Robotech, Sabre Corporation) MUST be retained.
   - You may reword, prioritize, or compress bullets within a job, but NEVER delete the job entry itself.

2. PRUNING CHECKLIST EXECUTION:
   - For every item marked `[DELETE]` in the Recruiter's directives, you MUST locate it (whether in Achievements, Projects, or Positions of Responsibility) and COMPLETELY ERASE IT.
   - If an entire section becomes empty after pruning (e.g., Position of Responsibility), omit the section heading as well.
   - SURGICAL RETENTION: Do NOT delete any achievement, publication, or metric that was NOT targeted by a `[DELETE]` directive.

3. REORDERING & HIERARCHY:
   - For items marked `[MOVE TO TOP]`: Place them as the #1 and #2 bullet points under their respective company or section.

4. CLOSED-WORLD SKILLS (NO JARGON INJECTION):
   - The `## SKILLS` section is a CLOSED-WORLD LIST.
   - DO NOT add any tool, platform, or database not in the candidate's resume.
   - DO NOT invent new category headers (e.g., do NOT create `Data Platforms` or `Distributed Systems`). Retain original categories (*Languages*, *Area of Expertise*, *Tools & Frameworks*).

5. IMPACT-DRIVEN REWORDING (GOOGLE XYZ):
   - Format: [Strong Action Verb] + [Technical Scope/Action Taken] + [Quantified Outcome/Impact].
   - FORBIDDEN: NEVER write "as measured by", "Accomplished [X]", or "by doing [Z]".
   - Use active verbs from the categorized catalog.

6. OUTPUT SPECIFICATION:
   - Output ONLY the finalized Markdown resume starting directly with `# Candidate Name`.
   - Do NOT wrap in JSON. Do NOT include markdown code fences (```). Do NOT include commentary.

CRITICAL - USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}"""),
    ("user", """--- TARGET JOB DESCRIPTION ---
{job_description}

--- RECRUITER AUDIT & DIRECTIVES ---
Current Match Tier: {match_tier}
{suggestions}

--- CATEGORIZED ACTION VERBS ---
{action_verbs_by_category}

--- CANDIDATE RESUME ---
{current_resume}

Execute the directives in pure Markdown now. Erase every `[DELETE]` item, retain ALL companies in Work Experience, and reorder as instructed.""")
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

    formatted_suggestions = "\n\n".join(state.get("suggestions", []))

    raw_markdown: str = chain.invoke({
        "job_description": state["job_description"],
        "match_tier": state.get("match_tier", "Low Match"),
        "suggestions": formatted_suggestions,
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
            "Preserved all verified employers in Work Experience",
            "Enforced closed-world skills baseline",
            "Applied semantic bridging to experience"
        ],
        "iteration": state["iteration"] + 1
    }