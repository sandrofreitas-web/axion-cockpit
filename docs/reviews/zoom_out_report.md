# Zoom-Out Architectural Review: Local Project OS

* **Target:** `docs/designs/local_project_os.md` (Lines 1–294)
* **Stage:** 5 (Initial Zoom Out Review)
* **Status:** Findings Identified (Blockers, Majors, Nits)

---

### Finding 1: LLM Engine in Backend Directly Contradicts Non-Goals (NG1) and Inflates System Complexity
* **Severity:** **Blocker**
* **Affected Scope:** Section 3.2 (Line 47), Section 4.1 (Lines 73, 93), Section 4.2 (Lines 114–120), Section 6.3 (Lines 254–256)
* **Simplicity Rationale (YAGNI & Architecture Boundaries):**
  - Section 3.2 explicitly declares: `NG1 - Execução e Orquestração de Agentes: O OS não executa comandos nem controla runtimes de LLM/agentes; a execução e o comando operacional permanecem externos (via CLI/Orca)`.
  - In direct contradiction, Sections 4.1, 4.2, and 6.3 introduce `app/engine/llm_bridge.py`, an `LLM_Bridge` component, and a `POST /api/projects/{id}/sync` backend endpoint dedicated to performing "Normalização e Extração com LLM (Flexible Path)".
  - Embedding an LLM extraction client inside the local Python backend introduces SDK dependencies (OpenAI/Anthropic/Gemini/Ollama), API key management, token costs, network timeouts, prompt tuning, and JSON schema repair logic into what is supposed to be a simple local file viewer.
  - If extraction is executed externally by Orca/developer agents, `llm_bridge.py` inside the backend is a redundant architectural phantom.
* **Simplification / Alternative:**
  - Enforce strict adherence to **NG1**: remove `app/engine/llm_bridge.py` and internal LLM hooks from the backend.
  - The backend should be a zero-dependency passive file reader. Documentation can be authored using standard Markdown/Mermaid templates (`ARCHITECTURE.md`, `docs/*.md`) or populated asynchronously by external CLI agents (Orca). The backend simply parses and serves existing files directly.

---

### Finding 2: Cache Summaries (`_summary.json`) Introduce Stale Documentation Drift
* **Severity:** **Blocker**
* **Affected Scope:** Section 1 (Lines 15–16), Section 4.1 (Line 79), Section 4.2 (Lines 115–120), Section 4.5 (Line 178), Section 6.3 (Lines 254–256)
* **Simplicity Rationale (Root Problem Divergence):**
  - The Problem statement explicitly identifies: `2. Risco de Stale Documentation e Duplicação: Criar um portal centralizado que replique manualmente especificações ou códigos gera uma segunda fonte da verdade. Essa abordagem rapidamente resulta em drift` (Lines 15–16).
  - Yet the design recreates this exact problem by writing extracted snapshots to `data/cache/{project_id}_summary.json`. As soon as a developer updates code, schemas, or docs in a monitored project, the Project OS cache is immediately stale and out of sync until a manual resync is triggered.
  - For local projects running on the same host filesystem, caching static text files is a premature optimization. Local disk reads for Markdown files take <1ms.
* **Simplification / Alternative:**
  - Eliminate `data/cache/{project_id}_summary.json` as a persistent cache.
  - The API endpoint (`/api/projects/{id}/summary` or `/docs`) should read directly from the monitored project's filesystem on demand. Mermaid code blocks can be rendered client-side on the fly by Mermaid.js, ensuring 100% real-time fidelity with zero drift.

---

### Finding 3: Premature Dependency Weight — Introducing FastAPI for an 8-Endpoint Observer
* **Severity:** **Major**
* **Affected Scope:** Section 4.1 (Line 69), Section 4.4 (Lines 155–169), Section 6.4 (Lines 260–267)
* **Simplicity Rationale (Code Minimization & Wheel Reinvention):**
  - The current codebase (`ui/app.py`) runs a functional local server with zero external dependencies using Python's standard library `http.server` and `socketserver`. It starts instantly via `python ui/app.py` on any Python 3 environment.
  - Replacing this with FastAPI requires adding `fastapi`, `uvicorn`, `pydantic`, `starlette`, and `anyio`. This creates environment friction (virtualenv/pip management) and complicates Docker/container workflows for a single-user local tool with ~8 straightforward CRUD/file-serving routes.
  - Furthermore, Section 6.6 (Line 290) still states `python ui/app.py` for execution, which clashes with standard ASGI server lifecycles (`uvicorn`).
