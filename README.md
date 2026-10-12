# Agentic Resume Rewriter

An intelligent, multi-agent CLI application built on the **Evaluator-Optimizer pattern**. It automates ATS resume auditing, iterative resume rewrites using industry-standard action verbs without hallucinations, and high-impact referral reach-out generation.

---

## 1. Introduction

When applying for technical roles, resumes often fail initial automated or human screenings due to passive language, poor visual prioritization, or mismatched phrasing. 

The **Agentic Resume Rewriter** addresses this by orchestrating a feedback loop between specialized AI agents powered by local LLMs via Ollama:
- **Recruiter Agent (The Evaluator):** Acts as a cold, deterministic (`temperature = 0`) ATS screener. It audits candidate alignment against a target Job Description (JD), identifies gaps, highlights strengths, and outputs an objective match score (1–10).
- **Re-writer Agent (The Optimizer):** Ingests the recruiter's critique and a curated bank of categorized action verbs (parsed from reference PDFs). It iteratively rewrites resume bullet points using active voice, impact metrics, and prioritized ordering—**strictly bound by a zero-hallucination policy** that forbids fabricating experience.
- **Referral Generator Agent:** Automatically triggers once the match score meets the qualification threshold to draft a concise, high-converting outreach message for LinkedIn or email.
- **Postgres Persistence & Caching:** Prevents redundant compute by caching application runs by Company and Job ID, supporting a `--force` flag for intentional re-runs.

---

## 2. Directory Structure & Module Breakdown

```text
resume_rewriter/
├── config/
│   ├── __init__.py
│   └── settings.py              # Pydantic Settings loading configurations from .env
├── db/
│   ├── __init__.py
│   ├── schema.sql               # PostgreSQL DDL schema definition
│   ├── connection.py            # Database client and connection verification
│   └── operations.py            # Read/write queries, caching, and state persistence
├── parsers/
│   ├── __init__.py
│   ├── base.py                  # Abstract Base Class for document parsing (BaseDocumentParser)
│   ├── resume_parser.py         # Multi-format parser for PDF, Markdown, and TXT resumes
│   └── verb_parser.py           # Specialized PDF parser extracting action verbs into memory
├── scrapers/
│   ├── __init__.py
│   └── jd_scraper.py            # Crawl4AI + BeautifulSoup async scraper for dynamic job boards
├── agents/
│   ├── __init__.py
│   ├── state.py                 # LangGraph AgentState TypedDict definition
│   ├── recruiter.py             # Recruiter evaluator node (temperature = 0)
│   ├── rewriter.py              # Resume optimizer node (action verbs injection)
│   ├── referral.py              # Referral generator node
│   └── workflow.py              # LangGraph StateGraph assembly and loop routing logic
├── data/
│   └── action_verbs.pdf         # Reference PDF with categorized action verbs
├── output/                      # Default destination for generated Markdown resumes
├── bootstrap.py                 # System health-check utility for pre-flight assertions
├── main.py                      # Click-based CLI entry point
├── requirements.txt             # Project dependencies
├── .env.example                 # Template environment variables
└── README.md                    # Project documentation
```

### Module Descriptions
- **`config/settings.py`**: Centralizes configuration (database URLs, Ollama endpoint, default loop limits, and score thresholds) via `pydantic-settings`.
- **`db/`**: Handles database interactions. `schema.sql` manages table creation, while `operations.py` manages deduplication checks and application state updates.
- **`parsers/`**: An extensible document extraction suite. `resume_parser.py` extracts text from `.pdf`, `.md`, and `.txt` files. `verb_parser.py` parses the attached reference PDF into a clean list of strong verbs.
- **`scrapers/jd_scraper.py`**: Uses `Crawl4AI` (headless Chromium) to render JavaScript-heavy ATS sites (Greenhouse, Lever, Workday) and `BeautifulSoup` to strip boilerplate (DOM headers, footers, scripts).
- **`agents/`**: Contains the core intelligence:
  - `state.py`: Defines the typed payload passed through the agent graph.
  - `recruiter.py`, `rewriter.py`, `referral.py`: Individual nodes encapsulating prompts and structured outputs.
  - `workflow.py`: The `StateGraph` that manages the Evaluator-Optimizer loop, early termination conditions, and file exports.
- **`bootstrap.py`**: Validates that external dependencies (PostgreSQL and Ollama) are online and configured before agent execution starts.
- **`main.py`**: The CLI interface. Provides option parsing, status tables, and error diagnostics using `rich`.

---

## 3. Setup Steps

### 3.1. Database Setup (PostgreSQL)

1. Install PostgreSQL through your OS package manager (`brew install postgresql` on macOS, `apt install postgresql` on Ubuntu).
2. Start the service:
   ```bash
   sudo systemctl start postgresql   # Linux
   brew services start postgresql    # macOS
   ```
3. Create the database:
   ```bash
   createdb -U postgres resume_rewriter_db
   ```

#### Initialize the Schema
Run the provided SQL script to build the tables and indexes:
```bash
psql -h localhost -p 5432 -U postgres -d resume_rewriter_db -f db/schema.sql
```

---

### 3.2. Ollama & LLM Setup

The application is configured by default for `qwen2.5:7b`, but works with larger variants (`qwen2.5:14b`, `qwen2.5:32b`) as well.

#### Option A: Native System Service

