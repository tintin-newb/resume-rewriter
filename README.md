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

## 2. System Architecture

The following diagram illustrates the main components of the application and how they communicate across ingestion, orchestration, persistence, and local LLM inference:

```mermaid
flowchart TD
    %% User Interfaces / Clients
    subgraph Clients["1. User Interfaces"]
        CLI["CLI Interface<br/>(run_cli.py)"]
        WEB["Web Dashboard<br/>(FastAPI + SSE)"]
    end

    %% Ingestion Layer
    subgraph Ingestion["2. Ingestion & Parsing"]
        RP["Resume Parser<br/>(PDF, MD, TXT, DOCX)"]
        JDS["JD Scraper<br/>(Crawl4AI / BeautifulSoup)"]
    end

    %% Core Multi-Agent Orchestration
    subgraph Agents["3. LangGraph Multi-Agent Core"]
        REC["Recruiter Agent<br/>(Evaluator, temp = 0)"]
        DEC{"Target Match<br/>Achieved?"}
        REW["Re-writer Agent<br/>(Optimizer + Action Verbs)"]
        REF["Referral Generator<br/>(Outreach Draft)"]
    end

    %% Storage & External Infrastructure
    subgraph Storage["4. Storage & LLM Infrastructure"]
        OLLAMA[("Ollama LLM Engine<br/>(Local Inference: qwen2.5)")]
        DB[("PostgreSQL Database<br/>(Run Cache & History)")]
        OUT["Output Resumes<br/>(output/ & uploads/)"]
    end

    %% Client communication
    CLI -->|"Base Resume"| RP
    CLI -->|"Job URL / Text"| JDS
    WEB -->|"Base Resume"| RP
    WEB -->|"Job URL / Text"| JDS
    CLI <-.->|"Check Cache / Save Run"| DB
    WEB <-.->|"Check Cache / Save Run"| DB

    %% Ingestion to Agents
    RP -->|"Parsed Candidate Text"| REC
    JDS -->|"Parsed Job Description"| REC

    %% Evaluator-Optimizer Feedback Loop
    REC -->|"Audit Verdict & Tier"| DEC
    DEC -->|"No (Within Max Loops)"| REW
    REW -->|"Tailored Bullets"| REC

    %% Workflow Completion
    DEC -->|"Yes (High / Perfect Match)"| REF
    DEC -->|"Max Loops Reached"| OUT
    REF -->|"Referral Message"| OUT
    OUT -.->|"Persist File Path"| DB

    %% LLM Invocations
    REC <-.->|"Prompt & Evaluation"| OLLAMA
    REW <-.->|"Prompt & Rewrites"| OLLAMA
    REF <-.->|"Prompt & Outreach"| OLLAMA
```

### Component Communication Breakdown

- **User Interfaces (`run_cli.py` & `webapp/`)**: Accepts candidate resumes and job inputs (URL or raw text). Coordinates pre-flight health checks and performs instant cache lookups against PostgreSQL (`Company` + `Job ID`) to avoid redundant LLM invocations unless `--force` is specified.
- **Ingestion & Parsing (`parsers/` & `scrapers/`)**: `ResumeParser` extracts normalized text from `.pdf`, `.md`, `.txt`, and `.docx` documents. `JDScraper` uses Crawl4AI (headless Chromium) with JSON-LD schema parsing and SPA delay handling to extract clean job postings from career sites or local files.
- **LangGraph Multi-Agent Core (`agents/`)**: Manages the Evaluator-Optimizer feedback loop via `StateGraph`:
  - **Recruiter Agent (Evaluator):** Deterministically (`temperature = 0`) compares candidate qualifications against JD requirements, producing structured gap analyses, strengths, and a categorical match tier.
  - **Decision Router (`should_continue`):** Evaluates if the match tier qualifies as passing (`High Match` or `Perfect Match`) or if `max_loops` has been reached.
  - **Re-writer Agent (Optimizer):** Takes recruiter feedback and a curated action verb taxonomy to rewrite bullets using active voice and metrics without fabricating facts (zero-hallucination constraint), then routes back to the Recruiter.
  - **Referral Generator Agent:** When target qualification is reached, drafts an outreach message for LinkedIn or email.
