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
        description="The first-person referral request note written directly from the candidate asking for an internal referral (60 to 90 words)."
    )


REFERRAL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are the JOB APPLICANT (The Candidate). 
You are writing a direct, polite message to an existing employee or engineering lead at {company} on LinkedIn or email, asking them to submit an internal job referral for YOU for the {role} position.

YOUR IDENTITY & MINDSET:
- You are NOT a recruiter, career coach, agency scout, or third-party strategist.
- You are NOT sourcing candidates, and you are NOT asking if they know someone else for the job.
- YOU are an accomplished software/ML engineer who wants to work at {company}, reaching out to a peer to request an internal referral.

STEP-BY-STEP WRITING GUIDE:
1. GREETING: Start with "Hi [Name]," (or "Hi [First Name],").
2. THE HOOK: Mention that you came across the {role} opening at {company} and are very excited about the team's work.
3. THE FIT (1-2 sentences): Highlight 1 or 2 specific technical accomplishments from your background that make you an immediate fit for this opening.
4. THE ASK: Directly ask if they would be open to reviewing your resume and submitting an internal referral on your behalf.
5. CLOSING: Thank them for their time and sign off with:
   Best regards,
   [Your Name]

STRICT NEGATIVE RESTRICTIONS:
- NEVER say "If you know someone fitting this role" or "I am reaching out to connect you with a candidate".
- NEVER refer to yourself in the third person ("they", "the candidate").
- Keep the entire body concise (typically 60 to 90 words unless user instructions specify otherwise). Avoid fluff, excessive pleasantries, or life stories.

CRITICAL - USER AUXILIARY INSTRUCTIONS (HIGHEST PRIORITY OVERRIDE):
{auxiliary_instructions}

PRIORITY DIRECTIVE:
If user auxiliary instructions are provided above, they take ABSOLUTE PRECEDENCE and HIGHEST PRIORITY over default tone, length, or template phrasing whenever a conflict arises. Tailor the message according to the user's specific guidance."""
    ),
    (
        "user",
        """Target Role: {role}
Target Company: {company}

My Verified Strengths:
{strengths}

Write the direct referral request message from me asking the recipient for an internal referral."""
    )
])


def referral_node(state: AgentState) -> Dict[str, Any]:
    """Generates a high-converting referral request written by the applicant."""
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=settings.REFERRAL_TEMP,
        num_ctx=4096,
        num_predict=1024
    ).with_structured_output(ReferralResult)

    strengths_list = state.get("strengths") or []
    strengths_text = "\n".join(f"- {s}" for s in strengths_list[:3]) or "- Python, RAG architectures, and distributed ML pipelines."

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