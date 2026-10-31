# Implementation Readiness Review Report: docs/designs/local_project_os.md

**Target:** `docs/designs/local_project_os.md` (`lines 220-294`)  
**Stage:** 9 (Implementation Readiness Test)  
**Reviewers:** `egm-implementation-readiness`, `egm-codebase-details`, `egm-style`

## Severity Breakdown
* 🔴 **Blocker**: 3
* 🟡 **Major**: 4
* 🟢 **Nit**: 3
* **Total Findings**: 10

---

## Prioritized Findings (Blockers -> Major -> Nits)

### 1. Frontend Implementation Scope Omission (`ui/static/app.js` and `ui/static/styles.css`) - Severity: Blocker
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Lines 268-282 (Section 6.5, Fase 5: Dashboard Visual)
* **Discrepancy Description**: Fase 5 lists only `ui/index.html` under "Arquivos a Modificar". In the actual codebase, `ui/index.html` is merely a markup shell (439 lines); all application state, event listeners, API communications, tab navigation, and modal controllers reside in `ui/static/app.js` (1,278 lines), styled by `ui/static/styles.css` (1,250 lines). Modifying `ui/index.html` alone cannot implement Mermaid dynamic rendering, zoom/pan canvas controls, notes Kanban boards, or reconciliation modal interactions.
* **Rationale & Recommendation**: Explicitly add `ui/static/app.js` and `ui/static/styles.css` to "Arquivos a Modificar" in Fase 5. Detail instructions for removing obsolete skills/fleet controllers (`initHub`, `initStudio`, `/api/catalog`) and adding Project OS controllers (`initProjects`, `initMermaidView`, `initKanbanNotes`, `initReconciliationModal`).

---

### 2. Architectural Framework Contradiction & Missing Dependency Manifest - Severity: Blocker
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Lines 257-267 (Section 6.4, Fase 4) & Line 290 (Section 6.6, Fase 6)
* **Discrepancy Description**: The Technical Plan specifies the backend as `Python / FastAPI` (lines 69 and 155). However, the existing server (`ui/app.py`) is implemented using Python standard library `http.server.SimpleHTTPRequestHandler` without external dependencies. Fase 4 lists `ui/app.py` under "Arquivos a Modificar" without specifying whether it is rewritten into FastAPI or retained as `http.server`. If converting to FastAPI, no dependency manifest (`requirements.txt` or `pyproject.toml` with `fastapi`, `uvicorn`, `pydantic`) is created in the plan. Furthermore, Fase 6 instructs starting the server with `python ui/app.py`, which fails for standard FastAPI apps unless an inline `uvicorn.run(...)` entrypoint is explicitly built.
* **Rationale & Recommendation**: Eliminate the architectural contradiction. Either formally retain the zero-dependency standard library `http.server` (adjusting sections 4.1/4.4), or specify a full migration to FastAPI. If FastAPI is selected, add `requirements.txt` to "Arquivos a Criar" in Fase 2/4 and update operational commands to `uvicorn ui.app:app --reload --port 4100` or specify the `if __name__ == '__main__': uvicorn.run(...)` bootstrap in `ui/app.py`.

---

### 3. Underspecified LLM Integration & Runtime Architecture - Severity: Blocker
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Lines 254-256 (Section 6.3, Fase 3, `app/engine/llm_bridge.py`)
* **Discrepancy Description**: `app/engine/llm_bridge.py` is tasked with processing unstructured documentation and generating structured JSON summaries containing Techspec, Mermaid workflows, and Mermaid ERDs. However, the plan provides zero implementation instructions regarding:
  1. The LLM integration method (OpenAI, Anthropic Claude, Google Gemini, Ollama, or local CLI process).
  2. Required environment variables, credentials, or API keys.
  3. Extraction prompt templates, schema definitions, and token/rate limit handling.
  4. Deterministic fallback behavior when no API key is supplied or when LLM output contains invalid Mermaid syntax.
  Leaving all of these architectural decisions to the implementer renders this core feature non-deterministic.
* **Rationale & Recommendation**: Explicitly specify the LLM client protocol (e.g., Gemini SDK / OpenAI-compatible endpoint / local runner), define environment variable requirements (`GEMINI_API_KEY` etc.), provide the target extraction JSON schema, and mandate a regex/heuristic fallback parser for environments running offline or without API keys.

---

### 4. Reconciliation Mechanism Algorithmic Underspecification & Note Schema Gap - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Lines 252-253 (Section 6.3, Fase 3, `app/engine/reconciler.py`) & Line 266 (Section 6.4, Fase 4)
* **Discrepancy Description**: `reconciler.py` is defined to compare notes in status `planejado` or `em-revisao` against changed physical files in the target project. However:
  1. Section 4.5 specifies note frontmatter with only `(status, data, versão)`, omitting file path references (`target_files` / `affected_paths`). Without target file metadata in notes, the reconciler cannot deterministically correlate notes to changed files.
  2. The mechanism for inspecting target project changes is not specified (e.g., `git status --porcelain`, `git diff`, or file modification timestamps).
  3. Failure modes (projects that are not Git repositories, missing `git` CLI on Windows, dirty working trees) are unhandled.
  4. The JSON response schema for `/api/projects/{id}/reconcile` is undefined.