- **Storage & External Infrastructure**:
  - **Ollama**: Provides private local inference for LLM prompts across all agent nodes.
  - **PostgreSQL**: Stores execution state, audit logs, and history for the web archive.
  - **Output Artifacts**: Saves the final optimized Markdown resume to `output/<Company>_<JobID>_resume.md` and user uploads to `~/.resume-rewriter/uploads/`.

### Tech Stack & System Specifications

#### Technology Stack & Versions
| Category | Component / Library | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Runtime** | Python | `3.10.12` | Core programming language runtime |
| **Agent Framework** | LangGraph | `1.2.15` | StateGraph orchestrator & cyclic Evaluator-Optimizer loop |
| **LLM Orchestration** | LangChain Core | `1.6.12` | Prompt templates, structured outputs, and chain execution |
| **LLM Integration** | LangChain-Ollama | `1.1.0` | Integration layer between LangChain and local Ollama |
| **Local LLM Engine** | Ollama | `0.40.5` | Local model inference hosting (`qwen2.5:7b` / `qwen2.5:14b`) |
| **Database** | PostgreSQL (`psql`) | `14.24` | Application state persistence, run history, and caching |
| **Database Driver** | Psycopg 3 | `3.2.0+` | PostgreSQL database adapter for Python |
| **Web Framework** | FastAPI | `0.143.3` | REST endpoints and Server-Sent Events (SSE) streaming |
| **ASGI Server** | Uvicorn | `0.54.0` | High-performance ASGI web server |
| **Web Scraping** | Playwright (Crawl4AI) | `1.64.0` | Dynamic headless Chromium browser rendering & job scraping |
| **HTML Parsing** | BeautifulSoup4 | `4.12.0+` | DOM extraction, text cleanup, and JSON-LD schema parsing |
| **Document Parsing** | PyPDF | `5.0.0+` | Candidate resume PDF parsing and text extraction |
| **CLI Framework** | Click | `8.5.0` | CLI argument and option parsing |
| **Terminal UI** | Rich | `15.0.0` | Terminal formatting, progress indicators, tables, and panels |
| **Configuration** | Pydantic / Pydantic-Settings | `2.14.1` / `2.15.0` | Typed settings management and environment loading |
| **Containerization** | Docker | `28.3.2` | Container platform for multi-container deployment |

#### Tested System Specifications (Hardware & Host OS)
| Specification | Details |
| :--- | :--- |
| **Operating System** | Ubuntu 22.04.5 LTS (x86_64, Linux Kernel `6.8.0-138-generic`) |
| **CPU** | 12th Gen Intel(R) Core(TM) i7-12700H (14 Cores / 20 Threads, up to 4.70 GHz) |
| **System Memory (RAM)** | 32 GB DDR (30 GiB usable) |
| **GPU / Acceleration** | NVIDIA RTX A2000 8GB Laptop GPU (Driver `570.158.01`, CUDA `12.8`) |
| **Storage Requirement** | ~15 GB free disk space (includes Playwright Chromium browser and local LLM weights) |

---

## 3. Directory Structure & Module Breakdown

```text
resume_rewriter/
├── config/
│   ├── __init__.py
│   ├── action_verbs.py          # Action verb taxonomy and categorized mappings
│   └── settings.py              # Dynamic configuration manager (supports ~/.resume-rewriter/config.env)
├── db/
│   ├── __init__.py
│   ├── schema.sql               # PostgreSQL DDL schema definition
│   ├── connection.py            # Database client and connection verification
│   └── operations.py            # Read/write queries, caching, history pagination, and state persistence
├── docker/                      # Containerization and multi-container deployment
│   ├── Dockerfile               # Slim Python 3.10 runtime with Playwright Chromium
│   ├── docker-compose.yml       # Orchestrates web app and GPU-accelerated Ollama
│   └── build.sh                 # Build script to generate container image
├── parsers/
│   ├── __init__.py
│   ├── base.py                  # Abstract Base Class for document parsing (BaseDocumentParser)
│   └── resume_parser.py         # Multi-format parser for PDF, Markdown, and TXT resumes
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
├── webapp/                      # Web application backend and frontend assets
│   ├── __init__.py
│   ├── server.py                # FastAPI REST API and static file server
│   ├── pipeline_runner.py       # Background worker and Server-Sent Events (SSE) stream manager
│   └── assets/                  # Frontend single-page app assets
│       ├── html/index.html      # Responsive Dark Mode dashboard
│       ├── css/style.css        # Slate/cyan design system and glassmorphism styling
│       └── js/app.js            # Independent tab logic, SSE stream consumer, and lazy loader
├── output/                      # Default destination for generated Markdown resumes
├── bootstrap.py                 # System health-check utility with intelligent localhost fallback
├── run_gui.py                    # Root entry point to launch the interactive Web UI
├── run_cli.py                      # Click-based CLI entry point
├── requirements.txt             # Project dependencies
├── .dockerignore                # Build context allowlist filter
├── .env.example                 # Template environment variables
└── README.md                    # Project documentation
```

