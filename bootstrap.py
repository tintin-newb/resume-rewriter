# bootstrap.py
import sys
import psycopg
import ollama
from rich.console import Console
from rich.table import Table

from config.settings import settings

console = Console()

class SystemBootstrap:
    def __init__(self):
        self.settings = settings
        self.ollama_client = ollama.Client(host=self.settings.OLLAMA_BASE_URL)

    def check_postgres(self) -> tuple[bool, str]:
        """Validates Postgres connectivity and table existence."""
        try:
            with psycopg.connect(self.settings.postgres_dsn, connect_timeout=3) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'job_applications'
                        );
                    """)
                    table_exists = cur.fetchone()[0]

            if not table_exists:
                return False, "Database connected, but 'job_applications' table is missing. Run schema.sql."
            return True, "Connected (Table 'job_applications' present)"

        except Exception as e:
            return False, f"PostgreSQL connection failed: {str(e)}"

    def check_ollama_and_model(self) -> tuple[bool, str]:
        """Validates Ollama connectivity and model availability."""
        try:
            available_models_resp = self.ollama_client.list()
            # Handle both object attributes and dict responses
            models_list = (
                available_models_resp.models 
                if hasattr(available_models_resp, 'models') 
                else available_models_resp.get('models', [])
            )
            
            names = []
            for m in models_list:
                name = m.model if hasattr(m, 'model') else m.get('name') or m.get('model')
                if name:
                    names.append(name.split(':')[0])  # Match base tag e.g. qwen2.5
                    names.append(name)                 # Match full tag e.g. qwen2.5:7b

            target_model = self.settings.OLLAMA_MODEL
            target_base = target_model.split(':')[0]

            if target_model in names or target_base in names:
                return True, f"Online (Model '{target_model}' ready)"
            else:
                return False, f"Ollama is running, but model '{target_model}' is not pulled. Run `ollama pull {target_model}`."

        except Exception as e:
            return False, f"Ollama server unreachable at {self.settings.OLLAMA_BASE_URL}: {str(e)}"

    def ensure_output_directory(self) -> tuple[bool, str]:
        try:
            self.settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            return True, f"Ready ({self.settings.OUTPUT_DIR.resolve()})"
        except Exception as e:
            return False, f"Could not create output directory: {str(e)}"

    def run_checks(self) -> bool:
        console.print("\n[bold cyan]=== Agentic Resume Rewriter: System Health Check ===[/bold cyan]\n")
        
        checks = [
            ("PostgreSQL Service", self.check_postgres),
            ("Ollama & Model Readiness", self.check_ollama_and_model),
            ("Output Storage Path", self.ensure_output_directory),
        ]

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Component", width=25)
        table.add_column("Status", width=10)
        table.add_column("Details", justify="left")

        all_passed = True
        for name, check_fn in checks:
            passed, detail = check_fn()
            status_text = "[green]OK[/green]" if passed else "[red]FAIL[/red]"
            table.add_row(name, status_text, detail)
            if not passed:
                all_passed = False

        console.print(table)
        console.print()

        if not all_passed:
            console.print("[bold red]Pre-flight checks failed. Please fix the reported issues before proceeding.[/bold red]\n")
            return False

        console.print("[bold green]All systems healthy and ready for agent orchestration.[/bold green]\n")
        return True


if __name__ == "__main__":
    bootstrap = SystemBootstrap()
    if not bootstrap.run_checks():
        sys.exit(1)