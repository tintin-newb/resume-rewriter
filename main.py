# main.py
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
    help="Name of the hiring company (e.g., 'Stripe')."
)
@click.option(
    "--job-id", "-j",
    required=True,
    type=str,
    help="Unique requisition ID or code (e.g., 'ENG-4021')."
)
@click.option(
    "--role",
    required=True,
    type=str,
    help="Target job title (e.g., 'Senior Backend Engineer')."
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
    "--min-score",
    type=float,
    default=None,
    help=f"Minimum target score to exit loop (default: {settings.MIN_MATCH_SCORE})."
)
@click.option(
    "--max-loops",
    type=int,
    default=None,
    help=f"Maximum rewriter iterations (default: {settings.MAX_LOOPS})."
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
    min_score: Optional[float],
    max_loops: Optional[int],
    skip_bootstrap: bool
):
    """
    Agentic Resume Rewriter CLI:
    Evaluates resumes against job descriptions, optimizes using action verbs,
    and generates high-impact referrals.
    """
    console.print(Panel.fit(
        "[bold cyan]Agentic Resume Rewriter[/bold cyan]\n"
        "[dim]Evaluator-Optimizer Workflow powered by Ollama & LangGraph[/dim]",
        border_style="cyan"
    ))

    # --- 1. Pre-Flight Health Checks ---
    if not skip_bootstrap:
        bootstrap = SystemBootstrap()
        if not bootstrap.run_checks():
            console.print("[bold red]Bootstrap verification failed. Aborting run.[/bold red]")
            sys.exit(1)

    # --- 2. Database Deduplication & Idempotency Check ---
    existing = get_existing_application(company=company, job_id=job_id)
    if existing and not force:
        console.print(Panel(
            f"[bold yellow]Job posting already evaluated![/bold yellow]\n\n"
            f"[bold]Company:[/bold] {existing['company']}\n"
            f"[bold]Job ID:[/bold] {existing['job_id']}\n"
            f"[bold]Role:[/bold] {existing['role']}\n"
            f"[bold]Last Score:[/bold] {existing['match_score']}/10.0\n"
            f"[bold]Status:[/bold] {existing['status']}\n"
            f"[bold]Saved Resume:[/bold] {existing['rewritten_resume_path']}\n\n"
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

    job_description: str = ""
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
        base_resume_text = resume_parser.parse(resume)
    except Exception as e:
        console.print(f"[bold red]Failed to parse resume:[/bold red] {str(e)}")
        sys.exit(1)

    # --- 5. State Initialization ---
    target_min_score = min_score if min_score is not None else settings.MIN_MATCH_SCORE
    target_max_loops = max_loops if max_loops is not None else settings.MAX_LOOPS

    initial_state: AgentState = {
        "company": company,
        "job_id": job_id,
        "role": role,
        "job_url": url,
        "job_description": job_description,
        "base_resume": base_resume_text,
        "current_resume": base_resume_text,
        "iteration": 1,
        "max_loops": target_max_loops,
        "min_match_score": target_min_score,
        "match_score": 0.0,
        "strengths": [],
        "gaps": [],
        "suggestions": [],
        "is_qualified": False,
        "recruiter_verdict": "",
        "modifications_made": [],
        "referral_message": None,
        "saved_file_path": None,
        "status": "PROCESSING"
    }

    # --- 6. Workflow Execution ---
    console.print("\n[bold magenta]Compiling & executing LangGraph agent pipeline...[/bold magenta]\n")
    workflow = build_workflow()
    final_state: AgentState = workflow.invoke(initial_state)

    # --- 7. PostgreSQL Persistence ---
    try:
        save_application_state(final_state)
        console.print("[green]Successfully persisted run artifacts to PostgreSQL.[/green]\n")
    except Exception as e:
        console.print(f"[red]Database write error:[/red] {str(e)}")

    # --- 8. Final Report Display ---
    score_color = "green" if final_state["match_score"] >= target_min_score else "red"
    console.print(Panel(
        f"[bold]Role:[/bold] {role} at {company}\n"
        f"[bold]Final Match Score:[/bold] [{score_color}]{final_state['match_score']}/10.0[/{score_color}] "
        f"(Target: {target_min_score})\n"
        f"[bold]Status:[/bold] {final_state['status']}\n"
        f"[bold]Output File:[/bold] {final_state['saved_file_path']}\n\n"
        f"[bold]Recruiter Verdict:[/bold]\n{final_state['recruiter_verdict']}",
        title="[bold green]Execution Complete[/bold green]",
        border_style="green"
    ))

    if final_state.get("referral_message"):
        console.print(Panel(
            final_state["referral_message"],
            title="[bold cyan]Targeted Referral Message[/bold cyan]",
            border_style="cyan"
        ))
    else:
        console.print("[yellow]Referral message was not generated because the match score threshold was not reached.[/yellow]")


if __name__ == "__main__":
    run_cli()