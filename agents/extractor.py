# agents/extractor.py
from enum import Enum
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings
from agents.state import AgentState


class SectionType(str, Enum):
    SKILLS = "skills"
    WORK_EXPERIENCE = "work_experience"
    PROJECTS = "projects"
    EDUCATION = "education"
    PUBLICATIONS = "publications"
    ACHIEVEMENTS = "achievements"
    OTHER = "other"  # Leadership, volunteering, positions of responsibility, etc.


class ResumeSection(BaseModel):
    title: str = Field(
        ...,
        description="Standardized uppercase title in markdown, e.g., 'SKILLS', 'WORK EXPERIENCE', 'EDUCATION', 'PROJECTS'."
    )
    section_type: SectionType = Field(
        ...,
        description="Categorical type of this section."
    )
    content: str = Field(
        ...,
        description=(
            "Cleaned Markdown content for this section ONLY. "
            "Fix squished dates/text and normalize bullet points to standard dashes ('- '). "
            "PRESERVE all original metrics, dates, companies, and achievements verbatim."
        )
    )


class ExtractedResume(BaseModel):
    candidate_name: str = Field(
        ...,
        description="Full legal or professional name of the candidate."
    )
    contact_header: str = Field(
        ...,
        description="Single-line Markdown string of contact details, e.g.: '**Email:** user@mail.com | **Contact:** +91 ... | **LinkedIn:** ...'"
    )
    sections: List[ResumeSection] = Field(
        ...,
        description="Ordered list of all non-header sections parsed from the raw resume text."
    )


EXTRACTOR_SYSTEM_PROMPT = """You are an expert Document Parsing and Layout Normalization Agent.
Your SOLE job is to ingest raw, unformatted text extracted from a resume (PDF/TXT) and segment it into structured, clean Markdown sections.

CRITICAL INSTRUCTIONS:
1. ZERO EDITING / ZERO REWRITING:
   - You MUST NOT edit, summarize, rewrite, or omit ANY detail, metric, company, or project.
   - Retain 100% of the candidate's factual claims, numbers, and dates verbatim.
2. LAYOUT & TYPO CLEANUP:
   - PDF extraction often merges words or squishes dates (e.g., "EngineerJul 2024" -> "Engineer | Jul 2024"). You MUST add proper spacing.
   - Convert all unicode or corrupted bullet points (•, ◦, *) into standard Markdown dashes ("- ").
3. PROPER CHUNKING:
   - Header information (Name, Email, Phone, Links) belongs ONLY in `candidate_name` and `contact_header`.
   - Every major resume block (Skills, Work Experience, Education, Projects, Publications, Achievements, Positions of Responsibility) must be a separate `ResumeSection` entry.
   - Do NOT merge Projects into Work Experience, and do NOT merge Achievements into Education.
4. CONTENT FIDELITY:
   - The `content` field of each section must contain the complete text of that section without abbreviation."""

EXTRACTOR_USER_PROMPT = """--- RAW RESUME TEXT ---
{raw_resume_text}

Parse this raw text into the structured ExtractedResume schema now."""


def extractor_node(state: AgentState) -> Dict[str, Any]:
    """
    Extracts raw resume text into standardized, cleanly formatted sections.
    """
    llm = ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.0,
        num_ctx=8192,
        num_predict=4096,
    ).with_structured_output(ExtractedResume)

    prompt = ChatPromptTemplate.from_messages([
        ("system", EXTRACTOR_SYSTEM_PROMPT),
        ("user", EXTRACTOR_USER_PROMPT),
    ])

    chain = prompt | llm

    raw_text = state.get("raw_resume_text", "")
    if not raw_text and state.get("base_resume"):
        raw_text = state["base_resume"]

    extracted: ExtractedResume = chain.invoke({"raw_resume_text": raw_text})

    # Convert Pydantic section objects into serialized dicts for state persistence
    sections_list = [
        {
            "title": s.title,
            "section_type": s.section_type.value,
            "content": s.content.strip()
        }
        for s in extracted.sections
    ]

    header_block = f"# {extracted.candidate_name}\n{extracted.contact_header}"

    return {
        "candidate_header": header_block,
        "parsed_sections": sections_list,
        "current_section_idx": 0,
        "processed_sections": []
    }