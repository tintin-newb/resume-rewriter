# agents/referral.py
from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from agents.state import AgentState


class ReferralResult(BaseModel):
    message: str = Field(..., description="Concise, high-impact cold referral or reachout message (under 120 words).")
    target_role: str = Field(..., description="Target role name.")
    impact_highlights: list[str] = Field(..., description="Key qualifications highlighted in the outreach.")


REFERRAL_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an Executive Career Coach specializing in high-conversion networking.
Write a concise, natural, and punchy referral reachout message for LinkedIn or email.
- Highlight 2 matching core strengths from the candidate's profile.
- Tone: Professional, confident, respectful of the recipient's time.
- Length: Under 120 words. No boilerplate filler."""),
    ("user", """Role: {role} at {company}
Top Candidate Strengths for this JD:
{strengths}

Generate the referral message.""")
])


def referral_node(state: AgentState) -> Dict[str, Any]:
    """Generates an impactful referral outreach message."""
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.3
    ).with_structured_output(ReferralResult)

    chain = REFERRAL_PROMPT | llm
    res: ReferralResult = chain.invoke({
        "role": state["role"],
        "company": state["company"],
        "strengths": "\n".join(f"- {s}" for s in state["strengths"][:3])
    })

    return {
        "referral_message": res.message
    }