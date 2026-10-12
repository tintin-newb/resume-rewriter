# agents/state.py
from typing import TypedDict, List, Optional


class AgentState(TypedDict):
    # Job Information
    company: str
    job_id: str
    role: str
    job_url: Optional[str]
    job_description: str

    # Resumes
    base_resume: str
    current_resume: str

    # Loop Controls
    iteration: int
    max_loops: int
    min_match_score: float

    # Recruiter Outputs
    match_score: float
    strengths: List[str]
    gaps: List[str]
    suggestions: List[str]
    is_qualified: bool
    recruiter_verdict: str

    # Rewriter Outputs
    modifications_made: List[str]

    # Referral Output
    referral_message: Optional[str]

    # Artifacts & DB State
    saved_file_path: Optional[str]
    status: str