# agents/state.py
from typing import TypedDict, List, Dict, Optional, Any


class AgentState(TypedDict):
    # Job Information
    company: str
    job_id: str
    role: str
    job_url: Optional[str]
    job_description: str

    # Raw Inputs & Extraction
    raw_resume_text: str
    candidate_header: str                     # "# Name \n Email | Phone | LinkedIn"
    parsed_sections: List[Dict[str, Any]]     # Clean sections extracted by ExtractionAgent

    # User Guidance
    auxiliary_instructions: Optional[str]
    recruiter_instructions: Optional[str]
    rewriter_instructions: Optional[str]
    referral_instructions: Optional[str]

    # Pipeline Section Iteration State
    current_section_idx: int                  # Index pointer for section iteration
    processed_sections: List[Dict[str, Any]]  # Surviving sections after Observer & Rewriter
    final_resume: str                         # Final stitched Markdown document

    # Recruiter-Observer Outputs (Current Section)
    observer_action: Optional[str]            # "DROP" | "KEEP_AS_IS" | "REVISE"
    section_directives: List[str]             # Specific suggestions for current section

    # Recruiter-Matcher Outputs (Holistic Evaluation)
    match_tier: str                           # "Irrelevant", "Low Match", ..., "Perfect Match"
    strengths: List[str]
    gaps: List[str]
    is_qualified: bool
    recruiter_verdict: str

    # Referral & Persistence
    referral_message: Optional[str]
    source_resume_path: Optional[str]
    saved_file_path: Optional[str]
    status: str