### Module Descriptions
- **`config/settings.py`**: Centralizes configuration (database URLs, Ollama endpoint, default loop limits, and score thresholds) via `pydantic-settings`. Prioritizes user configuration in `~/.resume-rewriter/config.env` and supports hot-reloading.
- **`db/`**: Handles database interactions. `schema.sql` manages table creation with columns for `source_resume_path` and `recruiter_verdict`. `operations.py` manages deduplication checks, cursor-based history pagination, and application state updates.
- **`docker/`**: Contains containerization and deployment assets. `Dockerfile` packages the application on a slim Python 3.10 runtime with Playwright Chromium; `docker-compose.yml` orchestrates the web dashboard alongside a GPU-accelerated Ollama container; and `build.sh` automates image compilation.
- **`parsers/`**: An extensible document extraction suite. `resume_parser.py` extracts text from `.pdf`, `.md`, and `.txt` files.
- **`scrapers/jd_scraper.py`**: Robust crawler built on `Crawl4AI` (headless Chromium) and `BeautifulSoup`. Features automatic extraction of structured `JobPosting` schema (`application/ld+json`), SPA render delay support, and heuristic DOM fallback to handle modern ATS platforms (Workday, Phenom People, Greenhouse, Lever).
- **`agents/`**: Contains the core intelligence:
  - `state.py`: Defines the typed payload passed through the agent graph.
  - `recruiter.py`, `rewriter.py`, `referral.py`: Individual nodes encapsulating prompts and structured outputs.
  - `workflow.py`: The `StateGraph` that manages the Evaluator-Optimizer loop, early termination conditions, and file exports.
- **`webapp/`**: Encapsulates the Web UI server and frontend. `server.py` provides REST and SSE streaming endpoints; `pipeline_runner.py` decouples LLM execution into non-blocking background tasks; `assets/` contains the vanilla HTML, CSS, and JS.
- **`run_gui.py`**: The clean root launcher to start the Web UI dashboard on `http://localhost:8000`.
- **`bootstrap.py`**: Validates that external dependencies (PostgreSQL and Ollama) are online and configured before agent execution starts, with automatic fallback resolution between `host.docker.internal` and `localhost`.
- **`run_cli.py`**: The CLI interface. Provides option parsing, status tables, and error diagnostics using `rich`.

---

## 4. Setup Steps

### 4.1. Database Setup (PostgreSQL)

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

### 4.2. Ollama & LLM Setup

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

### 4.3. Python Environment Setup

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

