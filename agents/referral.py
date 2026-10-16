# agents/referral.py
from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from agents.state import AgentState


class ReferralResult(BaseModel):
    subject_line: str = Field(
        ...,
        description="A punchy, high-open-rate LinkedIn or email subject line."
    )
    message: str = Field(
        ...,
        description="A concise, high-impact first-person outreach message written from the candidate to an employee or manager at the target company (under 110 words)."
    )


REFERRAL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an Executive Networking Strategist.
Write a personalized, concise FIRST-PERSON outreach message from a candidate directly to a prospective colleague, engineering manager, or recruiter at the hiring company.

PERSPECTIVE & VOICE RULES:
1. STRICT FIRST-PERSON VOICE: Write entirely from the perspective of the candidate ("I", "my background", "I have worked with", "I would welcome the opportunity").
2. NEVER write in third-person ("they", "their background", "connect you with [Candidate]").
3. Sign off cleanly with '[Your Name]' as the placeholder.
4. TONE: Confident, peer-to-peer, respectful of the recipient's time.
5. LENGTH: Under 110 words. Highlight 2 specific technical matches between the candidate's background and the role.
6. CALL TO ACTION: A light, low-friction request (e.g., asking for a referral or a brief chat)."""
    ),
    (
        "user",
        """Role: {role} at {company}
Key Matching Strengths:
{strengths}

Generate the first-person referral request message now."""
    )
])


def referral_node(state: AgentState) -> Dict[str, Any]:
    """Generates an impactful first-person outreach message."""
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.2,
        num_ctx=4096,
        num_predict=1024
    ).with_structured_output(ReferralResult)

    strengths_list = state.get("strengths") or []
    strengths_text = "\n".join(f"- {s}" for s in strengths_list[:3]) or "- Python, RAG workflows, and distributed systems."

    chain = REFERRAL_PROMPT | llm

    # Only expects 'role', 'company', and 'strengths'
    res: ReferralResult = chain.invoke({
        "role": state["role"],
        "company": state["company"],
        "strengths": strengths_text
    })

    full_message = f"Subject: {res.subject_line}\n\n{res.message}"

    return {
        "referral_message": full_message
    }