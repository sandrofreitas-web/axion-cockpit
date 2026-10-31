# Critic Review Report: docs/designs/local_project_os.md

**Target:** `docs/designs/local_project_os.md` (`Lines 1-219`)  
**Stage:** 7 (Critic Review)  
**Reviewers:** `egm-design`, `egm-structural`, `egm-style`

## Severity Breakdown
* 🔴 **Blocker**: 2
* 🟡 **Major**: 4
* 🟢 **Nit**: 3
* **Total Findings**: 9

---

## Prioritized Findings (Blockers -> Major -> Nits)

### 1. Unbounded Local Filesystem Access & Path Traversal Vulnerability - Severity: Blocker
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `Lines 159-161` (Section 4.4) & `Lines 70-71` (Section 4.1)
* **Discrepancy Description**: The specification accepts arbitrary local filesystem paths (`path`) via `POST /api/projects` without defining sanitization, canonical boundary enforcement, or directory whitelisting. Because the backend runs locally with full disk read permissions and without authentication or chroot jail boundaries, this design is vulnerable to path traversal (`../../`) or registration of sensitive host directories (e.g., `~/.ssh`, `C:\Windows`, `.env`, or credential folders). The scanner would ingest, summarize, and expose these contents through the API.
* **Rationale & Recommendation**: Mandate strict path validation (canonical absolute path checking via `os.path.realpath`, verification of directory existence, restriction against root or system directories) and specify localhost/CORS security policies in the technical plan.

---

