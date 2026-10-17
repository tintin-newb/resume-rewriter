#!/usr/bin/env python3
# run_ui.py
"""
Launcher script for Agentic Resume Rewriter Web UI.
Starts FastAPI backend with Uvicorn and opens the web application.
"""
import sys
import webbrowser
import uvicorn
from rich.console import Console
from rich.panel import Panel

from config.settings import get_active_env_file

console = Console()

def main():
    env_file = get_active_env_file()
    
    console.print(Panel.fit(
        f"[bold cyan]⚡ Agentic Resume Rewriter Web UI[/bold cyan]\n"
        f"[dim]Dark-themed local dashboard with live LangGraph streaming[/dim]\n\n"
        f"[bold]Active Configuration File:[/bold] [green]{env_file.resolve()}[/green]\n"
        f"[bold]Dashboard URL:[/bold] [cyan]http://localhost:8000[/cyan]\n\n"
        f"[dim]Press Ctrl+C to stop the server[/dim]",
        border_style="cyan"
    ))

    # Start Uvicorn web server
    uvicorn.run("webapp.server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
