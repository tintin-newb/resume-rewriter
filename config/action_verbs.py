# config/action_verbs.py
from typing import Dict, List

ACTION_VERBS_CATALOG: Dict[str, List[str]] = {
    "Accomplishments & High Impact": [
        "Accelerated", "Achieved", "Attained", "Completed", "Conceived", "Discovered",
        "Doubled", "Effected", "Eliminated", "Expanded", "Expedited", "Founded",
        "Improved", "Increased", "Initiated", "Innovated", "Introduced", "Invented",
        "Launched", "Mastered", "Originated", "Overcame", "Overhauled", "Pioneered",
        "Reduced", "Resolved", "Revitalized", "Spearheaded", "Strengthened",
        "Transformed", "Upgraded"
    ],
    "Technical & Engineering": [
        "Assembled", "Built", "Calculated", "Computed", "Designed", "Devised",
        "Engineered", "Fabricated", "Maintained", "Operated", "Pinpointed",
        "Programmed", "Remodeled", "Repaired", "Solved"
    ],
    "Leadership & Management": [
        "Administered", "Analyzed", "Assigned", "Chaired", "Consolidated", "Contracted",
        "Convinced", "Coordinated", "Decided", "Delegated", "Developed", "Directed",
        "Evaluated", "Examined", "Executed", "Expanded", "Facilitated", "Improved",
        "Initiated", "Managed", "Organized", "Oversaw", "Planned", "Prioritized",
        "Produced", "Recommended", "Reorganized", "Reported", "Reviewed", "Scheduled",
        "Supervised"
    ],
    "Research & Investigation": [
        "Calculated", "Cataloged", "Collected", "Correlated", "Critiqued", "Diagnosed",
        "Discovered", "Evaluated", "Examined", "Experimented", "Extrapolated", "Extracted",
        "Gathered", "Identified", "Inspected", "Interpreted", "Interviewed", "Investigated",
        "Monitored", "Organized", "Proved", "Reviewed", "Summarized", "Surveyed",
        "Systemized", "Tested"
    ],
    "Communication & Collaboration": [
        "Addressed", "Advised", "Aided", "Arbitrated", "Arranged", "Authored",
        "Clarified", "Co-authored", "Collaborated", "Consulted", "Corresponded",
        "Counseled", "Defined", "Drafted", "Enlisted", "Formulated", "Influenced",
        "Informed", "Inspired", "Interpreted", "Interviewed", "Lectured", "Mediated",
        "Merged", "Moderated", "Negotiated", "Persuaded", "Promoted", "Proposed",
        "Publicized", "Reconciled", "Recruited", "Represented", "Resolved", "Spoke",
        "Suggested", "Translated", "Wrote"
    ],
    "Creative & Problem Solving": [
        "Abstracted", "Acted", "Adapted", "Composed", "Conceptualized", "Created",
        "Customized", "Designed", "Drew", "Fashioned", "Generated", "Illustrated",
        "Imagined", "Improvised", "Instituted", "Integrated", "Innovated", "Painted",
        "Performed", "Problem solved", "Revised", "Revitalized", "Set up", "Shaped",
        "Streamlined", "Structured", "Synthesized", "Tabulated", "Validated", "Visualized"
    ],
    "Detail & Execution": [
        "Approved", "Catalogued", "Classified", "Collated", "Compared", "Compiled",
        "Dispatched", "Documented", "Enforced", "Filed", "Followed through", "Generated",
        "Implemented", "Met deadlines", "Monitored", "Ordered", "Prepared", "Processed",
        "Purchased", "Recorded", "Retrieved", "Screened", "Set priorities", "Specified",
        "Systematized", "Tabulated"
    ],
    "Teaching & Mentoring": [
        "Adapted", "Advised", "Clarified", "Coached", "Communicated", "Conducted",
        "Enabled", "Encouraged", "Educated", "Explained", "Facilitated", "Familiarized",
        "Guided", "Informed", "Instructed", "Lectured", "Mentored", "Motivated",
        "Participated", "Stimulated", "Supported", "Taught", "Trained", "Verified"
    ],
    "Financial & Commercial": [
        "Administered", "Allocated", "Analyzed", "Appraised", "Audited", "Balanced",
        "Budgeted", "Calculated", "Computed", "Figured", "Managed", "Planned",
        "Projected", "Researched"
    ],
    "Service & Operations": [
        "Assessed", "Assisted", "Attended", "Cared", "Delivered", "Demonstrated",
        "Furnished", "Handled", "Installed", "Issued", "Referred", "Rehabilitated",
        "Reinforced", "Submitted"
    ]
}


def get_formatted_action_verbs_prompt() -> str:
    """Formats the categorized verbs into a structured prompt block."""
    blocks = []
    for category, verbs in ACTION_VERBS_CATALOG.items():
        sample = ", ".join(verbs)
        blocks.append(f"[{category.upper()}]:\n  {sample}")
    return "\n\n".join(blocks)