* **Rationale & Recommendation**: Define the exact note frontmatter schema (mandating `files: [...]`), specify the concrete Git inspection command with filesystem timestamp fallback, and define the reconciliation report JSON contract returned by the API.

---

### 5. API Contract Incompleteness & Missing Endpoint in Implementation Tasks - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Lines 260-266 (Section 6.4, Fase 4)
* **Discrepancy Description**: Section 4.4 explicitly defines `POST /api/projects/{id}/sync` ("Dispara re-análise do diretório do projeto e atualiza o resumo"). However, in Fase 4 (line 266), `/api/projects/{id}/sync` is completely omitted from the list of endpoints to implement. Additionally, the plan does not define request payloads, response bodies, HTTP status error codes, or the semantic version bump algorithm for `/api/projects/{id}/bump-version`.
* **Rationale & Recommendation**: Add `POST /api/projects/{id}/sync` to the Fase 4 implementation tasks. Document request/response contracts for all routes, and specify whether `bump-version` accepts semantic bump types (`patch`, `minor`, `major`) or arbitrary version strings.

---

### 6. Python Package Initialization & Import Namespace Conflict - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Lines 246-256 (Section 6.3, Fase 3) & Lines 260-266 (Section 6.4, Fase 4)
* **Discrepancy Description**: Fase 3 creates modules under `app/engine/`, but omits `app/__init__.py` and `app/engine/__init__.py`. Furthermore, the server entrypoint is located at `ui/app.py`. When running `python ui/app.py`, Python adds `ui/` to `sys.path`. Attempting `import app.engine` risks namespace collisions with `ui/app.py` or fails with `ModuleNotFoundError: No module named 'app'` unless the repository root is explicitly added to `sys.path`.
* **Rationale & Recommendation**: Add `app/__init__.py` and `app/engine/__init__.py` to "Arquivos a Criar" in Fase 3. Specify explicit root path resolution (`sys.path.insert(0, str(PROJECT_ROOT))`) inside `ui/app.py` or restructure entrypoints to avoid shadowing.

---

### 7. Total Absence of Automated Testing & CI Verification Pipeline - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Line 232 (Section 6.1, Fase 1) & Lines 283-294 (Section 6.6, Fase 6)
* **Discrepancy Description**: Fase 1 deletes `.github/workflows/validate.yml`, eliminating the existing automated validation pipeline. The plan does not introduce any test tasks or files (`tests/test_scanner.py`, `tests/test_reconciler.py`, `tests/test_api.py`), nor does it create a replacement CI workflow to validate `data/projects.json` schemas, Python syntax, or unit tests.
* **Rationale & Recommendation**: Add an explicit verification and testing task specifying test suites for `scanner.py`, `reconciler.py`, and API endpoints. Create `.github/workflows/ci.yml` in Fase 6 to automate test execution on push/PR.

---

### 8. Missing Note Convention Template - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Lines 242-244 (Section 6.2, Fase 2)
* **Discrepancy Description**: Fase 2 creates convention templates for `TECHSPEC`, `WORKFLOWS`, and `DATABASE`, but omits `templates/convention/NOTE.template.md`, despite notes being a central pillar of the system.
* **Rationale & Recommendation**: Add `templates/convention/NOTE.template.md` to "Arquivos a Criar" in Fase 2 with standardized YAML frontmatter fields (`id`, `title`, `status`, `target_files`, `date`, `version_target`).

---

### 9. Status Enumeration Inconsistency Across Sections - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Line 253 (Fase 3) vs Line 280 (Fase 5) vs Section 4.3
* **Discrepancy Description**: Note lifecycle statuses are defined inconsistently: Section 4.3 uses `Aberta` -> `Planejada` / `Em Revisão` -> `Incorporada`, Fase 3 uses `planejado` ou `em-revisao`, and Fase 5 uses `Ideia` -> `Planejado` -> `Em Revisão` -> `Incorporado`.
* **Rationale & Recommendation**: Standardize a single canonical status enum (e.g., `idea`, `planned`, `in_review`, `incorporated`) across API schemas, backend validators, and frontend Kanban columns.

---

### 10. Unspecified Mermaid.js & Pan/Zoom Distribution Strategy - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** Lines 278-279 (Section 6.5, Fase 5)
* **Discrepancy Description**: Fase 5 specifies interactive zoom/pan Mermaid rendering without indicating whether Mermaid.js and Pan/Zoom libraries are loaded via CDN or bundled locally in `ui/static/vendor/`. For an offline-capable local developer console, unpinned CDN links can fail in disconnected environments.
* **Rationale & Recommendation**: Explicitly state the library distribution strategy (CDN link with integrity hash vs local vendor files under `ui/static/vendor/`).
