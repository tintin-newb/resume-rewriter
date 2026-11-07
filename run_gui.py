#!/usr/bin/env python3
"""
Launcher script for Agentic Resume Rewriter Web UI.
Starts FastAPI backend with Uvicorn and launches the web application dashboard.
"""
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional
import click
import uvicorn
from rich.console import Console
from rich.panel import Panel

from config.settings import get_active_env_file, settings
from bootstrap import SystemBootstrap

console = Console()


def _open_browser_after_delay(url: str, delay: float = 1.2):
    """Opens the web browser in a background thread once the server starts."""
    def _worker():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


@click.command()
@click.option(
    "--port", "-p",
    type=int,
    default=8000,
    show_default=True,
    help="Port to bind the web server to."
)
@click.option(
    "--host", "-h",
    type=str,
    default="0.0.0.0",
    show_default=True,
    help="Host address to bind the web server to."
)
@click.option(
    "--open-browser/--no-browser",
    default=True,
    show_default=True,
    help="Automatically open the dashboard in your default browser."
)
@click.option(
    "--reload/--no-reload",
    default=True,
    show_default=True,
    help="Enable auto-reload on code modifications."
)
@click.option(
    "--skip-bootstrap",
    is_flag=True,
    default=False,
    help="Skip pre-flight service checks for Ollama and PostgreSQL."
)
def run_gui(port: int, host: str, open_browser: bool, reload: bool, skip_bootstrap: bool):
    """
    Launches the Agentic Resume Rewriter Web Dashboard.
    Decomposed Section-by-Section Evaluator-Optimizer Architecture.
    """
    env_file = get_active_env_file()
    display_url = f"http://localhost:{port}" if host in ("0.0.0.0", "127.0.0.1") else f"http://{host}:{port}"

    console.print(Panel.fit(
        f"[bold cyan]⚡ Agentic Resume Rewriter Web Dashboard[/bold cyan]\n"
        f"[dim]Decomposed Section-by-Section Evaluator-Optimizer Architecture[/dim]\n\n"
        f"[bold]Active Configuration File:[/bold] [green]{env_file.resolve()}[/green]\n"
        f"[bold]Web Dashboard URL:[/bold] [bold cyan]{display_url}[/bold cyan]\n"
        f"[bold]Active Agents:[/bold] [dim]Extractor ➔ Observer ➔ Rewriter ➔ Stitcher ➔ Matcher ➔ Referral[/dim]\n\n"
        f"[dim]Press [bold red]Ctrl+C[/bold red] to stop the server[/dim]",
        border_style="cyan"
    ))

    # Optional Pre-flight checks
    if not skip_bootstrap:
        bootstrap = SystemBootstrap()
        pg_ok, pg_msg = bootstrap.check_postgres()
        ollama_ok, ollama_msg = bootstrap.check_ollama_and_model()

        if pg_ok and ollama_ok:
            console.print("[green]✓ System Services Online:[/green] PostgreSQL and Ollama model ready.\n")
        else:
            if not pg_ok:
                console.print(f"[yellow]⚠ PostgreSQL Warning:[/yellow] {pg_msg}")
            if not ollama_ok:
                console.print(f"[yellow]⚠ Ollama Warning:[/yellow] {ollama_msg}")
            console.print("[dim]Web UI will still launch; you can test and adjust credentials in System Settings.[/dim]\n")

    if open_browser:
        _open_browser_after_delay(display_url)

    # Launch Uvicorn
    uvicorn.run(
        "webapp.server:app",
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    run_gui()
