# agents/rewriter.py
from typing import Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from config.settings import settings
from config.action_verbs import get_formatted_action_verbs_prompt
from agents.state import AgentState


SECTION_REWRITER_SYSTEM_PROMPT = """You are an Executive Tech Resume Strategist.
Your task is to optimize and reformat ONE SPECIFIC SECTION of a candidate's resume for a target Job Description (JD).

CRITICAL SECTION-LEVEL INSTRUCTIONS:
1. STRICT ADHERENCE TO OBSERVER DIRECTIVES:
   - PRUNE BULLETS: If the directives list `[DELETE]: ...` under `PRUNE BULLETS:`, you MUST completely eliminate those specific lines or achievements. Do NOT retain them.
   - REORDER BULLETS: If the directives list `[MOVE TO TOP]: ...` under `REORDER BULLETS:`, you MUST place those specific achievements as the #1 and #2 bullet points in this section.
   - REWORDING DIRECTIVES: If the directives list items under `REWORDING:`, you MUST implement those specific suggestions to strengthen action verbs, highlight system complexity, and quantify impact.
   - SURGICAL RETENTION: Do NOT delete any bullet point, employer, date, or metric that was NOT targeted by a delete directive.
   - KEEP_AS_IS SECTION HANDLING: When a section has action `KEEP_AS_IS` or lacks revision directives, preserve the section's core achievements and details, but inspect every pointer: ensure the word limit constraint ({word_limit} words per pointer) is satisfied, and reword any pointer that can be made crisper, denser, and more impactful.

2. CLOSED-WORLD FIDELITY (ZERO JARGON INJECTION):
   - You MUST NOT add any new tool, library, framework, or cloud platform that was not present in this section.
   - If rewriting the SKILLS section: Do NOT invent new skill categories or add unearned keywords. Only reprioritize existing skills.
   - Retain all factual metrics, dates, company names, and project titles verbatim.

3. IMPACT-DRIVEN REWORDING (GOOGLE XYZ PHILOSOPHY):
   - Rephrase bullets using: [Strong Action Verb] + [Technical Scope/System Architecture] + [Quantified Outcome/Impact].
   - FORBIDDEN: NEVER write literal phrases like "as measured by", "Accomplished [X]", or "by doing [Z]".
   - Use active verbs from the categorized catalog provided.

4. WORD LIMIT PER POINTER & IMPACT OPTIMIZATION:
   - Every individual bullet point or pointer MUST NOT exceed {word_limit} words.
   - REGARDLESS of whether the section action is KEEP_AS_IS or REVISE:
     * Check every single pointer for the word limit constraint ({word_limit} words max). If any pointer exceeds this limit, you MUST reword and compress it into a punchy, high-impact bullet within the limit.
     * Furthermore, if any pointer can be made more impactful (e.g. converting passive phrasing into strong action verbs, highlighting quantified systems metrics, improving clarity), you MUST modify and polish it for maximum impact regardless of whether it was marked KEEP_AS_IS or already within the word limit.

5. OUTPUT SPECIFICATION:
   - Output ONLY the clean Markdown content for this section.
   - Do NOT include section titles (e.g., do NOT start with `## WORK EXPERIENCE`; only output the internal content).
   - Do NOT wrap in markdown code fences (```). Do NOT include conversational filler.

USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY):
{auxiliary_instructions}"""

SECTION_REWRITER_USER_PROMPT = """--- TARGET JOB DESCRIPTION ---
{job_description}

--- RECRUITER-OBSERVER DIRECTIVES FOR THIS SECTION ---
{section_directives}

--- CATEGORIZED ACTION VERBS CATALOG ---
{action_verbs_catalog}

--- ORIGINAL SECTION CONTENT ---
Section Title: {section_title}
Section Type: {section_type}

Content:
{section_content}

Rewrite and reorder this section content in clean Markdown now according to the directives. Enforce the {word_limit}-word limit per pointer and optimize pointers for maximum impact:"""


def rewriter_node(state: AgentState) -> Dict[str, Any]:
    """
    Rewrites ONLY the single active section pointed to by current_section_idx.
    Applies observer directives, prunes targeted bullets, and reorders top achievements.
    """
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.1,
        num_ctx=4096,
        num_predict=1536,
        reasoning=settings.reasoning,
    )

    current_idx = state.get("current_section_idx", 0)
    sections = state.get("parsed_sections", [])

    if not sections or current_idx >= len(sections):
        return {}

    target_section = sections[current_idx]
    # Word limit per pointer constraint
    word_limit = state.get("word_limit") or settings.WORD_LIMIT
    action = state.get("observer_action", "KEEP_AS_IS")

    directives_list = state.get("section_directives")
    if not directives_list:
        if action == "KEEP_AS_IS":
            directives_list = [
                "SECTION STATUS: KEEP_AS_IS (Preserve core achievements and structure)",
                f"WORD LIMIT CONSTRAINT: Enforce maximum of {word_limit} words per pointer.",
                "IMPACT DIRECTIVE: Audit every pointer and rephrase any pointer that exceeds the word limit or can be made more impactful with strong active verbs."
            ]
        else:
            directives_list = ["No specific directives. Clean formatting, enforce word limits, and enhance action verbs."]
    formatted_directives = "\n".join(directives_list)

    # User auxiliary instruction priority
    rewriter_inst = (state.get("rewriter_instructions") or "").strip()
    general_inst = (state.get("auxiliary_instructions") or "").strip()
    if rewriter_inst and general_inst:
        aux_text = f"{rewriter_inst}\n{general_inst}"
    elif rewriter_inst:
        aux_text = rewriter_inst
    elif general_inst:
        aux_text = general_inst
    else:
        aux_text = "None provided. Apply standard impact rewording and surgical pruning."

    prompt = ChatPromptTemplate.from_messages([
        ("system", SECTION_REWRITER_SYSTEM_PROMPT),
        ("user", SECTION_REWRITER_USER_PROMPT),
    ])

    chain = prompt | llm | StrOutputParser()

    raw_output: str = chain.invoke({
        "job_description": state["job_description"],
        "section_directives": formatted_directives,
        "action_verbs_catalog": get_formatted_action_verbs_prompt(),
        "section_title": target_section.get("title", ""),
        "section_type": target_section.get("section_type", "other"),
        "section_content": target_section.get("content", ""),
        "auxiliary_instructions": aux_text,
        "word_limit": word_limit,
    })

    # Clean any accidental outer code block fences
    cleaned = raw_output.strip()
    if cleaned.startswith("```markdown"):
        cleaned = cleaned[len("```markdown"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    # Append to processed_sections list
    updated_processed = list(state.get("processed_sections", []))
    updated_processed.append({
        "title": target_section["title"],
        "section_type": target_section["section_type"],
        "content": cleaned
    })

    return {
        "processed_sections": updated_processed,
        "current_section_idx": current_idx + 1
    }