### 2. Contradiction Between Flexible LLM Ingestion (G2) and Out-of-Scope Agent Execution (NG1) - Severity: Blocker
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Lines 39, 47, 73, 114-120` (Sections 3.1, 3.2, 4.1, 4.2)
* **Discrepancy Description**: Goal G2 ("Ingestão Flexível Assistida por LLM") and Component `LLM_Bridge` (Line 73) specify an automated LLM extraction pipeline within the OS backend. Conversely, Non-Goal NG1 (Line 47) explicitly dictates: *"O OS não executa comandos nem controla runtimes de LLM/agentes; a execução e o comando operacional permanecem externos (via CLI/Orca)"*. The technical specification fails to define how `LLM_Bridge` operates without violating NG1. It completely omits the invocation contract (CLI subprocess vs. direct OpenAI/Anthropic API client vs. pre-cached summaries), API key management, execution timeouts, and offline handling.
* **Rationale & Recommendation**: Resolve the architectural contradiction. Define the exact invocation boundary for `LLM_Bridge` (e.g., whether it calls an external CLI tool passed by the operator, consumes a pre-parsed artifact, or directly invokes an LLM API client) and define deterministic fallback behavior when LLM services are unreachable.

---

### 3. Inconsistent and Unspecified Note Lifecycle State Machine - Severity: Major
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `Lines 41, 136, 142, 148, 165, 168` (Sections 3.1, 4.3, 4.4)
* **Discrepancy Description**: Note states are divergent across sections:
  * Section 3.1 (G4): `Ideia`, `Planejado`, `Incorporado` (3 states)
  * Sequence Diagram (Line 136): `Aberta`
  * Sequence Diagram (Line 142): `Planejada`, `Em Revisão`
  * Sequence Diagram (Line 148) & API (Line 168): `Incorporada`
  The lack of a single canonical state machine creates ambiguity for Kanban board column mapping and backend status validation.
* **Rationale & Recommendation**: Define a formal state machine enum (e.g., `IDEA`, `PLANNED`, `IN_REVIEW`, `INCORPORATED`, `ARCHIVED`) with explicit permitted state transitions in Section 4.3.

---

### 4. Missing Formal Schema Specifications for Flat-File Persistence - Severity: Major
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `Lines 76-80, 115-119, 170-184` (Sections 4.1, 4.2, 4.5)
* **Discrepancy Description**: While G6 establishes flat-file storage as a core architectural guarantee, the document omits the formal schemas (JSON Schema, TypeScript interfaces, or Pydantic models) for:
  1. `data/projects.json` (required fields: id, name, path, tags, version, timestamp fields).
  2. `data/cache/{project_id}_summary.json` (exact shape of techspec, workflows, and database blocks).
  3. Frontmatter of `data/notes/{project_id}/*.md` (metadata keys, formatting, types).
* **Rationale & Recommendation**: Provide explicit schema definitions for all three file structures in Section 4.5 to eliminate interface divergence between the backend and UI.

---

### 5. REST API Contract Anti-Patterns & Ambiguous Endpoints - Severity: Major
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Lines 157-169` (Section 4.4)
* **Discrepancy Description**:
  * `POST /api/projects/{id}/notes`: Documented as "Cria ou edita uma nota de melhoria". Combining creation and mutation in a single POST without resource identifier routing violates REST design principles; updates must be addressed via `PUT` or `PATCH /api/projects/{id}/notes/{note_id}`.
  * `POST /api/projects/{id}/reconcile`: Triggering reconciliation returns diff data, but it is modeled as POST without specifying request payload or query parameters.
  * HTTP status codes (200, 201, 400, 404, 422) and standard error response schemas are entirely absent.
* **Rationale & Recommendation**: Separate creation (`POST`) from update (`PUT`/`PATCH`), specify payload types and parameters, and document expected HTTP status codes.

---

### 6. Missing Fallback View and UX Degradation Strategy for Mermaid Diagrams - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Lines 40, 65, 88, 117-119` (Sections 3.1, 4.1, 4.2)
* **Discrepancy Description**: LLM-extracted Mermaid syntax often suffers from syntax errors, unescaped characters, or oversized graphs that cause client-side rendering crashes. Section 4 lacks UX degradation affordances: there is no specification for syntax validation before render, raw code fallback view, copy-to-clipboard actions for manual debugging, or canvas navigation controls (reset zoom, pan bounds, SVG export).
* **Rationale & Recommendation**: Specify client-side UX error boundaries in Section 4.1/4.2, including syntax error alerts with line indicators, a raw Markdown toggle, and canvas controls (fit-to-screen, zoom, export).

---

### 7. Bilingual Heading and Section Asymmetry - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Lines 1, 10, 22, 35, 55, 187` (Sections 1 to 5)
* **Discrepancy Description**: Level 2 headings are written in English (`## 1. The Problem`, `## 2. Overview`, `## 3. Goals & Non-Goals`, `## 4. Technical Plan`, `## 5. Alternatives Considered`), whereas Level 3 subheadings and the entire document body are written in Brazilian Portuguese (`### 4.1. Arquitetura de Alto Nível`, `### 4.2. Ingestão Flexível...`).
* **Rationale & Recommendation**: Standardize all headings to Brazilian Portuguese (e.g., `## 1. O Problema`, `## 2. Visão Geral`, `## 3. Objetivos e Não-Objetivos`, `## 4. Plano Técnico`, `## 5. Alternativas Consideradas`) to preserve stylistic cohesion.

---

### 8. Vague Lexicon and Metaphorical Jargon - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Lines 14, 24, 216`
* **Discrepancy Description**: The copy uses informal metaphors such as "cockpit local" (Lines 14, 24) and "corte limpo (clean cut)" (Line 216) instead of precise architectural terminology.
* **Rationale & Recommendation**: Replace "cockpit local" with "painel consolidado de observabilidade de projetos" and "corte limpo" with "desacoplamento e remoção definitiva de componentes legados".

---

### 9. Undefined Git Inspection Method - Severity: Nit
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `Line 143` (Section 4.3)
* **Discrepancy Description**: The sequence diagram states *"Lê status Git / arquivos alterados / CHANGELOG"* without specifying whether the backend executes `git` via subprocess, relies on a Python Git library, or handles non-Git repositories.
* **Rationale & Recommendation**: Explicitly declare the reconciliation inspection mechanism (e.g. `subprocess` executing `git status --porcelain` with graceful fallback to file timestamps when a project is not version-controlled with Git).