* **Simplification / Alternative:**
  - Retain Python standard library (`http.server`) or specify a single ultra-lightweight micro-framework with an explicit dependency file (`pyproject.toml` or `requirements.txt`).
  - Keep the server zero-friction: a developer should be able to clone and run immediately without installing heavy ASGI frameworks.

---

### Finding 4: Speculative "Reconciler" Engine (`app/engine/reconciler.py`) vs. Existing Git Telemetry
* **Severity:** **Major**
* **Affected Scope:** Section 4.1 (Lines 72, 92, 97), Section 4.3 (Lines 121–151), Section 4.4 (Lines 167–168), Section 6.3 (Lines 252–253)
* **Simplicity Rationale (YAGNI & Over-Engineering):**
  - The design introduces `app/engine/reconciler.py` and a multi-step pre-version audit workflow (`/api/projects/{id}/reconcile` and `/api/projects/{id}/bump-version`) claiming to automatically audit whether pending notes were applied to physical files.
  - Automatically verifying that freeform Markdown notes (e.g. "Refactor auth pipeline") correspond to arbitrary git diffs is either technically speculative or amounts to checking `git status` / `git diff`.
  - The existing codebase *already* implements `get_git_telemetry(project_path)` in ~25 lines using `git status --porcelain` and `git branch --show-current`.
  - Building a bespoke reconciliation state machine overcomplicates a workflow where the human or orchestrator (Orca) is the entity doing the actual verification.
* **Simplification / Alternative:**
  - Remove `app/engine/reconciler.py` as a standalone engine.
  - Reuse the existing `get_git_telemetry()` function in `ui/app.py` to expose uncommitted changes, active branch, and recent commit history directly in the UI.
  - Let the operator inspect git status and manually transition note statuses (`Planejado` -> `Incorporado`) without building an artificial reconciliation verification engine.

---

### Finding 5: Isolated Notes Ledger in OS Repo (`data/notes/{id}/*.md`) vs Project-Local Backlogs
* **Severity:** **Major**
* **Affected Scope:** Section 3.1 (Line 41), Section 4.1 (Line 78), Section 4.3 (Lines 131–136), Section 4.5 (Lines 179–183), Section 6.5 (Line 280)
* **Simplicity Rationale (Architectural Dead-End & Drift Risk):**
  - Storing notes inside the Project OS repository (`skills-library/data/notes/{project_id}/`) isolates ideas from the monitored project's own repository and git history.
  - If another developer clones the monitored project, they have zero visibility into notes stored in a completely separate repository on someone else's machine.
  - Additionally, implementing a custom Kanban board (`Ideia`, `Planejado`, `Em Revisão`, `Incorporado`) with individual file CRUD endpoints (`POST/DELETE /api/projects/{id}/notes`) adds significant frontend and backend code to replicate what standard project-local files (`TODO.md`, `ROADMAP.md`, or issue trackers) already provide.
* **Simplification / Alternative:**
  - Keep notes colocated within the monitored project itself (e.g., `<project_root>/docs/notes/` or a single `TODO.md`), allowing the Project OS to simply read and render them.
  - If an out-of-tree staging pad is strictly required, store notes in a single simple JSON/YAML structure rather than managing a distributed directory tree of individual Markdown files with custom frontmatters.

---

### Finding 6: Template Rigidity & Altitude Drops
* **Severity:** **Nit**
* **Affected Scope:** Section 6.2 (Lines 242–244), Section 6.5 (Lines 276–281)
* **Simplicity Rationale:**
  - Section 6.2 mandates three distinct templates: `TECHSPEC.template.md`, `WORKFLOWS.template.md`, and `DATABASE.template.md`. In real-world repositories, architectural documentation is often consolidated into a single `ARCHITECTURE.md` or `docs/index.md`. Enforcing three rigid files conflicts with the stated goal of flexible ingestion.
  - Section 6.5 delves into granular frontend layout details (tabs, canvas pan/zoom, specific CSS cards) which are implementation details rather than architectural specifications.
* **Simplification / Alternative:**
  - Provide a single consolidated `ARCHITECTURE.template.md` covering techspec, workflows, and database schemas with standard Mermaid blocks.
  - Keep Section 6.5 focused on core API-UI interaction contracts rather than specific UI controls.