### 4.4. Environment Variables (`.env`)

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
MAX_LOOPS=3
```

| Variable | Description |
| :--- | :--- |
| `OLLAMA_BASE_URL` | Endpoint of the Ollama server (native or container). |
| `OLLAMA_MODEL` | Local LLM tag (e.g., `qwen2.5:7b`, `qwen2.5:14b`). |
| `POSTGRES_*` | Connection credentials for the application database. |
| `MAX_LOOPS` | Circuit breaker limit preventing infinite optimizer iterations. |

---

### 4.5. Docker Build & Deployment

As an alternative to native local Python setup, you can build and run the application and its LLM backend using Docker and Docker Compose.

#### 1. Build the Application Image
The container uses `python:3.10-slim` and installs all project requirements along with Playwright Chromium for web scraping. Run `build.sh` from the `docker/` directory:

```bash
cd docker
./build.sh
```
This builds and tags the image as `resume-rewriter:latest` using the repository root as the build context.

#### 2. Deploy with Docker Compose
Deploy both the Web UI and the Ollama service with NVIDIA GPU support:

```bash
# From the docker/ directory
docker compose up -d
```
*(Or from the repository root: `docker compose -f docker/docker-compose.yml up -d`)*

#### Services in `docker-compose.yml`:
* **`web`**: Runs `run_gui.py` on port `8000`. Maps `host.docker.internal` to `host-gateway` so the container can communicate with services running on the host machine. Mounts `~/.resume-rewriter` to `/root/.resume-rewriter` to persist uploaded resumes and user settings.
* **`ollama_gpu`**: Runs the official `ollama/ollama` image with NVIDIA GPU acceleration (`--gpus all`) on port `11434`, storing models persistently in the `ollama_storage` volume.

#### 3. Pull Model in Containerized Ollama
If using the containerized `ollama_gpu` service, pull your preferred model once the container is running:
```bash
docker exec -it ollama_gpu ollama pull qwen2.5:7b
```

#### 4. Access the Web Dashboard
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

#### 5. Stop the Containers
```bash
# From the docker/ directory
docker compose down
```

---

## 5. Run Methodology

### Step 1: Run Pre-flight Health Checks
Before starting a full run, verify that your local systems (PostgreSQL, Ollama, model availability) are operational:
```bash
python bootstrap.py
```
If any system is unreachable or uninitialized, the diagnostic table will highlight the problem with troubleshooting steps.

---

### Step 2: Running the CLI (`run_cli.py`)

#### Command Line Options
```text
Options:
  -r, --resume PATH        Path to base candidate resume (.pdf, .md, .txt, or
                           .docx).  [required]
  -c, --company TEXT       Name of the hiring company (e.g., 'Stripe').
                           [required]
  -j, --job-id TEXT        Unique requisition ID or code (e.g., 'ENG-4021').
                           [required]
  --role TEXT              Target job title (e.g., 'Senior Backend Engineer').
                           [required]
  -u, --url TEXT           Public URL to the job posting (scraped via
                           Crawl4AI).
  --jd-file PATH           Local path to a text/markdown file containing the
                           JD.
  -f, --force              Force re-execution even if the job posting was
                           already processed in the database.
  --min-score FLOAT        Minimum target score to exit loop (default: 8.0).
  --max-loops INTEGER      Maximum rewriter iterations (default: 3).
  --skip-bootstrap         Skip pre-flight health checks for Ollama and
                           PostgreSQL.
  -i, --instructions TEXT  Auxiliary instructions/guidance for Recruiter
                           evaluation and Re-writer tailoring (accepts a
                           string or path to a .txt file).
  --help                   Show this message and exit.
```

---

### Step 3: Common Execution Scenarios

#### Scenario A: Using a Live Job Posting URL
```bash
python run_cli.py \
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
python run_cli.py \
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
python run_cli.py \
  --resume "data/my_base_resume.md" \
  --company "Stripe" \
  --job-id "REQ-9920" \
  --role "Staff Infrastructure Engineer" \
  --jd-file "data/stripe_jd.txt"

# 2. Forced re-run (Bypasses cache, clears old result, and re-executes the agent loop)
python run_cli.py \
  --resume "data/my_base_resume.md" \
  --company "Stripe" \
  --job-id "REQ-9920" \
  --role "Staff Infrastructure Engineer" \
  --jd-file "data/stripe_jd.txt" \
  --force
```

#### Scenario D: Providing Auxiliary Guidance & Tone Instructions
Provide custom focus areas, role-specific nuances, or tone directives (as an inline string or path to a `.txt` file):
```bash
python run_cli.py \
  --resume "data/my_base_resume.pdf" \
  --company "Adobe" \
  --job-id "R171487" \
  --role "Machine Learning Engineer" \
  --url "https://careers.adobe.com/us/en/job/ADOBUSR171487EXTERNALENUS/Machine-Learning-Engineer-3" \
  --instructions "Prioritize transformer model training and distributed PyTorch pipelines; emphasize production ML engineering rather than research."
