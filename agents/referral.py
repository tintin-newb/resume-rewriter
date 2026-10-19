from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from agents.state import AgentState


class ReferralResult(BaseModel):
    subject_line: str = Field(
        ...,
        description="A concise, professional subject line for LinkedIn or email (e.g., 'Referral inquiry: {role} opening - [Your Name]')."
    )
    message: str = Field(
        ...,
        description="The first-person referral request note highlighting transferable architectural alignment (60 to 90 words)."
    )


REFERRAL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are the JOB APPLICANT (The Candidate). 
You are writing a direct, polite message to an existing employee or engineering lead at {company} on LinkedIn or email, asking them to submit an internal job referral for YOU for the {role} position.

YOUR IDENTITY & PERSPECTIVE:
- Write strictly in the FIRST PERSON ("I", "my background", "I have worked with").
- You are an accomplished engineer reaching out peer-to-peer to request an internal referral.
- Pitch your fit around TRANSFERABLE ARCHITECTURAL VALUE: highlight how your hands-on mastery of scalable systems, model optimization (e.g., vLLM/LoRA), and industry/platform scale allows you to contribute immediately to their specific team challenges.

STEP-BY-STEP WRITING GUIDE:
1. GREETING: Start with "Hi [Name]," (or "Hi [First Name],").
2. THE HOOK: State that you noticed the {role} opening on their team at {company} and are excited by their engineering direction.
3. THE TRANSFERABLE VALUE (1-2 sentences): Connect your proven background in core relevant systems (e.g., distributed inference, vector search, high-throughput pipelines, or shared macro-domain experience) directly to their platform requirements.
4. THE ASK: Politely ask if they would be open to reviewing your resume or submitting an internal referral on your behalf.
5. CLOSING: Thank them for their time and sign off with:
   Best regards,
   [Your Name]

STRICT RESTRICTIONS:
- NEVER say "If you know someone fitting this role" or speak in the third person.
- Keep the entire body concise (60 to 90 words). Avoid fluff or generic flattery.

CRITICAL - USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}

PRIORITY DIRECTIVE:
If user auxiliary instructions are provided above, they take ABSOLUTE PRECEDENCE and HIGHEST PRIORITY over default tone or phrasing whenever a conflict arises."""
    ),
    (
        "user",
        """Target Role: {role}
Target Company: {company}

My Transferable Architectural Strengths:
{strengths}

Write the direct referral request message from me asking the recipient for an internal referral."""
    )
])


def referral_node(state: AgentState) -> Dict[str, Any]:
    """Generates an impactful first-person outreach message emphasizing transferable strengths."""
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=settings.REFERRAL_TEMP,
        num_ctx=4096,
        num_predict=1024
    ).with_structured_output(ReferralResult)

    strengths_list = state.get("strengths") or []
    strengths_text = "\n".join(f"- {s}" for s in strengths_list[:3]) or "- Distributed model serving, high-throughput streaming, and vector search systems."

    referral_inst = (state.get("referral_instructions") or "").strip()
    general_inst = (state.get("auxiliary_instructions") or "").strip()

    if referral_inst and general_inst:
        aux_instructions = f"[Specific Referral Instructions - Top Priority]:\n{referral_inst}\n\n[General Guidance]:\n{general_inst}"
    elif referral_inst:
        aux_instructions = referral_inst
    elif general_inst:
        aux_instructions = general_inst
    else:
        aux_instructions = "None provided. Apply standard outreach guidelines."

    chain = REFERRAL_PROMPT | llm

    res: ReferralResult = chain.invoke({
        "role": state["role"],
        "company": state["company"],
        "strengths": strengths_text,
        "auxiliary_instructions": aux_instructions
    })

    full_message = f"Subject: {res.subject_line}\n\n{res.message}"

    return {
        "referral_message": full_message
    }