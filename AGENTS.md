# AGENTS.md

This file provides context for AI coding agents operating in this repository.

## Project Overview

A Python research project for detecting **CISB (Compiler-Introduced Security Bugs)** using
LLM-based multi-agent pipelines. The system analyzes bug reports from GCC Bugzilla, LLVM
GitHub Issues, and Linux kernel git commits to determine whether compiler optimizations
introduced security-relevant bugs.

This project is part of a **postgraduate graduation project**, which is outlined in outline.pdf.

**Language:** Python 3.13 (no package structure — no `__init__.py`, `setup.py`, or `pyproject.toml`)

**PDF Skill:** The `pdf` skill is declared for this project (see `.opencode/oh-my-opencode.json`).
It is installed globally at `~/.config/opencode/skills/pdf/`. When working with `outline.pdf`
or any other PDF files in this project, include `load_skills=["pdf"]` in task delegations.
The skill covers text extraction, table extraction, OCR, PDF creation, and form filling using
`pypdf`, `pdfplumber`, `reportlab`, and `pytesseract`.

**Dependencies** (inferred from imports — there is no `requirements.txt`):
- `openai` — OpenAI Python SDK for LLM API calls
- `requests` — HTTP requests (GitHub API, Bugzilla)
- `beautifulsoup4` (`bs4`) — HTML scraping of GCC Bugzilla
- Standard library: `json`, `os`, `sys`, `re`, `subprocess`, `time`, `urllib.parse`

## Repository Structure

```
cisb-llm/
├── agents/                  # Core multi-agent LLM pipeline
│   ├── agent.py             # Abstract base class for all agents
│   ├── digestor.py          # Extracts/structures bug report information
│   ├── reasoner.py          # Analyzes code for CISB using chain-of-thought
│   ├── helper.py            # File I/O utility class
│   └── wrapper.py           # Orchestrator: Digestor -> Reasoner pipeline
├── datasets/                # Bug IDs and scraped bug report JSON data
│   ├── Todos/               # Active datasets (bug_ids.txt, bug_reports.json)
│   └── backups/             # Backup copies
├── results/                 # Evaluation results
├── scratch.py               # GCC Bugzilla scraper
├── llvm_scratch.py          # LLVM GitHub Issues scraper
├── kernel_api.py            # Linux kernel commit fetcher (GitHub API)
├── kernel_gitshow.py        # Linux kernel commit fetcher (local git show)
└── README.md                # Project documentation (Chinese)
```

## Build / Lint / Test Commands

**There is no formal build system, test framework, linter, or CI/CD pipeline.**

### Running Scripts

All scripts are run directly with Python. The `agents/` directory scripts use bare imports
and must be run from within that directory:

```bash
# Run the full pipeline (Digestor -> Reasoner)
cd agents && python wrapper.py

# Run individual agents for manual testing
cd agents && python digestor.py
cd agents && python reasoner.py

# Run data collection scripts (from project root)
python scratch.py          # GCC Bugzilla scraper
python llvm_scratch.py     # LLVM Issues scraper
python kernel_api.py       # Kernel commits via GitHub API
python kernel_gitshow.py   # Kernel commits via local git
```

### Testing

There are no automated tests (no pytest, unittest, or any test framework). Each agent class
has a `.test(bug_id)` method that performs a manual integration test by making real LLM API
calls and writing results to files. These require live API credentials configured in the
`if __name__ == "__main__"` block of each file.

There are no assert statements, mocking, or test isolation anywhere in the codebase.

### Linting / Formatting / Type Checking

No linting, formatting, or type-checking tools are configured. There is no `.editorconfig`,
no ruff/flake8/pylint config, no black/autopep8 config, and no mypy/pyright config.

## Architecture

The pipeline follows this flow:

1. **Data Collection** — standalone scripts scrape bug reports from GCC Bugzilla, LLVM
   GitHub Issues, or Linux kernel commits
2. **Digestor** — processes raw bug report data into structured JSON digests
3. **Reasoner** — applies chain-of-thought reasoning to determine if a bug is a CISB
4. **Evaluator** (deprecated) — was intended to validate the Reasoner's analysis

The `Wrapper` class orchestrates the Digestor -> Reasoner pipeline. Two platform modes
exist: `bugzilla` (GCC bugs) and `kernel` (Linux kernel commits), each with tailored prompts.

LLM integration uses the OpenAI Python SDK with configurable `base_url` (supports DeepSeek
and other API-compatible providers). Both streaming and non-streaming responses are supported.

## Code Style Guidelines

### Imports

- Standard library imports first, then third-party, then local (not rigidly enforced).
- Named imports preferred: `from openai import OpenAI`, `from bs4 import BeautifulSoup`.
- Local imports use bare module names (no package prefix): `from agent import Agent`.
- Both `import json` and `from os import system` styles are used for stdlib.

### Naming Conventions

- **Classes:** `PascalCase` — `Agent`, `Digestor`, `Reasoner`, `Wrapper`, `ReportScraper`
- **Functions/methods:** `snake_case` — `gather_prompt()`, `get_analysis()`, `read_bug_report()`
- **Variables:** `snake_case` — `bug_ids`, `commit_ids`, `issue_body`
- **Constants:** `UPPER_SNAKE_CASE` — `GITHUB_REPO`, `COMMIT_LIST_PATH`, `GITHUB_TOKEN`
- **Instance "constants":** `UPPER_SNAKE_CASE` — `self.API_KEY`, `self.URL`
- **Domain abbreviations:** mixed case — `chatZS()` (Zero-Shot), `chatFS()` (Few-Shot),
  `ZS_RO()` (Zero-Shot Reasoning Only)

### Module Organization

- One class per file in `agents/`.
- `Agent` is the abstract base class; `Digestor`, `Reasoner`, `Evaluator` inherit from it.
- `Helper` is a stateless utility class (instantiated each time: `Helper().method()`).
- Top-level scripts use `if __name__ == "__main__":` guards with hardcoded (emptied) credentials.

### Error Handling

- Minimal error handling throughout. No custom exception classes.
- Broad `try/except Exception` with `print()` for error reporting (no logging module).
- HTTP errors checked via `response.status_code` with print-based reporting.
- `subprocess.CalledProcessError` caught in `kernel_gitshow.py`.
- `FileNotFoundError` caught with `sys.exit(1)` in some scripts.

### Type Annotations

Effectively unused. One exception exists in `kernel_api.py`:
```python
def strip_redundant_lines(commit_msg: str) -> str:
```

### Comments and Documentation

- Class-level docstrings use `'''triple single quotes'''` in `agents/`.
- `kernel_gitshow.py` uses `"""triple double quotes"""` for function docstrings.
- Inline comments are bilingual (Chinese and English).
- Section separators use `# === 标题 ===` style in some files.
- Commented-out dead code is common throughout.

### Formatting

- No enforced formatting standard.
- Indentation: 4 spaces (standard Python).
- No consistent line length limit.
- String literals: mixed single and double quotes, no enforced preference.

### Git Conventions

- Commit messages: lowercase, short phrases, no punctuation.
- No conventional commit prefixes (no `feat:`, `fix:`, etc.).
- Examples: `update gcc scratch with Dev review`, `trivial fix`, `add discussion`.

### API Key Handling

API keys, model names, and base URLs are stored as string variables in `if __name__ == "__main__"`
blocks or passed to class constructors. They are emptied before committing. There is no `.env`
file usage, no `python-dotenv`, and no `.gitignore` file.
