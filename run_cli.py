# run_cli.py
import sys
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.panel import Panel

from config.settings import settings
from bootstrap import SystemBootstrap
from parsers.resume_parser import ResumeParser
from scrapers.jd_scraper import JDScraper
from db.operations import get_existing_application, save_application_state
from agents.workflow import build_workflow
from agents.state import AgentState

console = Console()


def _parse_instruction(inst: Optional[str]) -> Optional[str]:
    """Helper to parse an instruction parameter that may be a direct string or file path."""
    if not inst:
        return None
    try:
        inst_path = Path(inst)
        if inst_path.is_file():
            return inst_path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return inst.strip()


def _get_tier_color(tier: str) -> str:
    """Returns Rich color string for qualification tier."""
    if tier in ("High Match", "Perfect Match"):
        return "green"
    elif tier == "Average Match":
        return "yellow"
    return "red"


@click.command()
@click.option(
    "--resume", "-r",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to base candidate resume (.pdf, .md, .txt, or .docx)."
)
@click.option(
    "--company", "-c",
    required=True,
    type=str,
    help="Name of the hiring company (e.g., 'Mastercard')."
)
@click.option(
    "--job-id", "-j",
    required=True,
    type=str,
    help="Unique requisition ID or code (e.g., 'MAS-101')."
)
@click.option(
    "--role",
    required=True,
    type=str,
    help="Target job title (e.g., 'Senior AI Engineer')."
)
@click.option(
    "--url", "-u",
    type=str,
    default=None,
    help="Public URL to the job posting (scraped via Crawl4AI)."
)
@click.option(
    "--jd-file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Local path to a text/markdown file containing the JD."
)
@click.option(
    "--force", "-f",
    is_flag=True,
    default=False,
    help="Force re-execution even if the job posting was already processed in the database."
)
@click.option(
    "--instructions", "-i",
    type=str,
    default=None,
    help="General auxiliary instructions for all agents (text string or path to a .txt file)."
)
@click.option(
    "--recruiter-instructions", "--recruiter-inst",
    type=str,
    default=None,
    help="Specific guidance for Recruiter-Observer and Matcher agents (text string or file path)."
)
@click.option(
    "--rewriter-instructions", "--rewriter-inst",
    type=str,
    default=None,
    help="Specific guidance for Section Re-writer agent (text string or file path)."
)
@click.option(
    "--referral-instructions", "--referral-inst",
    type=str,
    default=None,
    help="Specific guidance for Referral agent (text string or file path)."
)
@click.option(
    "--word-limit", "-w",
    type=int,
    default=None,
    help="Maximum word limit per pointer in the resume (overrides WORD_LIMIT env setting)."
)
@click.option(
    "--skip-bootstrap",
    is_flag=True,
    default=False,
    help="Skip pre-flight health checks for Ollama and PostgreSQL."
)
def run_cli(
    resume: Path,
    company: str,
    job_id: str,
    role: str,
    url: Optional[str],
    jd_file: Optional[Path],
    force: bool,
    instructions: Optional[str],
    recruiter_instructions: Optional[str],
    rewriter_instructions: Optional[str],
    referral_instructions: Optional[str],
    word_limit: Optional[int],
    skip_bootstrap: bool
):
    """
    Agentic Resume Rewriter CLI:
    Decomposed Section-by-Section Evaluator-Optimizer Pipeline.
    """
    console.print(Panel.fit(
        "[bold cyan]Agentic Resume Rewriter (Section-by-Section Architecture)[/bold cyan]\n"
        "[dim]Powered by Local Ollama & LangGraph State Machine[/dim]",
        border_style="cyan"
    ))

    # --- 1. Pre-Flight Health Checks ---
    if not skip_bootstrap:
        bootstrap = SystemBootstrap()
        if not bootstrap.run_checks():
            console.print("[bold red]Bootstrap verification failed. Aborting run.[/bold red]")
            sys.exit(1)

    # --- 2. Database Deduplication Check ---
    existing = None
    try:
        existing = get_existing_application(company=company, job_id=job_id)
    except Exception as e:
        console.print(f"[dim yellow]Notice: Database deduplication lookup skipped ({e})[/dim yellow]")

    if existing and not force:
        tier = existing.get("match_tier", "N/A")
        tier_color = _get_tier_color(tier)
        console.print(Panel(
            f"[bold yellow]Job posting already evaluated![/bold yellow]\n\n"
            f"[bold]Company:[/bold] {existing['company']}\n"
            f"[bold]Job ID:[/bold] {existing['job_id']}\n"
            f"[bold]Role:[/bold] {existing['role']}\n"
            f"[bold]Match Tier:[/bold] [{tier_color}]{tier}[/{tier_color}]\n"
            f"[bold]Status:[/bold] {existing['status']}\n"
            f"[bold]Saved Resume:[/bold] {existing.get('rewritten_resume_path', 'N/A')}\n\n"
            f"[dim]Run with [bold cyan]--force[/bold cyan] to overwrite this record.[/dim]",
            title="[bold yellow]Cached Run Found[/bold yellow]",
            border_style="yellow"
        ))
        if existing.get("referral_message"):
            console.print(Panel(
                existing["referral_message"],
                title="[bold green]Saved Referral Message[/bold green]",
                border_style="green"
            ))
        return

    if existing and force:
        console.print(f"[yellow]--force detected: Overwriting previous record for {company} ({job_id}).[/yellow]\n")

    # --- 3. Job Description Ingestion ---
    if not url and not jd_file:
        console.print("[bold red]Error:[/bold red] You must supply either [cyan]--url[/cyan] or [cyan]--jd-file[/cyan].")
        sys.exit(1)

    job_description = ""
    if url:
        console.print(f"[cyan]Scraping job description from URL:[/cyan] {url}")
        scraper = JDScraper()
        try:
            job_description = scraper.scrape(url)
            console.print("[green]Successfully extracted and sanitized JD text.[/green]")
        except Exception as e:
            console.print(f"[bold red]Failed to scrape URL:[/bold red] {str(e)}")
            sys.exit(1)
    elif jd_file:
        console.print(f"[cyan]Reading job description from:[/cyan] {jd_file}")
        job_description = jd_file.read_text(encoding="utf-8").strip()

    # --- 4. Resume Ingestion ---
    console.print(f"[cyan]Parsing base resume:[/cyan] {resume}")
    resume_parser = ResumeParser()
    try:
        raw_resume_text = resume_parser.parse(resume)
    except Exception as e:
        console.print(f"[bold red]Failed to parse resume:[/bold red] {str(e)}")
        sys.exit(1)

    # --- Auxiliary Instructions Parsing ---
    parsed_general = _parse_instruction(instructions)
    parsed_recruiter = _parse_instruction(recruiter_instructions)
    parsed_rewriter = _parse_instruction(rewriter_instructions)
    parsed_referral = _parse_instruction(referral_instructions)

    if parsed_general:
        console.print(f"[green]Active General Guidance:[/green] [dim]\"{parsed_general[:80]}...\"[/dim]")
    if parsed_recruiter:
        console.print(f"[green]Active Recruiter Guidance:[/green] [dim]\"{parsed_recruiter[:80]}...\"[/dim]")
    if parsed_rewriter:
        console.print(f"[green]Active Rewriter Guidance:[/green] [dim]\"{parsed_rewriter[:80]}...\"[/dim]")
    if parsed_referral:
        console.print(f"[green]Active Referral Guidance:[/green] [dim]\"{parsed_referral[:80]}...\"[/dim]")
    if any([parsed_general, parsed_recruiter, parsed_rewriter, parsed_referral]):
        console.print()

    active_word_limit = word_limit if word_limit is not None else settings.WORD_LIMIT
    console.print(f"[green]Word Limit per Pointer:[/green] [dim]{active_word_limit} words[/dim]\n")

    # --- 5. State Initialization ---
    initial_state: AgentState = {
        "company": company,
        "job_id": job_id,
        "role": role,
        "job_url": url,
        "job_description": job_description,
        "raw_resume_text": raw_resume_text,
        "candidate_header": "",
        "parsed_sections": [],
        "auxiliary_instructions": parsed_general,
        "recruiter_instructions": parsed_recruiter,
        "rewriter_instructions": parsed_rewriter,
        "referral_instructions": parsed_referral,
        "current_section_idx": 0,
        "processed_sections": [],
        "final_resume": "",
        "word_limit": active_word_limit,
        "observer_action": None,
        "section_directives": [],
        "match_tier": "Pending",
        "strengths": [],
        "gaps": [],
        "recruiter_verdict": "",
        "referral_message": None,
        "source_resume_path": str(resume.resolve()),
        "saved_file_path": None,
        "status": "PROCESSING"
    }

    # --- 6. Workflow Execution (Streamed) ---
    console.print("[bold magenta]Starting Modular Agent Workflow...[/bold magenta]\n")
    workflow = build_workflow()
    final_state = dict(initial_state)

    for event in workflow.stream(initial_state):
        for node_name, node_output in event.items():
            final_state.update(node_output)

            if node_name == "extractor":
                count = len(node_output.get("parsed_sections", []))
                console.print(f"[bold green]✓ Extraction Node:[/bold green] Successfully parsed resume into [cyan]{count}[/cyan] discrete sections.\n")

            elif node_name == "observer":
                action = node_output.get("observer_action", "KEEP_AS_IS")
                action_colors = {"DROP": "red", "KEEP_AS_IS": "green", "REVISE": "yellow"}
                color = action_colors.get(action, "white")
                idx = final_state.get("current_section_idx", 0)
                sections = final_state.get("parsed_sections", [])
                sec_title = sections[idx]["title"] if idx < len(sections) else f"Section {idx + 1}"
                
                action_notes = {
                    "DROP": "[dim](purged low-signal / non-technical)[/dim]",
                    "KEEP_AS_IS": "[dim](preserved verbatim)[/dim]",
                    "REVISE": "[dim](optimization directives generated)[/dim]"
                }
                note = action_notes.get(action, "")
                console.print(f"  [bold cyan]• Observer Auditing:[/bold cyan] {sec_title} ➔ [{color}]{action}[/{color}] {note}")

            elif node_name == "rewriter":
                idx = max(0, final_state.get("current_section_idx", 1) - 1)
                sections = final_state.get("parsed_sections", [])
                sec_title = sections[idx]["title"] if idx < len(sections) else "section"
                console.print(f"    [dim cyan]↳ Re-writer tailored '{sec_title}' with categorized action verbs.[/dim cyan]")

            elif node_name == "advance_section":
                pass  # Section increment handled cleanly

            elif node_name == "stitcher":
                surviving = len(final_state.get("processed_sections", []))
                total = len(final_state.get("parsed_sections", []))
                console.print(f"\n[bold green]✓ Stitcher Node:[/bold green] Assembled [cyan]{surviving}[/cyan] of [cyan]{total}[/cyan] sections into final Markdown.\n")

            elif node_name == "matcher":
                tier = node_output.get("match_tier", "Low Match")
                tier_color = _get_tier_color(tier)
                strengths = node_output.get("strengths", [])
                gaps = node_output.get("gaps", [])

                strengths_text = "\n".join(f"  ✓ {s}" for s in strengths[:4]) if strengths else "  ✓ Strong transferable systems baseline"
                gaps_text = "\n".join(f"  ✗ {g}" for g in gaps[:3]) if gaps else "  (None identified)"
                is_shortlisted = tier in ("High Match", "Perfect Match")

                console.print(Panel(
                    f"[bold]Holistic Match Tier:[/bold] [{tier_color}]{tier}[/{tier_color}]\n"
                    f"[bold]Qualified for Shortlist:[/bold] {'[green]Yes[/green]' if is_shortlisted else '[red]No[/red]'}\n\n"
                    f"[bold]Recruiter Assessment:[/bold]\n{node_output.get('recruiter_verdict', '')}\n\n"
                    f"[bold green]Key Strengths:[/bold green]\n{strengths_text}\n\n"
                    f"[bold red]Key Gaps:[/bold red]\n{gaps_text}",
                    title="[bold magenta]Node: Recruiter-Matcher Final Screening[/bold magenta]",
                    border_style="magenta"
                ))

            elif node_name == "referral":
                console.print("[bold green]✓ Referral Node:[/bold green] Generated targeted first-person reach-out message.")

            elif node_name == "save_artifacts":
                console.print(f"[bold dim]✓ Saved artifact to: {node_output.get('saved_file_path')}[/bold dim]\n")

    # --- 7. PostgreSQL Persistence ---
    try:
        save_application_state(final_state)
        console.print("[green]Successfully persisted run artifacts to PostgreSQL.[/green]\n")
    except Exception as e:
        console.print(f"[red]Database write error:[/red] {str(e)}")

    # --- 8. Final Results Display ---
    final_tier = final_state.get("match_tier", "Pending")
    tier_color = _get_tier_color(final_tier)
    console.print(Panel(
        f"[bold]Role:[/bold] {role} at {company}\n"
        f"[bold]Final Match Tier:[/bold] [{tier_color}]{final_tier}[/{tier_color}]\n"
        f"[bold]Status:[/bold] {final_state.get('status', 'COMPLETED')}\n"
        f"[bold]Output File:[/bold] {final_state.get('saved_file_path', 'N/A')}",
        title="[bold green]Pipeline Run Complete[/bold green]",
        border_style="green"
    ))

    if final_state.get("referral_message"):
        console.print(Panel(
            final_state["referral_message"],
            title="[bold cyan]Targeted Referral Outreach Note[/bold cyan]",
            border_style="cyan"
        ))
    else:
        console.print("[dim yellow]Note: Cold referral outreach was not generated because match tier did not meet high-confidence threshold ('High Match' or 'Perfect Match').[/dim yellow]")


if __name__ == "__main__":
    run_cli()