```

---

## 6. Output Artifacts

Upon completion of a successful run:
1. **Optimized Resume File**: A structured Markdown resume is generated at:
   ```text
   output/<Company>_<JobID>_resume.md
   ```
2. **Referral Message**: If the match threshold was met, a customized reach-out message is printed directly to the terminal for easy copying.
3. **Database Record**: All execution details (match score, final status, file paths, and referral messages) are updated in the `job_applications` PostgreSQL table.

---

## 7. Interactive Web UI Dashboard

A modern, dark-themed Web UI is available to interactively tailor resumes and review history:

```bash
python run_gui.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

### Key Features
* **Tab 1: Generate Resume (Live Pipeline Stream):**
  * Drag & drop candidate base resume (`.pdf`, `.md`, `.txt`, `.docx`) — automatically saved to `~/.resume-rewriter/uploads/` for side-by-side version comparison.
  * Enter Target Company, Requisition ID, and Target Role.
  * Ingest Job Description via **URL Web Scrape** (Crawl4AI with JSON-LD schema parsing and SPA render delays) or **Direct Text / Paste**.
  * **Auxiliary Instructions / Guidance (Optional):** Stateless per-run guidance to steer the Recruiter evaluation criteria and Re-writer optimization (e.g. tone directives, technical focus, or specific experience to emphasize).
  * Real-time Server-Sent Events (SSE) stepper reflecting each stage of the LangGraph agent pipeline: Pre-flight Bootstrap, Cache Verification, Content Ingestion, Recruiter Audit rounds (with Match Tier badge, strengths, gaps, and verdict), Re-writer Optimization passes, Referral Outreach, and Artifact saving.
* **Tab 2: History (Interactive Run Archive):**
  * **Fully Independent:** Switching between tabs does not disrupt an ongoing generation task.
  * **Lazy Loading:** Automatically fetches past applications sorted newest-first in batches of 15 records as you scroll.
  * **Search Bar:** Instantly filter runs by Company, Role, or Requisition ID.
  * **Inspection Modal:** Click any card to review full Job Details, the Recruiter Audit Verdict, and the drafted Referral Message (with 1-click clipboard copy).
  * **Document Viewer:** Switch between **Rewritten Resume**, **Original Upload**, and a **Side-by-Side Comparison Diff** with full Markdown syntax highlighting and PDF preview.
* **System Settings Drawer (Top-Right Gear Icon):**
  * Edit Ollama host/model, PostgreSQL credentials, and pipeline parameters directly from the browser.
  * Persisted to `~/.resume-rewriter/config.env` and reused across all runs without needing to touch project files or restart the server.
  * **Test Connections:** Live connectivity validator for PostgreSQL and Ollama with status indicators.

---

## 8. Troubleshooting & FAQs

### 8.1. "Service Issue" Status Badge in UI
* **Ollama Host Resolution:** On native Linux, Ollama runs on `http://localhost:11434` (or `http://127.0.0.1:11434`), while `http://host.docker.internal:11434` is only routable inside Docker containers. `bootstrap.py` automatically resolves and falls back to `localhost:11434`.
* **Hovering Details:** Hover over or click the health pill in the top header (`System Ready` / `Service Issue`) to see exact diagnostic messages for both PostgreSQL and Ollama.
* **Model Readiness:** Ensure the model specified in settings (e.g. `qwen2.5:7b` or `qwen3:8b`) is pulled locally via `ollama pull <model-name>`.

### 8.2. PostgreSQL Connection Failures
* Ensure PostgreSQL is running (`sudo systemctl status postgresql` or `pg_isready`).
* Verify that the database and user match your `~/.resume-rewriter/config.env` settings.
* Test connectivity using `./env_rr/bin/python bootstrap.py` or the **Test Connections** button in the Web UI Settings drawer.

### 8.3. Force Re-running Cached Applications
* If an application was already evaluated for a given Company and Job ID, the system caches the result to avoid redundant compute.
* In the CLI: Add the `--force` / `-f` flag.
* In the Web UI: Expand the **Advanced Run Configuration** accordion and check **Force re-execution if cached**.