1. **Install Ollama:**
   - **Linux / macOS:** Run `curl -fsSL https://ollama.com/install.sh | sh`
   - **Windows:** Download the installer from the [official Ollama website](https://ollama.com).
2. **Start the Service:**
   - Ollama usually runs in the background automatically. To start manually:
     ```bash
     ollama serve
     ```
3. **Pull the Model:**
   ```bash
   ollama pull qwen2.5:7b
   ```

#### Option B: Docker Container

##### 1. With GPU Acceleration (NVIDIA)
Ensure you have the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) installed.
```bash
docker run -d \
  --gpus=all \
  -v ollama_storage:/root/.ollama \
  -p 11434:11434 \
  --name ollama_gpu \
  ollama/ollama

# Download the model inside the container
docker exec -it ollama_gpu ollama pull qwen2.5:7b
```

##### 2. CPU Only
```bash
docker run -d \
  -v ollama_storage:/root/.ollama \
  -p 11434:11434 \
  --name ollama_cpu \
  ollama/ollama

# Download the model inside the container
docker exec -it ollama_cpu ollama pull qwen2.5:7b
```

---

### 3.3. Python Environment Setup

Requires **Python 3.10+**.

1. **Clone the repository and set up a virtual environment:**
   ```bash
   git clone <repo-url>
   cd resume_rewriter

   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Python dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Install Crawl4AI Browser Dependencies:**
   `Crawl4AI` requires Playwright headless browser binaries to render dynamic job portals:
   ```bash
   playwright install chromium
   ```

---

### 3.4. Environment Variables (`.env`)

Create your `.env` configuration file from the provided template:
```bash
cp .env.example .env
```

Edit `.env` to match your environment:
```ini
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# PostgreSQL Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=resume_rewriter_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Optimization Loop Guardrails
MIN_MATCH_SCORE=8.0
MAX_LOOPS=3

# Default File Paths
DEFAULT_ACTION_VERBS_PATH=data/action_verbs.pdf
OUTPUT_DIR=output/
```

| Variable | Description |
| :--- | :--- |
| `OLLAMA_BASE_URL` | Endpoint of the Ollama server (native or container). |
| `OLLAMA_MODEL` | Local LLM tag (e.g., `qwen2.5:7b`, `qwen2.5:14b`). |
| `POSTGRES_*` | Connection credentials for the application database. |
| `MIN_MATCH_SCORE` | Score (1.0 to 10.0) that satisfies the loop and triggers the referral agent. |
| `MAX_LOOPS` | Circuit breaker limit preventing infinite optimizer iterations. |
| `DEFAULT_ACTION_VERBS_PATH`| Path to the PDF listing power action verbs. |
| `OUTPUT_DIR` | Directory where optimized Markdown resumes are saved. |

---

## 4. Run Methodology

### Step 1: Run Pre-flight Health Checks
Before starting a full run, verify that your local systems (PostgreSQL, Ollama, model availability) are operational:
```bash
python bootstrap.py
```
If any system is unreachable or uninitialized, the diagnostic table will highlight the problem with troubleshooting steps.

---

### Step 2: Running the CLI (`main.py`)

#### Command Line Options
```text
Options:
  -r, --resume PATH       Path to base candidate resume (.pdf, .md, .txt) [required]
  -c, --company TEXT      Name of the hiring company [required]
  -j, --job-id TEXT       Unique requisition ID or code [required]
  --role TEXT             Target job title [required]
  -u, --url TEXT          Public URL to job posting (scraped via Crawl4AI)
  --jd-file PATH          Local path to a text/markdown file containing the JD
  -f, --force             Force re-execution even if already cached in DB
  --min-score FLOAT       Target score threshold to exit loop (default: 8.0)
  --max-loops INTEGER     Maximum optimizer iterations (default: 3)
  --verbs-pdf PATH        Path to custom action verbs reference PDF
  --skip-bootstrap        Skip pre-flight system checks
  --help                  Show this help message and exit.
```

---

### Step 3: Common Execution Scenarios

#### Scenario A: Using a Live Job Posting URL
```bash
python main.py \
  --resume "data/my_base_resume.pdf" \
  --company "Datadog" \
  --job-id "ENG-4491" \
  --role "Senior Backend Engineer" \
  --url "https://careers.datadog.com/detail/12345"
```
*The scraper launches a headless Chromium instance, strips web noise, passes the text to the Recruiter Agent, runs the rewrite loop, and saves the Markdown resume under `output/`.*

#### Scenario B: Using a Local Job Description File
Useful when applying to private job portals or internal transfers:
```bash
python main.py \
  --resume "data/my_base_resume.md" \
  --company "Stripe" \
  --job-id "REQ-9920" \
  --role "Staff Infrastructure Engineer" \
  --jd-file "data/stripe_jd.txt" \
  --min-score 8.5 \
  --max-loops 2
```

#### Scenario C: Idempotency Caching & Overriding (`--force`)
If you run the CLI with an identical `--company` and `--job-id` combination:
```bash
# 1. Normal run (Returns cached score, saved file path, and referral message immediately)
python main.py \
  --resume "data/my_base_resume.md" \
  --company "Stripe" \
  --job-id "REQ-9920" \
  --role "Staff Infrastructure Engineer" \
  --jd-file "data/stripe_jd.txt"

# 2. Forced re-run (Bypasses cache, clears old result, and re-executes the agent loop)
python main.py \
  --resume "data/my_base_resume.md" \
  --company "Stripe" \
  --job-id "REQ-9920" \
  --role "Staff Infrastructure Engineer" \
  --jd-file "data/stripe_jd.txt" \
  --force
```

---

## 5. Output Artifacts

Upon completion of a successful run:
1. **Optimized Resume File**: A structured Markdown resume is generated at:
   ```text
   output/<Company>_<JobID>_resume.md
   ```
2. **Referral Message**: If the match threshold was met, a customized reach-out message is printed directly to the terminal for easy copying.
3. **Database Record**: All execution details (match score, final status, file paths, and referral messages) are updated in the `job_applications` PostgreSQL table.